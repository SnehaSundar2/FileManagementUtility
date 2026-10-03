import os
import time
from datetime import datetime

from filemanager import analysis
from filemanager.analysis import human_size
from filemanager.categories import category_for
from filemanager.scanner import JOURNAL_FILE, TRASH_DIR, scan
from tests.helpers import TempFolderTest


class TestScanner(TempFolderTest):
    def test_recursive_and_flat(self):
        self.make("a.txt")
        self.make("sub/b.jpg")
        self.make("sub/deeper/c.py")
        self.assertEqual(len(scan(self.root).files), 3)
        self.assertEqual(len(scan(self.root).folders), 2)
        self.assertEqual([f.name for f in scan(self.root, recursive=False).files], ["a.txt"])

    def test_internal_items_skipped(self):
        self.make("a.txt")
        self.make(f"{TRASH_DIR}/old/b.txt")
        self.make(JOURNAL_FILE, b"[]")
        self.assertEqual([f.name for f in scan(self.root).files], ["a.txt"])

    def test_file_info(self):
        f = scan(self.root if self.make("Photo.JPG", b"12345") else None).files[0]
        self.assertEqual((f.size, f.extension, f.category), (5, ".jpg", "Images"))


class TestAnalysis(TempFolderTest):
    def setUp(self):
        super().setUp()
        self.make("big.mp4", b"v" * 5000)
        self.make("photo.jpg", b"same-content" * 10)
        self.make("photo copy.jpg", b"same-content" * 10)
        self.make("sub/photo.jpg", b"same-content" * 10)
        self.make("other.jpg", b"diff-content" * 10)   # same size, different content
        self.make("empty.txt", b"")
        self.make("empty2.log", b"")
        self.make("report_2025.pdf", b"p" * 300)
        (self.root / "blank" / "nested").mkdir(parents=True)
        old = time.mktime(datetime(2024, 1, 15).timetuple())
        os.utime(self.root / "report_2025.pdf", (old, old))
        self.result = scan(self.root)

    def test_categories_and_human_size(self):
        self.assertEqual(category_for(".PDF"), "Documents")
        self.assertEqual(category_for(".xyz"), "Other")
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(1536), "1.5 KB")
        self.assertEqual(human_size(5 * 1024 ** 3), "5.0 GB")

    def test_summary(self):
        s = analysis.summary(self.result)
        self.assertEqual(s["files"], 8)
        self.assertEqual(s["by_category"]["Images"]["count"], 4)
        self.assertEqual(s["oldest"].name, "report_2025.pdf")
        self.assertNotIn("Audio", s["by_category"])  # empty categories hidden

    def test_search_filters(self):
        files = self.result.files
        self.assertEqual(len(analysis.search(files, "PHOTO*")), 3)  # case-insensitive
        self.assertEqual(len(analysis.search(files, extensions={".jpg"})), 4)
        self.assertEqual([f.name for f in analysis.search(files, min_size=1000)], ["big.mp4"])
        self.assertEqual(len(analysis.search(files, max_size=0)), 2)
        self.assertEqual([f.name for f in analysis.search(files, modified_before=datetime(2024, 12, 31))],
                         ["report_2025.pdf"])

    def test_largest_and_sort(self):
        self.assertEqual(analysis.largest(self.result.files, 1)[0].name, "big.mp4")
        names = [f.name for f in analysis.sort_files(self.result.files, "name")]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_duplicates(self):
        groups, errors = analysis.find_duplicates(self.result.files)
        self.assertEqual(errors, [])
        self.assertEqual(len(groups), 1)  # other.jpg same size but different content; empties ignored
        rels = [f.relative_to(self.root) for f in groups[0]]
        self.assertEqual(rels[0], "photo.jpg")  # original kept, not the 'copy' or nested one
        self.assertEqual(set(rels[1:]), {"photo copy.jpg", "sub/photo.jpg"})
        self.assertEqual(analysis.wasted_space(groups), 240)

    def test_empty_items(self):
        self.assertEqual({f.name for f in analysis.empty_files(self.result.files)}, {"empty.txt", "empty2.log"})
        empty = [p.relative_to(self.root).as_posix() for p in analysis.empty_folders(self.result)]
        self.assertEqual(empty, ["blank/nested", "blank"])  # deepest first; 'sub' has a file
