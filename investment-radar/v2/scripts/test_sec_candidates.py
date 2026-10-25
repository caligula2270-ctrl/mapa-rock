import unittest
from update_sec_companyfacts import evidence_candidates
class TestSECCandidates(unittest.TestCase):
 def test_candidate_keeps_filing_identity_and_does_not_substitute(self):
  data={"facts":{"us-gaap":{"PaymentsToAcquirePropertyPlantAndEquipment":{
   "label":"Cash PPE purchases","description":"Cash PPE","units":{"USD":[
    {"start":"2024-08-01","end":"2025-04-30","val":235,"filed":"2025-06-03","form":"10-Q","accn":"testA"},
    {"start":"2024-08-01","end":"2025-07-31","val":310,"filed":"2025-09-01","form":"8-K","accn":"testB"}]}}}}}
  result=evidence_candidates(data)
  self.assertEqual(len(result["capex"]),1)
  self.assertEqual(result["capex"][0]["latest"]["form"],"10-Q")
  self.assertEqual(result["capex"][0]["latest"]["end"],"2025-04-30")
  self.assertEqual(result["capex"][0]["latest"]["accn"],"testA")
 def test_missing_not_assumed_zero(self):
  r=evidence_candidates({"facts":{}})
  self.assertEqual(r["capex"],[])
  self.assertEqual(r["debt_proceeds"],[])
if __name__=="__main__":unittest.main()
