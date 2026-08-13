import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.duplicates as duplicates


class DuplicatePerformanceTests(unittest.TestCase):
    def test_quick_signature_filters_same_size_nonmatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.bin"
            b = root / "b.bin"
            c = root / "c.bin"
            a.write_bytes(b"A" * 200_000)
            b.write_bytes(b"A" * 200_000)
            c.write_bytes(b"B" * 200_000)
            records = []
            for path in (a, b, c):
                stat = path.stat()
                records.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )

            original = duplicates.sha256_file
            calls = []

            def tracked(path, chunk_size=1024 * 1024):
                calls.append(str(path))
                return original(path, chunk_size)

            with patch.object(duplicates, "sha256_file", side_effect=tracked):
                groups = duplicates.exact_duplicate_groups(records)

            self.assertEqual(len(groups), 1)
            self.assertEqual(len(calls), 2)
            self.assertNotIn(str(c), calls)


if __name__ == "__main__":
    unittest.main()
