import unittest
from pathlib import Path
import json
from datetime import date
from adbe_review_model import dcf,period_values,build
ROOT=Path("investment-radar/v2/data")
L=json.loads((ROOT/"adbe-reviewed-evidence.json").read_text())
class TestAdobe(unittest.TestCase):
 def test_cash_ties(self):
  t=period_values(L)
  self.assertEqual(t["cfo"],10806)
  self.assertEqual(t["capex"],214)
  self.assertEqual(t["reportedFCFE"],10835)
  self.assertEqual(t["economicFCFEAfterSBCAndAcquisitions"],7204)
 def test_dcf_monotonic_and_terminal_guard(self):
  args=(25970,.35,.225,.08,.30)
  self.assertGreater(dcf(*args,.09,.025,.20,1243.4,395)["perShareUSD"],dcf(*args,.11,.025,.20,1243.4,395)["perShareUSD"])
  with self.assertRaises(ValueError):dcf(*args,.025,.025,.20,1243.4,395)
 def test_missing_source_disables_threshold(self):
  r=build(L,{"companies":[],"retrievedAt":"2026-11-28"},{"companies":[]},date(2026,11,28))
  self.assertIsNone(r["reviewThresholdUSD"])
  self.assertFalse(r["decisionReady"])
 def test_stale_source_disables_threshold(self):
  r=build(L,{"companies":[],"retrievedAt":"2026-10-25"},{"companies":[]},date(2026,11,28))
  self.assertIn("SEC_REFRESH_STALE",r["blockingIssues"])
if __name__=="__main__":unittest.main()
