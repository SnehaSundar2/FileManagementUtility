"""Safe file operations with preview, rollback, trash and undo.

Every operation works in two steps:

1. plan_*()  builds a list of Step(src, dst) and checks it for conflicts
             without touching the disk, so the user can preview it.
2. execute() carries the plan out. If any step fails, the steps already
             done are reversed, so the folder is never left half-changed.
             The completed operation is recorded in a journal so it can be
             undone later.

Nothing is ever permanently deleted except by purge_trash(); "delete"
moves files into a hidden trash folder inside the managed root.
"""

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import validators as v
from .exceptions import (
    ConflictError,
    NothingToDoError,
    OperationError,
    UndoError,
)
from .scanner import JOURNAL_FILE, TRASH_DIR

log = logging.getLogger("filemanager")

RENAME_MODES = ("prefix", "suffix", "replace", "sequence", "lower")


@dataclass
class Step:
    src: Path
    dst: Path
    kind: str = "move"  # "move" or "copy"


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


class FileManager:
    def __init__(self, root):
        self.root = v.validate_directory(root, "Managed folder")
        self.trash = self.root / TRASH_DIR
        self.journal_path = self.root / JOURNAL_FILE

    # ------------------------------------------------------------ helpers
    def rel(self, path):
        return Path(path).resolve().relative_to(self.root).as_posix()

    def _check_inside(self, path):
        return v.validate_inside(self.root, path)

    def _unique(self, dst, taken):
        """Return dst, or 'name (1).ext', 'name (2).ext'... if dst is taken."""
        candidate, n = dst, 1
        while candidate.exists() or str(candidate).lower() in taken:
            candidate = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
            n += 1
        return candidate

    # ------------------------------------------------------------ planning
    def plan_organize(self, files):
        """Move files that sit directly in the root into <root>/<Category>/."""
        steps, taken = [], set()
        for f in files:
            if f.path.parent != self.root:
                continue
            dst = self._unique(self.root / f.category / f.name, taken)
            taken.add(str(dst).lower())
            steps.append(Step(f.path, dst))
        if not steps:
            raise NothingToDoError("No loose files in the top folder to organise.")
        return steps

    def plan_rename(self, files, mode, text="", new_text="", start=1):
        mode = v.validate_choice(mode, RENAME_MODES, "Rename mode")
        if mode in ("prefix", "suffix"):
            v.validate_non_empty(text, mode.title())
        if mode == "replace":
            v.validate_non_empty(text, "Text to replace")
        if mode == "sequence":
            v.validate_filename(text, "Base name")
            start = v.validate_positive_int(start, "Start number", 99999)
        text = v.validate_name_fragment(text)
        new_text = v.validate_name_fragment(new_text, "Replacement text")

        ordered = sorted(files, key=lambda f: f.name.lower())
        width = max(3, len(str(start + len(ordered) - 1)))
        steps = []
        for i, f in enumerate(ordered):
            stem, ext = f.path.stem, f.path.suffix
            if mode == "prefix":
                name = text + f.name
            elif mode == "suffix":
                name = f"{stem}{text}{ext}"
            elif mode == "replace":
                name = stem.replace(text, new_text) + ext
            elif mode == "sequence":
                name = f"{text}_{start + i:0{width}d}{ext}"
            else:  # lower
                name = f.name.lower()
            if name == f.name:
                continue
            v.validate_filename(name, "New name")
            steps.append(Step(f.path, f.path.with_name(name)))
        if not steps:
            raise NothingToDoError("No file names would change.")
        self._check_conflicts(steps)
        return steps

    def _check_conflicts(self, steps):
        sources = {str(s.src).lower() for s in steps}
        seen, problems = {}, []
        for s in steps:
            key = str(s.dst).lower()
            if key in seen:
                problems.append(f"{s.src.name} and {seen[key].name} would both become {s.dst.name}")
            seen[key] = s.src
            occupied = s.dst.exists() and not _same_file(s.src, s.dst)
            if occupied and key not in sources:
                problems.append(f"{s.dst.name} already exists in {self.rel(s.dst.parent) or '.'}")
        if problems:
            raise ConflictError("Operation cancelled, nothing was changed:\n    - " + "\n    - ".join(problems))

    def plan_copy(self, files, folder_name):
        folder = self._check_inside(v.validate_filename(folder_name, "Folder name"))
        steps, taken = [], set()
        for f in files:
            if f.path.parent == folder:
                continue
            dst = self._unique(folder / f.name, taken)
            taken.add(str(dst).lower())
            steps.append(Step(f.path, dst, "copy"))
        if not steps:
            raise NothingToDoError("No files to copy.")
        return steps

    def plan_trash(self, files):
        batch = self.trash / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        steps = [Step(f.path, batch / self.rel(f.path)) for f in files]
        if not steps:
            raise NothingToDoError("No files selected.")
        return steps

    def plan_trash_duplicates(self, groups):
        """Keep the first file of every duplicate group, trash the rest."""
        return self.plan_trash([f for g in groups for f in g[1:]])

    # ------------------------------------------------------------ execution
    @staticmethod
    def _key(path):
        return str(path).lower()

    def _expand(self, steps):
        """If a destination is also another step's source (a->b, b->c), go via
        temporary names so no file is ever overwritten."""
        sources = {self._key(s.src) for s in steps if s.kind == "move"}
        chained = any(s.kind == "move" and self._key(s.dst) in sources and not _same_file(s.src, s.dst)
                      for s in steps)
        if not chained:
            return list(steps)
        first, second = [], []
        for i, s in enumerate(steps):
            if s.kind == "move":
                tmp = s.src.with_name(f".fmu-tmp-{i}-{s.src.name}")
                first.append(Step(s.src, tmp))
                second.append(Step(tmp, s.dst))
            else:
                second.append(s)
        return first + second

    def _apply(self, step):
        step.dst.parent.mkdir(parents=True, exist_ok=True)
        if step.kind == "copy":
            shutil.copy2(step.src, step.dst)
        else:
            shutil.move(str(step.src), str(step.dst))

    def _revert(self, step):
        if step.kind == "copy":
            step.dst.unlink()
        else:
            shutil.move(str(step.dst), str(step.src))

    def _run(self, steps):
        """Apply steps in order; on any failure reverse the completed ones."""
        expanded = self._expand(steps)
        done = []
        try:
            for s in expanded:
                self._apply(s)
                done.append(s)
        except OSError as exc:
            failed = expanded[len(done)]
            for s in reversed(done):
                try:
                    self._revert(s)
                except OSError:
                    log.exception("Rollback failed for %s", s.dst)
            raise OperationError(
                f"Could not process {failed.src.name}: {exc.strerror or exc}. "
                f"All completed changes were rolled back; nothing was changed."
            ) from exc

    def execute(self, steps, action):
        for s in steps:
            self._check_inside(s.src)
            self._check_inside(s.dst)
        self._run(steps)
        self._record(action, steps)
        log.info("%s: %d file(s)", action, len(steps))
        return len(steps)

    # ------------------------------------------------------------ journal / undo
    def _load_journal(self):
        if not self.journal_path.exists():
            return []
        try:
            data = json.loads(self.journal_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("journal is not a list")
            return data
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable journal: %s", exc)
            return []

    def _save_journal(self, entries):
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)
        os.replace(tmp, self.journal_path)

    def _record(self, action, steps):
        entries = self._load_journal()
        entries.append({
            "action": action,
            "time": datetime.now().isoformat(timespec="seconds"),
            "steps": [[self.rel(s.src), self.rel(s.dst), s.kind] for s in steps],
        })
        self._save_journal(entries)

    def history(self):
        return self._load_journal()

    def undo_last(self):
        entries = self._load_journal()
        if not entries:
            raise UndoError("There is nothing to undo.")
        entry = entries[-1]
        steps = [Step(self.root / src, self.root / dst, kind) for src, dst, kind in entry["steps"]]

        destinations = {self._key(s.dst) for s in steps}
        problems = []
        for s in steps:
            if not s.dst.exists():
                problems.append(f"{self.rel(s.dst)} no longer exists")
            elif (s.kind == "move" and s.src.exists() and not _same_file(s.src, s.dst)
                  and self._key(s.src) not in destinations):
                problems.append(f"{self.rel(s.src)} has been re-created")
        if problems:
            raise UndoError("Cannot undo safely, files changed since the operation:\n    - "
                            + "\n    - ".join(problems[:10]))

        copies = [s for s in steps if s.kind == "copy"]
        try:
            for s in copies:
                s.dst.unlink()
        except OSError as exc:
            raise OperationError(f"Undo stopped at {s.dst.name}: {exc.strerror or exc}") from exc
        self._run([Step(s.dst, s.src) for s in reversed(steps) if s.kind == "move"])
        self._remove_empty_dirs(s.dst.parent for s in steps)
        entries.pop()
        self._save_journal(entries)
        log.info("Undid '%s' (%d file(s))", entry["action"], len(steps))
        return entry

    def _remove_empty_dirs(self, folders):
        """Tidy up folders an undone operation created (e.g. category or trash folders)."""
        for folder in sorted(set(folders), key=lambda p: len(p.parts), reverse=True):
            while folder != self.root and folder.exists():
                try:
                    folder.rmdir()  # only succeeds if empty
                except OSError:
                    break
                folder = folder.parent

    # ------------------------------------------------------------ trash
    def trash_contents(self):
        if not self.trash.exists():
            return 0, 0
        files = [p for p in self.trash.rglob("*") if p.is_file()]
        return len(files), sum(p.stat().st_size for p in files)

    def purge_trash(self):
        """Permanently delete the trash. Trash operations can no longer be undone."""
        count, size = self.trash_contents()
        if count == 0:
            raise NothingToDoError("Trash is already empty.")
        try:
            shutil.rmtree(self.trash)
        except OSError as exc:
            raise OperationError(f"Could not empty trash: {exc.strerror or exc}") from exc
        trash_prefix = TRASH_DIR + "/"
        kept = [e for e in self._load_journal()
                if not any(dst.startswith(trash_prefix) for _, dst, _ in e["steps"])]
        self._save_journal(kept)
        log.info("Emptied trash: %d file(s)", count)
        return count, size

