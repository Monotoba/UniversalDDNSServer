"""Documentation checks for evolving pre-alpha capabilities."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_required_documents(self):
        required = [
            "README.md", "LICENSE", "CHANGELOG.md",
            "docs/PROJECT_PROPOSAL.md", "docs/DESIGN_SPEC.md",
            "docs/IMPLEMENTATION_PLAN.md", "docs/dev/API.md",
            "docs/dev/PLUGINS.md", "docs/architecture/THREAT_MODEL.md",
        ]
        for relative in required:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_attribution_notices(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("BSD 2-Clause License", license_text)
        self.assertIn("Copyright (c) 2026", license_text)
        self.assertIn("Redistributions of source code", license_text)

    def test_status_is_explicit(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("pre-alpha", readme.lower())
        self.assertIn("no configured production http deployment", readme.lower())


if __name__ == "__main__":
    unittest.main()
