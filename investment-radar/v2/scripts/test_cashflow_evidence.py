import unittest
from cashflow_evidence import record,build
def fixture(sector="software"):
 rows=[{"fiscalYearEnd":"2025-12-31","incomeStatement":{"revenue":1000,"operatingIncome":300,"netIncome":200},
  "cashFlow":{"operatingCashFlow":340,"propertyCapex":70,"stockCompensation":30}}]
 source={"ticker":"TEST","name":"Test","facts":{}}
 fin={"ticker":"TEST","name":"Test","category":sector,"fiscalHistory":rows}
 return source,fin
class TestCashflowEvidence(unittest.TestCase):
 def test_missing_finance_facts_are_not_zero(self):
  src,fin=fixture();r=record(src,fin);y=r["fiscalAnnualBridges"][0]
  self.assertEqual(y["reconciliations"]["cfoMinusPPECapex"],270)
  self.assertIsNone(y["reconciliations"]["netDebtIssuedPartial"])
  self.assertIsNone(y["reconciliations"]["fcfeCashPlusBorrowingProxy"])
  self.assertIsNone(y["reconciliations"]["fcffFromCFOAndReportedInterestTax"])
  self.assertFalse(y["fcffVerified"]);self.assertFalse(y["fcfeVerified"])
 def test_insurance_ebit_fcff_is_blocked(self):
  src,fin=fixture("insurance")
  result=record(src,fin)
  self.assertIn("SECTOR_NOT_GENERAL_CORPORATE_FCFF",result["fiscalAnnualBridges"][0]["issues"])
 def test_missing_capex_never_imputed(self):
  src,fin=fixture();fin["fiscalHistory"][0]["cashFlow"]["propertyCapex"]=None
  self.assertIsNone(record(src,fin)["fiscalAnnualBridges"][0]["reconciliations"]["cfoMinusPPECapex"])
if __name__=="__main__":unittest.main()
