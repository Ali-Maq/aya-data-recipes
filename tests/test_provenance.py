"""Bind the delivered component to the controller's real acceptance receipt."""

import hashlib
import json
import unittest
from pathlib import Path


class Provenance(unittest.TestCase):
    def test_delivery_matches_verified_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / "verification.json").read_text())
        contract_bytes = (root / "specs/export-recipe.json").read_bytes()
        contract = json.loads(contract_bytes)
        self.assertEqual(receipt["module_sha256"], hashlib.sha256((root / "recipe.py").read_bytes()).hexdigest())
        self.assertEqual(receipt["contract_sha256"], hashlib.sha256(contract_bytes).hexdigest())
        self.assertEqual(receipt["reference_sha256"], contract["reference"]["library_sha256"])
        for split in ["development", "holdout"]:
            self.assertGreater(receipt[split]["total"], 0)
            self.assertEqual(receipt[split]["passed"], receipt[split]["total"])
            self.assertEqual(receipt[split]["source_sha256"], receipt["module_sha256"])
        self.assertEqual(receipt["inference"]["provider"], "Crusoe")
        self.assertTrue(receipt["inference"]["response_id"])
        records = receipt["reference_evidence"]
        self.assertTrue(any(record["operation"] == "procedure_pseudo_code" and record["raw_result"]["value"] for record in records))
        sessions = [session for audit in receipt["native_agents"] for session in audit["sessions"]]
        self.assertTrue(any("mcp__rea__procedure_pseudo_code" in session["tools"] for session in sessions))
        self.assertTrue(any(session["parent_session_id"] for session in sessions))


if __name__ == "__main__":
    unittest.main()
