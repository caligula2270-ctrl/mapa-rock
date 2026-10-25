#!/usr/bin/env python3
"""Generate normalized SEC schedules and sector models; fail closed."""
from pathlib import Path
import json
from financial_normalizer import normalized_report
from sector_valuation import create_report
BASE=Path("investment-radar/v2/data")
def main():
 research=json.loads((BASE/"fundamental-research.json").read_text())
 if research["summary"]["tracked"]<9:raise ValueError("Research universe incomplete")
 norm=normalized_report(research)
 sectors=create_report(norm,research)
 if norm["summary"]["companies"]<9 or sectors["summary"]["covered"]<9:raise ValueError("Missing companies")
 if sectors["summary"]["closedValuations"]!=0 or sectors["summary"]["decisionReady"]!=0:
  raise ValueError("Unapproved investment recommendation generated")
 for name,data in (("normalized-financials.json",norm),("sector-models.json",sectors)):
  path=BASE/name
  output=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
  if not path.exists() or path.read_text()!=output:path.write_text(output)
 print("Normalized:",norm["summary"])
 print("Sector models:",sectors["summary"])
if __name__=="__main__":main()
