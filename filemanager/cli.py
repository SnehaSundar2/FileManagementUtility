"""Interactive menu-driven command-line interface.

Destructive actions always show a preview and ask for confirmation.
All FileManagerError subclasses are caught and shown as friendly messages.
"""

import logging

from . import analysis, reports
from . import validators as v
from .analysis import human_size
from .exceptions import FileManagerError
from .operations import RENAME_MODES, FileManager
from .scanner import scan

log = logging.getLogger("filemanager")

MENU = """
================ FILE MANAGEMENT UTILITY ================
 EXPLORE                        CLEAN UP
  1. Folder summary              7. Organise files by type
  2. List files                  8. Bulk rename
  3. Search files                9. Copy files to a folder
  4. Largest files              10. Move duplicates to trash
  5. Find duplicates            11. Move files to trash
  6. Empty files & folders      12. Undo last operation
 REPORTS                        13. Operation history
 15. Save folder report         14. Empty trash (permanent)
 16. Export file list (CSV)
 17. Change folder               0. Exit
========================================================="""

PREVIEW_LIMIT = 15


def ask(prompt):
    return input(f"  {prompt}: ").strip()


def confirm(prompt):
    return ask(f"{prompt} [y/N]").lower() in {"y", "yes"}


class FileManagerCLI:
    def __init__(self, root=None):
        self.fm = FileManager(root) if root else None
        self.actions = {
            "1": self.show_summary, "2": self.list_files, "3": self.search,
            "4": self.largest, "5": self.duplicates, "6": self.empties,
            "7": self.organise, "8": self.rename, "9": self.copy,
            "10": self.trash_duplicates, "11": self.trash_files, "12": self.undo,
            "13": self.history, "14": self.empty_trash, "15": self.save_report,
            "16": self.export_csv, "17": self.change_folder,
        }

    def run(self):
        while self.fm is None:
            try:
                self.change_folder()
            except FileManagerError as exc:
                print(f"  ! Error: {exc}")
        while True:
            print(MENU)
            print(f"  Folder: {self.fm.root}")
            choice = ask("Choose an option")
            if choice == "0":
                print("  Goodbye!")
                return
            action = self.actions.get(choice)
            if action is None:
                print("  ! Invalid option, please enter a number from the menu.")
                continue
            try:
                action()
            except FileManagerError as exc:
                log.warning("%s failed: %s", action.__name__, exc)
                print(f"  ! Error: {exc}")
            except (KeyboardInterrupt, EOFError):
                print("\n  Operation cancelled.")
            except Exception:  # safety net; full traceback goes to the log file
                log.exception("Unexpected error in %s", action.__name__)
                print("  ! An unexpected error occurred. See filemanager.log for details.")

    # ---------------------------------------------------------- helpers
    def scan(self, recursive=True):
        result = scan(self.fm.root, recursive)
        for e in result.errors:
            print(f"  (skipped) {e}")
        return result

    def pick_files(self, recursive=True):
        """Ask for name pattern + extensions and return matching files."""
        pattern = v.validate_pattern(ask("File name pattern, e.g. *.txt or report* [*]"))
        exts = v.validate_extensions(ask("Only these extensions, e.g. jpg,png [all]"))
        return analysis.search(self.scan(recursive).files, pattern, exts)

    def preview(self, steps, verb):
        print(f"\n  Preview - {len(steps)} file(s) will be {verb}:")
        for s in steps[:PREVIEW_LIMIT]:
            print(f"    {self.fm.rel(s.src)}  ->  {self.fm.rel(s.dst)}")
        if len(steps) > PREVIEW_LIMIT:
            print(f"    ... and {len(steps) - PREVIEW_LIMIT} more")

    def run_plan(self, steps, verb, action):
        self.preview(steps, verb)
        if not confirm("Go ahead?"):
            print("  Cancelled. Nothing was changed.")
            return
        count = self.fm.execute(steps, action)
        print(f"  Done: {count} file(s) {verb}. Use option 12 to undo.")

    def print_files(self, files):
        print(reports.format_table(reports.file_rows(files, self.fm.root), reports.FILE_COLUMNS))

    # ---------------------------------------------------------- explore
    def change_folder(self):
        self.fm = FileManager(ask("Folder to manage"))
        print(f"  Now managing {self.fm.root}")

    def show_summary(self):
        s = analysis.summary(self.scan())
        print(f"\n  Files: {s['files']}   Folders: {s['folders']}   "
              f"Total: {human_size(s['total_size'])}   Average: {human_size(s['average_size'])}\n")
        rows = [{"category": c, "files": d["count"], "size": human_size(d["size"])}
                for c, d in sorted(s["by_category"].items(), key=lambda kv: -kv[1]["size"])]
        print(reports.format_table(rows, ["category", "files", "size"]))

    def list_files(self):
        key = v.validate_choice(ask("Sort by [name/size/date/type]") or "name",
                                ("name", "size", "date", "type"), "Sort order")
        self.print_files(analysis.sort_files(self.scan().files, key, descending=key in ("size", "date")))

    def search(self):
        pattern = v.validate_pattern(ask("Name pattern [*]"))
        exts = v.validate_extensions(ask("Extensions [all]"))
        raw_min, raw_max = ask("Minimum size, e.g. 10KB [none]"), ask("Maximum size [none]")
        min_size = v.parse_size(raw_min, "Minimum size") if raw_min else None
        max_size = v.parse_size(raw_max, "Maximum size") if raw_max else None
        if min_size is not None and max_size is not None and min_size > max_size:
            raise v.ValidationError("Minimum size cannot be larger than maximum size.")
        raw_after, raw_before = ask("Modified on/after YYYY-MM-DD [any]"), ask("Modified on/before [any]")
        after = v.validate_date(raw_after, "Start date") if raw_after else None
        before = v.validate_date(raw_before, "End date").replace(hour=23, minute=59, second=59) \
            if raw_before else None
        found = analysis.search(self.scan().files, pattern, exts, min_size, max_size, after, before)
        print(f"  {len(found)} match(es), {human_size(sum(f.size for f in found))} in total.")
        self.print_files(found)

    def largest(self):
        n = v.validate_positive_int(ask("How many? [10]") or 10, "Count", 500)
        self.print_files(analysis.largest(self.scan().files, n))

    def duplicates(self):
        groups, errors = analysis.find_duplicates(self.scan().files)
        for e in errors:
            print(f"  (skipped) {e}")
        if not groups:
            print("  No duplicate files found.")
            return
        print(f"  {len(groups)} group(s) of identical files; "
              f"{human_size(analysis.wasted_space(groups))} could be freed.")
        for i, g in enumerate(groups, 1):
            print(f"\n  Group {i} - {human_size(g[0].size)} each")
            for j, f in enumerate(g):
                print(f"    {'keep ' if j == 0 else 'extra'}  {f.relative_to(self.fm.root)}")

    def empties(self):
        result = self.scan()
        files, folders = analysis.empty_files(result.files), analysis.empty_folders(result)
        print(f"  Empty files ({len(files)}):")
        for f in files:
            print(f"    {f.relative_to(self.fm.root)}")
        print(f"  Empty folders ({len(folders)}):")
        for p in folders:
            print(f"    {p.relative_to(self.fm.root).as_posix()}")

    # ---------------------------------------------------------- clean up
    def organise(self):
        steps = self.fm.plan_organize(self.scan(recursive=False).files)
        self.run_plan(steps, "moved into category folders", "Organise by type")

    def rename(self):
        print("  Files in the top folder only.")
        files = self.pick_files(recursive=False)
        mode = v.validate_choice(ask(f"Mode [{'/'.join(RENAME_MODES)}]"), RENAME_MODES, "Rename mode")
        text, new_text, start = "", "", 1
        if mode == "prefix":
            text = ask("Prefix to add")
        elif mode == "suffix":
            text = ask("Suffix to add before the extension")
        elif mode == "replace":
            text, new_text = ask("Text to find"), ask("Replace with (blank = remove)")
        elif mode == "sequence":
            text, start = ask("Base name, e.g. photo"), ask("Start number [1]") or 1
        steps = self.fm.plan_rename(files, mode, text, new_text, start)
        self.run_plan(steps, "renamed", f"Bulk rename ({mode})")

    def copy(self):
        files = self.pick_files()
        steps = self.fm.plan_copy(files, ask("Destination folder name (inside this folder)"))
        self.run_plan(steps, "copied", "Copy files")

    def trash_duplicates(self):
        groups, _ = analysis.find_duplicates(self.scan().files)
        if not groups:
            print("  No duplicate files found.")
            return
        steps = self.fm.plan_trash_duplicates(groups)
        print(f"  Keeping one copy of each; {human_size(analysis.wasted_space(groups))} will be freed.")
        self.run_plan(steps, "moved to trash", "Trash duplicates")

    def trash_files(self):
        files = self.pick_files()
        self.run_plan(self.fm.plan_trash(files), "moved to trash", "Move to trash")

    def undo(self):
        entries = self.fm.history()
        if entries:
            last = entries[-1]
            if not confirm(f"Undo '{last['action']}' ({len(last['steps'])} file(s), {last['time']})?"):
                print("  Cancelled.")
                return
        entry = self.fm.undo_last()
        print(f"  Undone: {entry['action']} ({len(entry['steps'])} file(s) restored).")

    def history(self):
        entries = self.fm.history()
        if not entries:
            print("  No operations recorded yet.")
        for i, e in enumerate(reversed(entries), 1):
            print(f"  {i}. {e['time']}  {e['action']}  ({len(e['steps'])} file(s))"
                  + ("   <- undo target" if i == 1 else ""))

    def empty_trash(self):
        count, size = self.fm.trash_contents()
        if count == 0:
            print("  Trash is empty.")
            return
        print(f"  Trash holds {count} file(s), {human_size(size)}. This CANNOT be undone.")
        if ask("Type DELETE to confirm") != "DELETE":
            print("  Cancelled.")
            return
        self.fm.purge_trash()
        print(f"  Permanently deleted {count} file(s).")

    # ---------------------------------------------------------- reports
    def save_report(self):
        path = ask("Report file [folder_report.txt]") or "folder_report.txt"
        reports.save_text_report(self.scan(), path)
        print(f"  Report written to {path}")

    def export_csv(self):
        path = ask("CSV file [file_list.csv]") or "file_list.csv"
        reports.export_inventory_csv(self.scan(), path)
        print(f"  File list exported to {path}")
