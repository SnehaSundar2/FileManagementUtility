"""Creates a messy sample folder to try the utility on."""

import os
import time
from pathlib import Path

from .exceptions import ValidationError

DEMO_FILES = {
    "holiday photo.jpg": b"\xff\xd8\xff" + b"JPEGDATA" * 3000,
    "holiday photo copy.jpg": b"\xff\xd8\xff" + b"JPEGDATA" * 3000,     # duplicate
    "screenshot.PNG": b"\x89PNG" + b"PIXELS" * 1500,
    "Resume.pdf": b"%PDF-1.7 " + b"resume " * 2000,
    "notes.txt": b"Meeting notes\n- finish internship project\n",
    "todo.txt": b"",                                                    # empty file
    "marks.csv": b"roll_no,name,maths\n1,Asha,95\n2,Rahul,72\n",
    "budget.xlsx": b"PK" + b"sheet" * 1200,
    "slides.pptx": b"PK" + b"slide" * 4000,
    "song.mp3": b"ID3" + b"audio" * 9000,
    "clip.mp4": b"\x00\x00\x00\x18ftyp" + b"video" * 20000,
    "backup.zip": b"PK\x03\x04" + b"zipped" * 2500,
    "script.py": b"print('hello world')\n",
    "README": b"No extension here.\n",
    "projects/report_final.docx": b"PK" + b"docx" * 3000,
    "projects/report_final (old).docx": b"PK" + b"docx" * 3000,         # duplicate
    "projects/code/app.js": b"console.log('hi');\n",
    "projects/code/notes.txt": b"Meeting notes\n- finish internship project\n",  # duplicate
}
EMPTY_DIRS = ["old stuff", "projects/archive/2024"]


def create_demo(folder):
    """Create the demo folder. Refuses to write into a non-empty folder."""
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise ValidationError(f"{folder} already exists and is not empty; choose a new folder name.")
    now = time.time()
    for i, (rel, content) in enumerate(DEMO_FILES.items()):
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        age = (i * 37 % 400) * 86400  # spread modified dates over ~13 months
        os.utime(path, (now - age, now - age))
    for rel in EMPTY_DIRS:
        (folder / rel).mkdir(parents=True, exist_ok=True)
    return folder.resolve()
