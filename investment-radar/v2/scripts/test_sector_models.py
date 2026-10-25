#!/usr/bin/env python3
import unittest
from financial_normalizer import normalized_company
from sector_valuation import discounted_proxy, valuation
class TestModels(unittest.TestCase):
 def make(self,category="software",ticker="ADBE"):
  annual=[]
  for i in range(3):
   annual.append({"yearEnd":str(2025-i)+"-12-31","sources":{"operating_cash_flow":{"accession":"123"}},
   "operatingCashFlow":500-i*20,"capex":70,"freeCashFlowSimple":430-i*20,
   "stockCompensation":40,"revenue":1000,"netIncome":240,
   "operatingIncome":300,"equity":700,"assets":1500,"liabilities":800,
   "cash":150,"currentDebt":None,"longDebt":100,"shortDebt":None,
   "weightedDilutedShares":100,"operatingMargin":.3,"freeCashFlowMargin":.43,"cashConversion":2})
  return {"ticker":ticker,"name":ticker,"category":category,"annual":annual,"status":"review_required","issues":[]}
 def test_no_invented_debt(self):
  fin=normalized_company(self.make());balance=fin["fiscalHistory"][0]["balanceSheet"]
  self.assertIsNone(balance["grossDebt"]);self.assertIsNone(balance["netDebt"])
  self.assertFalse(fin["coverage"]["debtFullyReconciled"])
 def test_sbc_adjustment_exact(self):
  fin=normalized_company(self.make());self.assertEqual(fin["fiscalHistory"][0]["cashFlow"]["ownerCashProxyAfterSBC"],390)
 def test_sector_dcf_is_not_purchase_price(self):
  src=self.make();fin=normalized_company(src);m=valuation(fin,src)
  self.assertTrue(m["scenarios"]);self.assertIsNone(m["priceTarget"])
  self.assertIsNone(m["purchasePrice"]);self.assertFalse(m["decisionReady"])
 def test_insurance_and_captive_finance_block(self):
  for sector,ticker in (("insurance","CB"),("industrial","DE")):
   src=self.make(sector,ticker);model=valuation(normalized_company(src),src)
   self.assertIsNone(model["scenarios"]);self.assertFalse(model["decisionReady"])
 def test_discount_violating_terminal_blocks(self):
  self.assertIsNone(discounted_proxy(200,100,.02,.05,.04))
 def test_incomplete_sbc(self):
  src=self.make();src["annual"][0]["stockCompensation"]=None
  fin=normalized_company(src);self.assertIsNone(fin["fiscalHistory"][0]["cashFlow"]["ownerCashProxyAfterSBC"])
  self.assertIn("MISSING_OWNER_CASH_PROXY",[x["code"] for x in fin["issues"]])
if __name__=="__main__":unittest.main()
