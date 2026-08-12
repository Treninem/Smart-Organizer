class Scanner:
    """Safe filesystem scanner.

    First version only analyzes structure and does not move or delete files.
    """

    def status(self):
        return "Scanner ready: analysis mode"

    def scan(self, path):
        return {
            "path": str(path),
            "mode": "analysis_only"
        }
