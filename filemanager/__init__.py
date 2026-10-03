"""File Management Utility.

A modular command-line tool that scans a folder, analyses its contents
(sizes, types, duplicates, empty items), and safely organises, renames,
copies and deletes files with preview, trash and undo support.
"""

import logging

__version__ = "1.0.0"

# Stay silent unless the application (main.py) configures logging.
logging.getLogger("filemanager").addHandler(logging.NullHandler())
