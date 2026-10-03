# File Management Utility

A menu-driven Python tool that scans a folder, explains what's in it (sizes, types, duplicates,
empty items), and **safely** cleans it up: organise by type, bulk rename, copy, and move to
trash. Every change can be previewed first and undone afterwards.

Built as a virtual internship project to demonstrate **Python modules, input validation,
data processing and error handling**. It uses only the Python standard library, so there is
nothing to install.

---

## 1. Features

| Area | What it does |
|---|---|
| **Explore** | Folder summary by category, list/sort files, search, largest files |
| **Search** | Name wildcard (`*.txt`, `report*`), extensions, size range (`10KB`–`5MB`), modified-date range |
| **Duplicates** | Finds files with identical content (SHA-256), shows space that could be freed |
| **Empty items** | Lists empty files and folders that have nothing inside them |
| **Organise** | Moves loose files into `Images/`, `Documents/`, `Video/` ... folders |
| **Bulk rename** | Prefix, suffix, find & replace, numbered sequence (`photo_001.jpg`), lower-case |
| **Copy** | Copies matching files into a folder (e.g. a backup) |
| **Trash** | "Delete" moves files to a hidden trash folder; duplicates can be trashed in one step |
| **Undo** | Reverses the last operation; full operation history kept |
| **Reports** | Full text report and CSV file inventory |

### Safety features

- **Preview before every change**, with an explicit yes/no confirmation.
- **Conflict detection**: a rename that would overwrite a file is refused before anything happens.
- **Automatic numbering** when a file with the same name already exists (`a (1).jpg`).
- **All-or-nothing**: if any file fails mid-operation, the files already changed are put back.
- **Undo** of the last operation, refused if files were changed since (so undo can't overwrite anything).
- **Nothing is permanently deleted** except by "Empty trash", which needs you to type `DELETE`.
- **Stays inside the chosen folder**: paths that escape it (`../`) are blocked.

---

## 2. Project structure

```
FileManagementUtility/
├── main.py                   # Entry point: options, logging, demo, report-only mode
├── filemanager/              # The application package
│   ├── __init__.py
│   ├── exceptions.py         # Custom exception hierarchy
│   ├── validators.py         # Input validation (names, paths, sizes, dates, patterns)
│   ├── categories.py         # Extension → category mapping
│   ├── scanner.py            # Walks the folder, collects FileInfo records
│   ├── analysis.py           # Summary, search, sorting, duplicates, empty items
│   ├── operations.py         # Plan → preview → execute, rollback, journal, undo, trash
│   ├── reports.py            # Text report and CSV inventory
│   ├── demo.py               # Creates a messy sample folder to practise on
│   └── cli.py                # Interactive menu
├── tests/                    # 42 automated tests
└── docs/
    └── PROJECT_REPORT.md     # Internship submission report
```

---

## 3. How to run

Requires **Python 3.8 or newer**.

```bash
cd FileManagementUtility
python main.py --make-demo demo_folder     # create a sample folder (18 files, duplicates, empties)
python main.py --root demo_folder          # open the menu on it
```

Report without the menu:

```bash
python main.py --root demo_folder --report folder_report.txt --csv file_list.csv
```

| Option | Purpose |
|---|---|
| `--root FOLDER` | Folder to manage (asked for if not given) |
| `--make-demo FOLDER` | Create a sample folder to practise on (must be new or empty) |
| `--report PATH` | Print and save a full folder report, then exit |
| `--csv PATH` | With `--report`, also export the file list as CSV |

> Try it on the demo folder first. On your own folders, start with the explore and report
> options. They only read files and never change anything.

---

## 4. Workflow

```
  choose folder ──► validators.validate_directory  (must exist, must be a folder)
        │
        ▼
  scanner.scan ──► FileInfo list  (unreadable items recorded, scan continues)
        │
        ├──► analysis / reports ──► summary, search, duplicates, report, CSV   (read-only)
        │
        ▼
  operations.plan_*            builds the list of changes; validates names;
        │                      detects conflicts → ConflictError, nothing touched
        ▼
  cli.preview + confirm        user sees every "old -> new" and answers y/N
        │
        ▼
  operations.execute           applies changes; on any failure rolls back → OperationError
        │
        ▼
  journal (.fmu_journal.json)  records the operation  ──►  undo_last() reverses it
```

### Typical session on the demo folder

1. **Folder summary** (1) and **Save folder report** (15): see what's there.
2. **Find duplicates** (5): 3 groups found. **Move duplicates to trash** (10) keeps the original
   of each.
3. **Organise files by type** (7): preview, confirm, and loose files move into category folders.
4. Changed your mind? **Undo last operation** (12).
5. **Bulk rename** (8), e.g. sequence mode `photo` gives `photo_001.jpg`, `photo_002.jpg`...
6. **Operation history** (13) to review, then **Empty trash** (14) when sure.

### Input rules

| Input | Rule | Examples |
|---|---|---|
| Folder | Must exist and be a folder; quotes allowed | `D:\Downloads`, `"C:\My Files"` |
| File/folder name | No `< > : " / \ | ? *`, not `CON`/`NUL`/..., no trailing space or dot, ≤ 255 chars | `backup 2026` |
| Name pattern | Wildcards `*` and `?`, no folder separators | `*.txt`, `report_??.pdf` |
| Extensions | Comma/space separated, dot optional | `jpg, png .pdf` |
| Size | Number + optional unit B/KB/MB/GB/TB | `500`, `20KB`, `1.5MB` |
| Date | `YYYY-MM-DD` | `2026-01-31` |

---

## 5. Key concepts demonstrated

**Python modules.** Reading (`scanner`), thinking (`analysis`), changing (`operations`) and
talking to the user (`cli`) are separate modules. Everything that changes files goes through a
single `execute()` path, which is what makes preview, rollback and undo possible.

**Input validation.** File names are checked against Windows, macOS and Linux rules, including
reserved names like `CON` and `NUL`. Sizes, dates, extensions and wildcard patterns are parsed
and checked. Every path is resolved and confirmed to be inside the managed folder.

**Data processing.** Files are grouped by category and extension. Duplicate detection groups
files by size first (cheap) and hashes only the candidates with SHA-256, reading in 64 KB
chunks, so large files are handled efficiently. Empty-folder detection works bottom-up, and
searches combine several filters.

**Error handling**
- Custom exceptions: `FileManagerError` → `ValidationError`, `UnsafePathError`, `ConflictError`,
  `OperationError`, `NothingToDoError`, `UndoError`.
- Unreadable files and folders are skipped and reported; the scan carries on.
- Operations are transactional: a failure part-way (e.g. "Access is denied") rolls back.
- A corrupted journal file is ignored safely, and journal writes are atomic.
- The menu catches all expected errors and logs unexpected ones to `filemanager.log`.

---

## 6. Testing

```bash
cd FileManagementUtility
python -m unittest discover -s tests -t . -v
```

Result: **42 tests, all passing.** Every test runs in its own temporary folder, so your real
files are never touched.

| Test file | Tests | Covers |
|---|---|---|
| `test_validators.py` | 10 | File names, reserved names, sizes, dates, extensions, patterns, folder checks, `../` traversal |
| `test_scan_analysis.py` | 9 | Recursive/flat scans, internal files skipped, summary, search filters, duplicates, empty items |
| `test_operations.py` | 16 | Organise, all rename modes, conflicts, chained renames, copy, trash, undo, purge, rollback after a simulated failure, corrupt journal |
| `test_reports_cli.py` | 7 | Demo folder, text report, CSV, end-to-end menu sessions, confirmations, error messages |
