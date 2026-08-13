import unittest

from core.archive_analyzer import _parse_7zip_slt


class SevenZipParserTests(unittest.TestCase):
    def test_directories_are_not_counted_as_entries(self):
        output = """
Path = folder
Folder = +
Size = 0
Attributes = D

Path = folder/readme.txt
Folder = -
Size = 12
Attributes = A

Path = folder/sub
Folder = +
Size = 0
Attributes = D

Path = folder/sub/image.png
Folder = -
Size = 25
Attributes = A
"""
        names, total = _parse_7zip_slt(output)
        self.assertEqual(names, ["folder/readme.txt", "folder/sub/image.png"])
        self.assertEqual(total, 37)

    def test_parser_flushes_when_next_path_starts_without_blank_line(self):
        output = """Path = a.txt
Size = 2
Attributes = A
Path = b.txt
Size = 3
Attributes = A
"""
        names, total = _parse_7zip_slt(output)
        self.assertEqual(names, ["a.txt", "b.txt"])
        self.assertEqual(total, 5)


if __name__ == "__main__":
    unittest.main()
