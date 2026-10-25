import unittest
from datetime import date
from autonomous_analyst import cash_dcf,analyze,choose_growth,CONFIG
class TestAutonomous(unittest.TestCase):
 def test_cash_dcf_positive_and_discount(self):
  x=cash_dcf(100,10,.11,.06,.025)
  self.assertGreater(x,0)
  self.assertLess(cash_dcf(100,10,.14,.06,.025),x)
 def test_terminal_constraint(self):
  self.assertIsNone(cash_dcf(100,10,.02,.04,.03))
 def test_growth_not_defined_without_two_periods(self):
  self.assertEqual(choose_growth([{"incomeStatement":{"revenue":100}}],CONFIG["software"])[0],None)
 def test_block_without_documentary_bridge(self):
  h=[]
  for year in [2025,2024,2023,2022]:
   h.append({"fiscalYearEnd":f"{year}-12-31","incomeStatement":{"revenue":1000-(2025-year)*90},
    "shareCapital":{"weightedDilutedShares":100},"cashFlow":{"ownerCashProxyAfterSBC":300,"propertyCapex":50},
    "balanceSheet":{"cash":100},"sourceIndex":{"operating_cash_flow":{"accession":"ACC"}}})
  fin={"ticker":"ADBE","name":"Adobe","category":"software","fiscalHistory":h,"issues":[],
       "coverage":{"ownerCashProxy3FY":True,"dilutedSharesLatest":True}}
  src={"ticker":"ADBE","status":"review_required","sourceURL":"https://data.sec.gov/example",
       "issues":[],"interimYTD":None}
  r=analyze(fin,src,None,date(2026,10,25))
  self.assertFalse(r["decisionReady"])
  self.assertIsNone(r["approvedFairValueUSD"])
  self.assertIsNone(r["approvedEntryPriceUSD"])
  self.assertIn("NET_DEBT_DOCUMENTED",r["hardGates"])
  self.assertIsNotNone(r["sensitivity"])
  self.assertTrue(r["checks"]["SCENARIO_ORDER_VALID"])
if __name__=="__main__":unittest.main()
