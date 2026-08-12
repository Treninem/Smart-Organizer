from pathlib import Path


class FileSystemAnalyzer:
    def build_tree(self, path, depth=3):
        root = Path(path)
        return self._scan(root, depth)

    def _scan(self, path, depth):
        result = {
            "name": path.name,
            "path": str(path),
            "type": "folder" if path.is_dir() else "file"
        }

        if path.is_dir() and depth > 0:
            result["children"] = []
            try:
                for item in path.iterdir():
                    result["children"].append(self._scan(item, depth - 1))
            except PermissionError:
                result["children"] = []

        return result
