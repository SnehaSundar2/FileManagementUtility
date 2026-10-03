"""Input validation helpers.

Each function returns a cleaned value or raises ValidationError (or
UnsafePathError) with a message that can be shown directly to the user.
"""

import re
from datetime import datetime
from pathlib import Path

from .exceptions import UnsafePathError, ValidationError

INVALID_NAME_CHARS = set('<>:"/\\|?*')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL",
                  *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_NAME_LENGTH = 255
SIZE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)?$", re.IGNORECASE)
SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
DATE_FORMAT = "%Y-%m-%d"


def validate_non_empty(value, field):
    if value is None or not str(value).strip():
        raise ValidationError(f"{field} cannot be empty.")
    return str(value).strip()


def validate_directory(value, field="Folder"):
    """Return an absolute, resolved Path to an existing directory."""
    raw = validate_non_empty(value, field).strip('"')
    path = Path(raw).expanduser()
    if not path.exists():
        raise ValidationError(f"{field} does not exist: {raw}")
    if not path.is_dir():
        raise ValidationError(f"{field} is not a folder: {raw}")
    return path.resolve()


def validate_inside(root, path):
    """Make sure `path` resolves to somewhere inside `root` (blocks ../ tricks)."""
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise UnsafePathError(f"'{path}' is outside the managed folder {root}.") from None
    return resolved


def validate_filename(value, field="File name"):
    """Check a single file or folder name is legal on Windows, macOS and Linux.
    The name is checked exactly as given (not trimmed), since it is used as-is."""
    validate_non_empty(value, field)
    name = str(value)
    bad = sorted({c for c in name if c in INVALID_NAME_CHARS or ord(c) < 32})
    if bad:
        shown = " ".join(repr(c) for c in bad)
        raise ValidationError(f"{field} '{name}' contains invalid character(s): {shown}")
    if name in {".", ".."}:
        raise ValidationError(f"{field} cannot be '.' or '..'.")
    if name.endswith((" ", ".")):
        raise ValidationError(f"{field} cannot end with a space or a dot.")
    if name.split(".")[0].upper() in RESERVED_NAMES:
        raise ValidationError(f"'{name}' uses a name reserved by Windows.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"{field} must be at most {MAX_NAME_LENGTH} characters.")
    return name


def validate_name_fragment(value, field="Text"):
    """Text that will become part of a file name (prefix, suffix, replacement). May be empty."""
    text = "" if value is None else str(value)
    bad = sorted({c for c in text if c in INVALID_NAME_CHARS or ord(c) < 32})
    if bad:
        raise ValidationError(f"{field} contains invalid character(s): {' '.join(repr(c) for c in bad)}")
    return text


def parse_size(value, field="Size"):
    """'500', '10KB', '1.5 mb' -> bytes."""
    text = validate_non_empty(value, field)
    match = SIZE_PATTERN.match(text)
    if not match:
        raise ValidationError(f"{field} must look like 500, 20KB, 1.5MB or 2GB.")
    number, unit = match.groups()
    return int(float(number) * SIZE_UNITS[(unit or "B").upper()])


def validate_date(value, field="Date"):
    text = validate_non_empty(value, field)
    try:
        return datetime.strptime(text, DATE_FORMAT)
    except ValueError:
        raise ValidationError(f"{field} must be in YYYY-MM-DD format.") from None


def validate_extensions(value):
    """'jpg, .PNG pdf' -> {'.jpg', '.png', '.pdf'}. Blank -> empty set (means all)."""
    if value is None or not str(value).strip():
        return set()
    result = set()
    for part in re.split(r"[,\s]+", str(value).strip()):
        if not part:
            continue
        ext = part.lower() if part.startswith(".") else "." + part.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,10}", ext):
            raise ValidationError(f"'{part}' is not a valid file extension.")
        result.add(ext)
    return result


def validate_pattern(value):
    """A file-name wildcard pattern such as *.txt or report_*. Blank -> '*'."""
    text = (value or "").strip() or "*"
    if "/" in text or "\\" in text:
        raise ValidationError("Pattern must match file names only, not folders (no / or \\).")
    return text


def validate_positive_int(value, field, maximum=None):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number.") from None
    if number < 1:
        raise ValidationError(f"{field} must be at least 1.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be at most {maximum}.")
    return number


def validate_choice(value, choices, field):
    text = validate_non_empty(value, field).lower()
    if text not in choices:
        raise ValidationError(f"{field} must be one of: {', '.join(choices)}.")
    return text
