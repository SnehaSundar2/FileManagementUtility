"""Custom exception hierarchy.

Every deliberate error derives from FileManagerError so the CLI can catch
a single base class and show a friendly message instead of a traceback.
"""


class FileManagerError(Exception):
    """Base class for all utility errors."""


class ValidationError(FileManagerError):
    """Raised when user input fails validation."""


class UnsafePathError(FileManagerError):
    """Raised when a path would escape the managed root folder."""


class ConflictError(FileManagerError):
    """Raised when an operation would overwrite or collide with a file."""


class OperationError(FileManagerError):
    """Raised when a file operation fails (and has been rolled back)."""


class NothingToDoError(FileManagerError):
    """Raised when an operation has no files to act on."""


class UndoError(FileManagerError):
    """Raised when the last operation cannot be undone safely."""
