"""
report/test_report.py

Run:  python3 -m unittest report.test_report -v   (run from the repo root)

Part 1 (offline) always runs - no model needed.
Part 2 (live) runs only if your local model server is up.
"""

import unittest

from report.generate import (
    ask_llm_once,
    fallback_report,
    find_banned_words,
    generate_report,
    is_llm_up,
    validate_report,
)
from report.sample_payloads import ALL_SAMPLES, FULL, WITH_NULLS

BANNED_EXAMPLES = ["scammer", "fraudster", "crook", "criminal", "thief", "swindler"]


class TestOffline(unittest.TestCase):
    def test_detects_banned_words(self):
        for word in BANNED_EXAMPLES:
            text = f"This seller is a {word}. Risk indicators found."
            self.assertTrue(find_banned_words(text), f"missed: {word}")

    def test_detects_plural_and_capitals(self):
        self.assertTrue(find_banned_words("SCAMMERS often copy photos."))
        self.assertTrue(find_banned_words("This is a Fraudster."))

    def test_safe_phrases_are_allowed(self):
        text = "Risk indicators found. This does not prove fraud. Scam-risk score is high."
        self.assertEqual(find_banned_words(text), [])

    def test_validator_rejects_scammer_report(self):
        good = fallback_report(FULL)
        bad = good.replace("Risk indicators found.", "This seller is a scammer.", 1)
        problems = validate_report(bad, FULL)
        self.assertTrue(any("banned" in p for p in problems))

    def test_validator_rejects_invented_number(self):
        text = fallback_report(FULL) + " Also 9999 people complained."
        problems = validate_report(text, FULL)
        self.assertTrue(any("numbers not in the data" in p for p in problems))

    def test_fallback_passes_all_rules_for_every_sample(self):
        for payload in ALL_SAMPLES:
            text = fallback_report(payload)
            self.assertEqual(validate_report(text, payload), [])
            self.assertEqual(find_banned_words(text), [])

    def test_null_data_is_reported_as_unavailable(self):
        text = fallback_report(WITH_NULLS)
        self.assertIn("unavailable", text.lower())


@unittest.skipUnless(is_llm_up(), "Local LLM server is not running - skipping live tests")
class TestLiveLLM(unittest.TestCase):
    def test_raw_model_never_uses_banned_words(self):
        for payload in ALL_SAMPLES:
            raw = ask_llm_once(payload)
            self.assertEqual(find_banned_words(raw), [], f"Model said: {raw}")

    def test_final_report_passes_every_rule(self):
        for payload in ALL_SAMPLES:
            result = generate_report(payload)
            self.assertEqual(validate_report(result["text"], payload), [])
            self.assertEqual(find_banned_words(result["text"]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
