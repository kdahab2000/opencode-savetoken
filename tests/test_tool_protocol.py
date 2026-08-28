"""Tool-protocol mirror test: the Gemma parser suite from the sibling
SaveToken-GemmaMLX kit runs here unchanged, so drift between the
integration repo's assumptions and the actual protocol is caught.

If the sibling repo is absent the test is skipped with a notice (the kit
repo is the canonical home of these tests).
"""

import importlib.util
import os
import sys
import unittest

_KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "SaveToken-GemmaMLX")


@unittest.skipUnless(os.path.isdir(_KIT),
                     "sibling SaveToken-GemmaMLX kit not present")
class TestGemmaParserMirror(unittest.TestCase):
    """Runs the kit's own suite in-process; any failure means the wire
    protocol assumptions of this repo and the kit disagree."""

    def test_kit_parser_suite_passes(self):
        suite_path = os.path.join(_KIT, "tests", "test_gemma_kit.py")
        spec = importlib.util.spec_from_file_location("kit_tests",
                                                      suite_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.failures + result.errors, [],
                         f"kit mirror failures: "
                         f"{[f[1] for f in result.failures + result.errors]}")


class TestProtocolAssumptions(unittest.TestCase):
    """The wire facts this repo's docs and scripts rely on."""

    def test_gemma_syntax_documented_in_models_doc(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "docs", "models.md")) as f:
            doc = f.read()
        self.assertIn("<|tool_call>call:NAME{key:value}<tool_call|>", doc)
        self.assertIn("drop_tools_on_continuation", doc)
        # the fixed list-content bug must stay documented
        self.assertIn("can only concatenate str", doc)

    def test_smoke_fixture_uses_loopback_only(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        smoke = open(os.path.join(root, "tools", "smoke.sh")).read()
        self.assertIn("http://127.0.0.1", smoke)
        self.assertNotIn("https://", smoke.replace(
            "https://opencode.ai", ""))  # only the schema namespace


if __name__ == "__main__":
    unittest.main()
