# Project Report: File Management Utility

**Program:** Virtual Internship – Python Development
**Project:** File Management Utility
**Submitted by:** _[Your Name]_
**Date:** _[Submission Date]_

---

## 1. Introduction

Folders like *Downloads* and *Desktop* quickly fill up with a mix of photos, documents,
installers and duplicate copies. Cleaning them up by hand is slow, and bulk tools can be risky:
one wrong rename or delete can destroy files. This project is a Python command-line utility
that analyses a folder and cleans it up **safely**. Every change is previewed, checked for
conflicts, applied all-or-nothing, and can be undone.

## 2. Objectives

1. Build a working file management tool from clearly separated Python modules.
2. Validate every input: folder paths, file names, sizes, dates and patterns.
3. Process file data into useful information: categories, sizes, duplicates, empty items.
4. Handle errors (permissions, conflicts, failures part-way) without losing or damaging files.
5. Document the workflow and verify the behaviour with automated tests.

## 3. Tools and technologies

| Item | Used |
|---|---|
| Language | Python 3 (tested on 3.13) |
| Libraries | Standard library only: `pathlib`, `os`, `shutil`, `hashlib`, `fnmatch`, `json`, `csv`, `tempfile`, `dataclasses`, `logging`, `argparse`, `unittest` |
| Testing | `unittest`, `unittest.mock` (to simulate failures) |

## 4. System design

### 4.1 Modules

| Module | Responsibility |
|---|---|
| `main.py` | Starts the app; demo creation; report-only mode |
| `cli.py` | Menu, prompts, previews and confirmations |
| `validators.py` | Validates names, paths, sizes, dates, extensions, patterns |
| `categories.py` | Maps extensions to categories (Images, Documents, ...) |
| `scanner.py` | Walks the folder and builds `FileInfo` records |
| `analysis.py` | Summary, search, sorting, duplicates, empty items |
| `operations.py` | Planning, conflict checks, execution with rollback, journal, undo, trash |
| `reports.py` | Text report and CSV inventory |
| `exceptions.py` | Custom error types |

### 4.2 Safe-operation design

Each change follows **plan → preview → confirm → execute → record**:

1. A `plan_*` function builds a list of `Step(src, dst)` without touching the disk, validating
   every new name and checking for conflicts.
2. The CLI shows every `old -> new` line and asks for confirmation.
3. `execute()` applies the steps. If one fails, the completed steps are reversed in reverse order.
4. The operation is saved to a JSON journal so `undo_last()` can reverse it later.

**Chained renames.** Renumbering `file_001 → file_002` and `file_002 → file_003` would overwrite
a file if done naively. The utility detects this and moves files through temporary names first.

**Trash instead of delete.** "Delete" moves files to `.fmu_trash/<timestamp>/`, keeping their
folder structure. Only "Empty trash", confirmed by typing `DELETE`, removes anything for good.

## 5. Implementation highlights

**Validation.** `validate_filename` rejects `< > : " / \ | ? *`, control characters, names
ending in a space or dot, `.`/`..`, and Windows reserved names such as `CON` and `nul.txt`.
`validate_inside` resolves a path and blocks anything outside the managed folder, such as
`../secret.txt`. `parse_size` turns `1.5MB` into 1,572,864 bytes.

**Duplicate detection.** Files are grouped by size, and only groups with two or more files are
hashed with SHA-256 in 64 KB chunks. This avoids reading most files at all. In each group the
file to keep is the one in the shallowest folder with the shortest name, so `photo.jpg` is kept
and `photo copy.jpg` is marked as extra.

**Error handling.** Unreadable folders are recorded and skipped during the scan. A simulated
"Access is denied" on the second of three moves is fully rolled back (verified by a test).
Undo refuses to run if a file has been changed or re-created since the operation, rather than
overwrite it.

## 6. Testing

42 automated tests were written and **all pass**. Each runs in a temporary folder.

| # | Test case | Expected | Result |
|---|---|---|---|
| 1 | Names `CON`, `what?.txt`, `ends.`, `a/b.txt` | ValidationError | Pass |
| 2 | Path `../outside.txt` | UnsafePathError | Pass |
| 3 | Sizes `10kb`, `1.5 MB`; invalid `ten`, `5 PB` | Bytes / ValidationError | Pass |
| 4 | Two files with the same content, one same-size but different | One duplicate group only | Pass |
| 5 | Organise with an existing `Images/a.jpg` | New file becomes `a (1).jpg`, existing untouched | Pass |
| 6 | Rename onto an existing name / two files to one name | ConflictError, nothing changed | Pass |
| 7 | Chained renumber 001→002, 002→003 | Contents preserved, undo restores | Pass |
| 8 | Case-only rename `C.TXT → c.txt` on Windows | Succeeds | Pass |
| 9 | Failure on 2nd of 3 moves | All rolled back, no journal entry | Pass |
| 10 | Undo after a moved file was deleted | UndoError, nothing changed | Pass |
| 11 | Trash duplicates → undo → trash again → empty trash | Restored, then purged; history cleared | Pass |
| 12 | Corrupt journal file | Ignored safely, new operations recorded | Pass |
| 13 | CLI: cancel at preview | "Nothing was changed" | Pass |
| 14 | CLI: empty trash without typing DELETE | Cancelled | Pass |

## 7. Sample output (demo folder)

```
  OVERVIEW
  Files: 18   Folders: 5   Total size: 274.6 KB   Average file: 15.3 KB

  DUPLICATE FILES
  3 group(s); 35.2 KB could be freed.
  Group 1 (23.4 KB each):
    keep   holiday photo.jpg
    extra  holiday photo copy.jpg

  Preview - 2 file(s) will be renamed:
    notes.txt  ->  note_001.txt
    todo.txt  ->  note_002.txt
  Go ahead? [y/N]: y
  Done: 2 file(s) renamed. Use option 12 to undo.
```

## 8. Challenges and solutions

| Challenge | Solution |
|---|---|
| Bulk operations could leave a folder half-changed after an error | Transactional `execute()` with rollback |
| Chained renames would overwrite files | Two-phase move through temporary names |
| Users fear deleting the wrong thing | Trash folder + undo + typed confirmation to purge |
| Hashing every file is slow | Group by size first; hash only possible duplicates, in chunks |
| Windows treats `A.txt` and `a.txt` as the same file | `samefile` checks so case-only renames work and aren't seen as conflicts |
| Testing failures without breaking real files | Temporary folders and `unittest.mock` to simulate "Access is denied" |

## 9. Future enhancements

- Graphical interface (Tkinter) with drag-and-drop
- Scheduled automatic organising of the Downloads folder
- Rename by date taken (photo EXIF data)
- Multi-level undo (undo several steps back)
- Compress old files into ZIP archives

## 10. Conclusion

The File Management Utility meets all project objectives. It is organised into focused
modules, validates every input, turns raw file data into useful insights, and handles errors
so that no operation can leave files damaged or half-changed. The workflow is documented and
the behaviour is verified by 42 passing automated tests.

## 11. How to run

```bash
cd FileManagementUtility
python main.py --make-demo demo_folder
python main.py --root demo_folder
python -m unittest discover -s tests -t . -v
```
