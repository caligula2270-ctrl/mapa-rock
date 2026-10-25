from pathlib import Path
import json
from filing_audit import report
base=Path("investment-radar/v2/data")
filings=json.loads((base/"filing-balance-bridges.json").read_text())
models=json.loads((base/"sector-models.json").read_text())
data=report(filings,models)
p=base/"filing-audit.json"
text=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
if not p.exists() or p.read_text()!=text:p.write_text(text)
print("Documentary audit:",data["summary"])
