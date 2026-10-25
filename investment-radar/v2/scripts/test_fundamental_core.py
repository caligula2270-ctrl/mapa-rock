#!/usr/bin/env python3
"""Regression tests for investment-radar/fundamental_core.py. No web/API required."""
import datetime as dt
import unittest
from fundamental_core import annual_facts, instants, evaluate
from analyze_fundamentals import build

TODAY=dt.date(2026,10,25)
ENDS=["2025-12-31","2024-12-31","2023-12-31","2022-12-31"]
STARTS=["2025-01-01","2024-01-01","2023-01-01","2022-01-01"]
def sample(ticker="ADBE"):
    tags={}
    def duration(name,values):
        tags[name]=[{"start":s,"end":e,"val":val,"filed":e[:4]+"-03-01","accn":"0000000000-00-000001","form":"10-K"} for s,e,val in zip(STARTS,ENDS,values)]
    def instant(name,values):
        tags[name]=[{"end":e,"val":val,"filed":e[:4]+"-03-01","accn":"0000000000-00-000001","form":"10-K"} for e,val in zip(ENDS,values)]
    duration("operating_cash_flow",[450,380,310,260])
    duration("property_capex",[65,60,55,50])
    duration("revenue_contract",[1800,1650,1500,1300])
    duration("net_income",[290,250,230,200])
    duration("operating_income",[340,310,290,280])
    duration("diluted_weighted_shares",[100,102,104,108])
    instant("assets",[2000,1900,1800,1700])
    instant("liabilities",[900,850,800,750])
    instant("shareholder_equity",[1100,1050,1000,950])
    return {"ticker":ticker,"name":ticker,"cik":1234,
            "factsURL":"https://data.sec.gov/api/xbrl/companyfacts/CIK0000001234.json",
            "facts":tags}
class TestSECNormalization(unittest.TestCase):
    def test_annual_period_filter_and_full_year(self):
        a=sample()
        a["facts"]["operating_cash_flow"].append({"start":"2025-10-01","end":"2025-12-31","val":2000,"filed":"2026-02-01","accn":"100","form":"10-K"})
        facts=annual_facts(a,"operating_cash_flow")
        self.assertEqual(facts["2025-12-31"]["val"],450)
    def test_amendment_resolved_by_latest_filed(self):
        a=sample()
        a["facts"]["operating_cash_flow"].append({"start":"2025-01-01","end":"2025-12-31","val":455,"filed":"2026-03-02","accn":"200","form":"10-K"})
        self.assertEqual(annual_facts(a,"operating_cash_flow")["2025-12-31"]["val"],455)
    def test_instants_not_durations(self):
        a=sample()
        a["facts"]["assets"].append({"start":"2025-01-01","end":"2025-12-31","val":99999,"filed":"2026-03-10","accn":"200","form":"10-K"})
        self.assertEqual(instants(a,"assets")["2025-12-31"]["val"],2000)
    def test_fcf_math_and_source(self):
        a=evaluate(sample(),TODAY)
        self.assertEqual(a["annual"][0]["freeCashFlowSimple"],385)
        self.assertEqual(a["annual"][0]["fcfPerDilutedShare"],3.85)
        self.assertEqual(a["annual"][0]["sources"]["operating_cash_flow"]["unit"],"USD")
        self.assertFalse(a["decisionReady"])
        self.assertIsNone(a["partialScore"]["total"])
        self.assertEqual(a["investmentSignal"],"disabled")
    def test_margins(self):
        a=evaluate(sample(),TODAY)
        self.assertEqual(a["annual"][0]["operatingMargin"],round(340/1800,6))
    def test_missing_capex_blocks(self):
        x=sample();x["facts"].pop("property_capex")
        a=evaluate(x,TODAY)
        self.assertEqual(a["status"],"blocked")
        self.assertIsNone(a["screening"])
        self.assertIn("MISSING_CAPEX",[e["code"] for e in a["issues"]])
    def test_financial_insurance_prohibits_dcf(self):
        a=evaluate(sample("CB"),TODAY)
        self.assertEqual(a["status"],"blocked")
        self.assertIsNone(a["screening"])
    def test_finance_arm_sector_blocks(self):
        a=evaluate(sample("DE"),TODAY)
        self.assertIn("FINANCE_ARM_SEGMENT",[e["code"] for e in a["issues"]])
    def test_stale_blocks(self):
        a=evaluate(sample(),dt.date(2028,6,1))
        self.assertEqual(a["status"],"blocked")
    def test_negative_fcf_flags(self):
        x=sample();x["facts"]["property_capex"][0]["val"]=900
        a=evaluate(x,TODAY)
        self.assertIn("NEGATIVE_FCF",[e["code"] for e in a["issues"]])
    def test_balance_mismatch_flags(self):
        x=sample();x["facts"]["liabilities"][0]["val"]=1300
        a=evaluate(x,TODAY)
        self.assertIn("BALANCE_MISMATCH",[e["code"] for e in a["issues"]])
    def test_schema_gate_blocks_incomplete_source(self):
        with self.assertRaises(ValueError):
            build({"schema":2,"companies":[sample()]},TODAY)
    def test_full_dataset_yields_no_auto_buy(self):
        t=["MSFT","ADBE","V","MA","CB","CME","GOOGL","FERG","DE"]
        report=build({"schema":2,"companies":[sample(k) for k in t],"errors":[]},TODAY)
        self.assertEqual(report["summary"]["decisionReady"],0)
        self.assertEqual(report["summary"]["fullQualityScores"],0)
        self.assertEqual(report["summary"]["tracked"],9)
        self.assertTrue(all(x["investmentSignal"]=="disabled" for x in report["companies"]))
    def test_sources_missing_marked(self):
        report=build({"schema":2,"companies":[sample(k) for k in ["MSFT","ADBE","V","MA","CB","CME"]],"errors":[{"ticker":"GOOGL"}]},TODAY)
        self.assertIn("GOOGL",[x["ticker"] for x in report["companies"] if x["status"]=="blocked"])
if __name__=="__main__":unittest.main()
