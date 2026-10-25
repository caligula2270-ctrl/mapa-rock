from pathlib import Path
from datetime import date
import json
from autonomous_analyst import make_report
base=Path("investment-radar/v2/data")
load=lambda name:json.loads((base/name).read_text())
report=make_report(load("normalized-financials.json"),load("fundamental-research.json"),load("filing-audit.json"),date.today())
if report["summary"]["approved"]!=0 or any(c["approvedEntryPriceUSD"] is not None for c in report["companies"]):
 raise RuntimeError("Unapproved price must never be published")
out=base/"autonomous-analysis.json"
serialized=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
if not out.exists() or out.read_text()!=serialized:out.write_text(serialized)
print("Autonomous analyst:",report["summary"])
