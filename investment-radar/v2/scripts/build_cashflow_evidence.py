from pathlib import Path
import json
from cashflow_evidence import build
ROOT=Path("investment-radar/v2/data")
source=json.loads((ROOT/"sec-financial-facts.json").read_text())
financial=json.loads((ROOT/"normalized-financials.json").read_text())
r=build(source,financial)
r["tagReview"]=[{"ticker":c["ticker"],"candidates":c.get("tagCandidateEvidence",{})}
 for c in source.get("companies",[])]
r["summary"]["candidateFamiliesFound"]=sum(
 sum(bool(items) for items in c["candidates"].values()) for c in r["tagReview"])
r["tagReviewPolicy"]="Informational evidence only. No replacement of missing financial tag without accounting equivalence, period and filing tie-out."

if r["summary"]["covered"]<9:raise RuntimeError("No publicar una cobertura incompleta")
p=ROOT/"cashflow-evidence.json";s=json.dumps(r,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
if not p.exists() or p.read_text()!=s:p.write_text(s)
print("FCFF/FCFE evidence:",r["summary"])
