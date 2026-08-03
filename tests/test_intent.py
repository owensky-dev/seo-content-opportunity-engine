import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_content_backlog.py"
SPEC = importlib.util.spec_from_file_location("build_content_backlog", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class IntentClassificationTest(unittest.TestCase):
    def test_reusable_terms_are_not_global_stopwords(self):
        self.assertEqual(MODULE.classify_intent("best bath sink", "Example"), "comparison")

    def test_site_name_still_drives_brand_intent(self):
        self.assertEqual(MODULE.classify_intent("ExampleBath shower door", "ExampleBath"), "brand")


if __name__ == "__main__":
    unittest.main()
