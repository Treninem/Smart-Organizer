import re


class VersionManager:
    PATTERNS = [
        r"v\d+\.\d+(?:\.\d+)?",
        r"Version[_ -]?\d+\.\d+"
    ]

    def detect(self, name):
        found = []
        for pattern in self.PATTERNS:
            found.extend(re.findall(pattern, name, re.IGNORECASE))
        return found

    def classify(self, version):
        if not version:
            return "unknown"
        if "test" in version.lower():
            return "test"
        return "release"
