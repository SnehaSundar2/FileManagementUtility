"""Report generation: formatted tables, folder report and CSV inventory."""

import csv
from datetime import datetime
from pathlib import Path

from . import analysis
from .analysis import human_size
from .exceptions import OperationError


def format_table(rows, columns):
    if not rows:
        return "  Nothing to show."
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    lines = ["  " + "  ".join(c.upper().ljust(widths[c]) for c in columns),
             "  " + "  ".join("-" * widths[c] for c in columns)]
    for r in rows:
        lines.append("  " + "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))
    return "\n".join(lines)


def file_rows(files, root):
    return [{"file": f.relative_to(root), "type": f.category, "size": human_size(f.size),
             "modified": f.modified.strftime("%Y-%m-%d %H:%M")} for f in files]


FILE_COLUMNS = ["file", "type", "size", "modified"]


def build_text_report(scan_result, top_n=10):
    root = scan_result.root
    s = analysis.summary(scan_result)
    groups, dup_errors = analysis.find_duplicates(scan_result.files)
    out = [
        "=" * 72,
        "  FOLDER REPORT",
        f"  Folder:    {root}",
        f"  Generated: {datetime.now():%Y-%m-%d %H:%M}",
        "=" * 72,
        "",
        "  OVERVIEW",
        f"  Files: {s['files']}   Folders: {s['folders']}   Total size: {human_size(s['total_size'])}"
        f"   Average file: {human_size(s['average_size'])}",
    ]
    if s["newest"]:
        out.append(f"  Newest: {s['newest'].relative_to(root)} ({s['newest'].modified:%Y-%m-%d})"
                   f"   Oldest: {s['oldest'].relative_to(root)} ({s['oldest'].modified:%Y-%m-%d})")

    out += ["", "  BY CATEGORY"]
    total = s["total_size"] or 1
    cat_rows = [{"category": c, "files": d["count"], "size": human_size(d["size"]),
                 "share": f"{100 * d['size'] / total:.1f}%"}
                for c, d in sorted(s["by_category"].items(), key=lambda kv: -kv[1]["size"])]
    out.append(format_table(cat_rows, ["category", "files", "size", "share"]))

    out += ["", "  BY EXTENSION"]
    ext_rows = [{"extension": e, "files": d["count"], "size": human_size(d["size"])}
                for e, d in list(s["by_extension"].items())[:top_n]]
    out.append(format_table(ext_rows, ["extension", "files", "size"]))

    out += ["", f"  LARGEST {top_n} FILES",
            format_table(file_rows(analysis.largest(scan_result.files, top_n), root), FILE_COLUMNS)]

    out += ["", "  DUPLICATE FILES"]
    if groups:
        out.append(f"  {len(groups)} group(s); {human_size(analysis.wasted_space(groups))} could be freed.")
        for i, g in enumerate(groups, 1):
            out.append(f"  Group {i} ({human_size(g[0].size)} each):")
            for j, f in enumerate(g):
                out.append(f"    {'keep ' if j == 0 else 'extra'}  {f.relative_to(root)}")
    else:
        out.append("  No duplicates found.")

    empty_f = analysis.empty_files(scan_result.files)
    empty_d = analysis.empty_folders(scan_result)
    out += ["", "  EMPTY ITEMS",
            f"  Empty files ({len(empty_f)}): " + (", ".join(f.relative_to(root) for f in empty_f) or "none"),
            f"  Empty folders ({len(empty_d)}): "
            + (", ".join(p.relative_to(root).as_posix() for p in empty_d) or "none")]

    errors = scan_result.errors + dup_errors
    if errors:
        out += ["", f"  ITEMS THAT COULD NOT BE READ ({len(errors)})", *(f"  - {e}" for e in errors)]
    out.append("=" * 72)
    return "\n".join(out)


def _ensure_parent(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_text_report(scan_result, path):
    try:
        _ensure_parent(path).write_text(build_text_report(scan_result) + "\n", encoding="utf-8")
    except OSError as exc:
        raise OperationError(f"Could not write report: {exc.strerror or exc}") from exc
    return path


def export_inventory_csv(scan_result, path):
    root = scan_result.root
    try:
        with open(_ensure_parent(path), "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["path", "name", "extension", "category", "size_bytes", "modified"])
            for f in analysis.sort_files(scan_result.files, "name"):
                writer.writerow([f.relative_to(root), f.name, f.extension, f.category, f.size,
                                 f.modified.isoformat(timespec="seconds")])
    except OSError as exc:
        raise OperationError(f"Could not export CSV: {exc.strerror or exc}") from exc
    return path
