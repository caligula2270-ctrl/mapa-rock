#!/usr/bin/env python3
"""Run audited free SEC fundamental screening. Never publish auto-trading signals."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from fundamental_core import evaluate,CATEGORIES

ROOT=Path("investment-radar/v2/data")
SOURCE=ROOT/"sec-financial-facts.json"
DEST=ROOT/"fundamental-research.json"

def build(source:dict, today:dt.date|None=None)->dict:
    if source.get("schema")!=2:
        raise ValueError("SEC fundamental source schema must be 2; legacy data cannot be silently normalized")
    companies=source.get("companies",[])
    if not isinstance(companies,list) or len(companies)<5:
        raise ValueError("At least 5 official SEC companies must be downloaded; refused incomplete overwrite")
    expected=set(CATEGORIES)
    got=[x.get("ticker") for x in companies]
    if len(got)!=len(set(got)) or not set(got)<=expected:
        raise ValueError("Duplicate or unexpected ticker from public SEC data")
    asof=today or dt.datetime.now(dt.timezone.utc).date()
    result=[evaluate(c,asof) for c in companies]
    failures={e.get("ticker") for e in source.get("errors",[]) if e.get("ticker")}
    missing=sorted(expected-set(got))
    if failures or missing:
        # No stale-data masquerading: keep all valid companies; disclose gaps.
        for ticker in sorted(failures|set(missing)):
            if ticker not in got:
                result.append({"ticker":ticker,"name":ticker,"category":CATEGORIES.get(ticker),
                               "status":"blocked","annual":[],"issues":[{"severity":"block","code":"SEC_DOWNLOAD_MISSING","detail":"Official company facts missing in this run"}],
                               "investmentSignal":"disabled","decisionReady":False,"screening":None})
    result.sort(key=lambda x:x["ticker"])
    published={
        "schema":1,"engine":"deterministic-sec-fundamentals-v1",
        "analysisDate":asof.isoformat(),"sourceRetrievedAt":source.get("retrievedAt"),
        "sources":{"official":"https://data.sec.gov/api/xbrl/companyfacts/",
                   "filingForms":["10-K"],"currency":"USD"},
        "limitations":[
            "This is quantitative screening, not an AI-generated moat assessment.",
            "Annual fiscal periods only; quarterly reports are NOT automatically annualized.",
            "Simple FCF (CFO less property capex) is NOT FCFE and not a defensible purchase price.",
            "Moat, normalized ROIC, net financing, peer comparison and investment decision need audited human/company-specific input.",
            "Screening price ranges, where shown, are illustrative FCF-yield sensitivities and NOT fair value.",
            "Missing sources, stale periods, sector mismatches or inconsistent filings block valuation approval.",
            "US SEC XBRL data do not cover non-US companies fully; no invented global coverage.",
            "Neither buys securities nor makes automated recommendations."],
        "companies":result,
        "summary":{"tracked":len(result),
            "withAnnualFacts":sum(bool(x.get("annual")) for x in result),
            "blocked":sum(x["status"]=="blocked" for x in result),
            "reviewRequired":sum(x["status"]=="review_required" for x in result),
            "decisionReady":sum(x.get("decisionReady") is True for x in result),
            "fullQualityScores":sum(x.get("partialScore",{}).get("total") is not None for x in result),
            "illustrativeFCFScreens":sum(x.get("screening") is not None for x in result),
            "sourceErrors":len(source.get("errors",[]))}}
    return published

def main():
    source=json.loads(SOURCE.read_text())
    report=build(source)
    if DEST.exists():
        prev=json.loads(DEST.read_text())
        if prev==report:
            print("No financial-screening changes")
            return
    DEST.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print("SEC fundamental screen:",report["summary"])

if __name__=="__main__":main()
