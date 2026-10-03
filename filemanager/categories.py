"""Maps file extensions to human-friendly categories."""

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".json", ".xml",
             ".sql", ".sh", ".ipynb", ".yaml", ".yml"},
    "Executables": {".exe", ".msi", ".bat", ".apk", ".dmg"},
}
OTHER = "Other"

_LOOKUP = {ext: name for name, exts in CATEGORIES.items() for ext in exts}


def category_for(extension):
    return _LOOKUP.get(extension.lower(), OTHER)


def all_categories():
    return [*CATEGORIES, OTHER]
