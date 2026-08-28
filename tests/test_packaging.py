"""Packaging hygiene: this repo must never carry secrets, weights,
personal absolute paths, or copies of external projects.
"""

import os
import re
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_TEXT_EXT = (".py", ".sh", ".md", ".json", ".example.json")

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)api[_-]key['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{8,}"),
)


def _repo_files():
    for dirpath, dirnames, filenames in os.walk(_ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if name.endswith(_TEXT_EXT) or "." not in name:
                yield path


class TestPackaging(unittest.TestCase):
    def test_no_secrets(self):
        for path in _repo_files():
            with open(path, errors="replace") as f:
                content = f.read()
            for pattern in _SECRET_PATTERNS:
                match = pattern.search(content)
                self.assertIsNone(
                    match,
                    f"{path} matches secret pattern {pattern.pattern!r}")

    def test_no_weights_or_blobs(self):
        for path in _repo_files():
            self.assertFalse(
                path.endswith((".safetensors", ".gguf", ".bin", ".pth")),
                f"weight-like file committed: {path}")

    def test_no_personal_absolute_paths(self):
        # /Users/<name> style paths must never be hardcoded; ${HOME} and
        # path-derived values are fine.
        pattern = re.compile(r"/Users/[A-Za-z0-9_\-]+/")
        for path in _repo_files():
            with open(path, errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if "${HOME}" in line or "$HOME" in line:
                        continue
                    match = pattern.search(line)
                    self.assertIsNone(
                        match,
                        f"{path}:{lineno} hardcodes a personal path: "
                        f"{match.group(0) if match else line.strip()[:60]}")

    def test_provenance_headers_present(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for tool in ("generate_config.py", "import_check.py"):
            with open(os.path.join(root, "tools", tool)) as f:
                head = f.read(600)
            self.assertIn("Provenance", head, tool)

    def test_no_opencode_source_vendored(self):
        # OpenCode is an external dependency; only its config namespace may
        # appear, never code. (Scan shipped code, not the tests that
        # assert this.)
        for path in _repo_files():
            if os.path.dirname(path) == os.path.join(_ROOT, "tests"):
                continue
            if path.endswith(".md") or path.endswith(".example.json"):
                continue
            with open(path, errors="replace") as f:
                content = f.read()
            self.assertNotIn("ai.opencode.desktop", content,
                             f"{path} references OpenCode internals")


if __name__ == "__main__":
    unittest.main()
