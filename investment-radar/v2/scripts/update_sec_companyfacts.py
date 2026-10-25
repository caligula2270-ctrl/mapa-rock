#!/usr/bin/env python3
"""SEC XBRL facts for public Investment Radar research candidates.
Facts are reported facts as filed, not normalized annual forecasts, TTM or valuation.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
from urllib.request import Request,urlopen
import time

ROOT=Path("investment-radar/v2/data")
OUT=ROOT/"sec-financial-facts.json"
USER_AGENT=os.environ.get("SEC_USER_AGENT","").strip()
if "@" not in USER_AGENT: raise SystemExit("Set SEC_USER_AGENT GitHub secret with SEC contact email")
COMPANIES={
 "MSFT":(789019,"Microsoft"),"ADBE":(796343,"Adobe"),
 "V":(1403161,"Visa"),"MA":(1141391,"Mastercard"),
 "CB":(896159,"Chubb"),"CME":(1156375,"CME Group"),
 "GOOGL":(1652044,"Alphabet"),"FERG":(2011641,"Ferguson Enterprises"),
 "DE":(315189,"Deere")
}
TAGS={
 "operating_cash_flow":("us-gaap","NetCashProvidedByUsedInOperatingActivities","USD"),
 "property_capex":("us-gaap","PaymentsToAcquirePropertyPlantAndEquipment","USD"),
 "net_income":("us-gaap","NetIncomeLoss","USD"),
 "revenue_contract":("us-gaap","RevenueFromContractWithCustomerExcludingAssessedTax","USD"),
 "revenue":("us-gaap","Revenues","USD"),
 "shareholder_equity":("us-gaap","StockholdersEquity","USD"),
 "assets":("us-gaap","Assets","USD"),
 "liabilities":("us-gaap","Liabilities","USD"),
 "operating_income":("us-gaap","OperatingIncomeLoss","USD"),
 "shares_outstanding":("dei","EntityCommonStockSharesOutstanding","shares"),
 "diluted_weighted_shares":("us-gaap","WeightedAverageNumberOfDilutedSharesOutstanding","shares"),
 "cash":("us-gaap","CashAndCashEquivalentsAtCarryingValue","USD"),
 "short_term_debt":("us-gaap","ShortTermBorrowings","USD"),
 "long_term_debt":("us-gaap","LongTermDebtNoncurrent","USD"),
 "current_debt":("us-gaap","LongTermDebtCurrent","USD"),
 "capital_returns_dividends":("us-gaap","PaymentsOfDividends","USD"),
 "capital_returns_repurchases":("us-gaap","PaymentsForRepurchaseOfCommonStock","USD"),
 "stock_compensation":("us-gaap","ShareBasedCompensation","USD"),
 "common_shares":("us-gaap","CommonStockSharesOutstanding","shares"),
 "gross_profit":("us-gaap","GrossProfit","USD"),
 "taxes":("us-gaap","IncomeTaxExpenseBenefit","USD"),
 "interest_expense":("us-gaap","InterestExpense","USD"),
 "cash_interest_paid":("us-gaap","InterestPaid","USD"),
 "income_tax_expense":("us-gaap","IncomeTaxExpenseBenefit","USD"),
 "pretax_income":("us-gaap","IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest","USD"),
 "depreciation_and_amortization":("us-gaap","DepreciationDepletionAndAmortization","USD"),
 "depreciation_pp_e":("us-gaap","DepreciationDepletionAndAmortizationPropertyPlantAndEquipment","USD"),
 "depreciation_amortization_cf":("us-gaap","DepreciationDepletionAndAmortizationAcquiredInProcessResearchAndDevelopment","USD"),
 "proceeds_long_term_debt":("us-gaap","ProceedsFromIssuanceOfLongTermDebt","USD"),
 "repayments_long_term_debt":("us-gaap","RepaymentsOfLongTermDebt","USD"),
 "proceeds_debt":("us-gaap","ProceedsFromBorrowings","USD"),
 "payments_debt":("us-gaap","RepaymentsOfBorrowings","USD"),
 "operating_working_capital_change":("us-gaap","IncreaseDecreaseInOperatingCapital","USD"),
 "purchase_businesses_net_cash":("us-gaap","PaymentsToAcquireBusinessesNetOfCashAcquired","USD"),
 "purchase_intangibles":("us-gaap","PaymentsToAcquireIntangibleAssets","USD"),
 "cash_dividends":("us-gaap","PaymentsOfDividends","USD"),
 "ppe_accrued":("us-gaap","CapitalExpendituresIncurredButNotYetPaid","USD"),
 "finance_lease_ppe":("us-gaap","PropertyPlantAndEquipmentObtainedInExchangeForFinanceLeaseLiabilities","USD"),
 "operating_lease_liabilities":("us-gaap","OperatingLeaseLiabilityNoncurrent","USD"),
 "finance_lease_liabilities":("us-gaap","FinanceLeaseLiabilityNoncurrent","USD")
}
# These are candidates for documentary review, not mechanically fungible GAAP synonyms.
# A match is never inserted into normalized financials automatically.
REVIEW_FAMILIES={
 "capex":["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireOtherProductiveAssets","PaymentsToAcquireOtherPropertyPlantAndEquipment","CapitalExpenditures"],
 "depreciation":["DepreciationDepletionAndAmortization","DepreciationAmortizationAndAccretionNet","DepreciationAmortizationAndAccretion","Depreciation","AmortizationOfIntangibleAssets"],
 "interest":["InterestExpense","InterestExpenseNonOperating","InterestAndDebtExpense","InterestExpenseDebt"],
 "debt_proceeds":["ProceedsFromIssuanceOfLongTermDebt","ProceedsFromIssuanceOfDebt","ProceedsFromBorrowings","ProceedsFromDebtNetOfIssuanceCosts"],
 "debt_repayments":["RepaymentsOfLongTermDebt","RepaymentsOfDebt","RepaymentsOfBorrowings","RepaymentsOfOtherDebt"],
 "diluted_shares":["WeightedAverageNumberOfDilutedSharesOutstanding","WeightedAverageNumberOfSharesOutstandingDiluted","WeightedAverageNumberOfShareOutstandingBasicAndDiluted"],
 "income_tax":["IncomeTaxExpenseBenefit","IncomeTaxesPaidNet"],
 "working_capital":["IncreaseDecreaseInOperatingCapital","IncreaseDecreaseInAccountsReceivable","IncreaseDecreaseInInventory","IncreaseDecreaseInAccountsPayable"],
}
def evidence_candidates(src:dict)->dict:
 """Report exact SEC concepts with filing identity; no auto substitution."""
 namespaces=src.get("facts",{})
 result={}
 for family,aliases in REVIEW_FAMILIES.items():
  matches=[]
  for namespace in ("us-gaap","ifrs-full"):
   entries=namespaces.get(namespace,{})
   for tag in aliases:
    v=entries.get(tag)
    if not v:continue
    rows=v.get("units",{}).get("shares" if family=="diluted_shares" else "USD",[])
    valid=[]
    for a in rows:
     if a.get("form") not in ("10-K","10-Q") or not a.get("filed") or not a.get("end"):continue
     valid.append({k:a[k] for k in ("start","end","filed","form","accn","val") if k in a})
    valid.sort(key=lambda x:(x.get("end",""),x["filed"]),reverse=True)
    if valid:
     matches.append({"taxonomy":namespace,"tag":tag,"label":v.get("label",tag),
      "definition":v.get("description","")[:280],
      "latest":valid[0],"otherRecent":valid[1:3]})
  result[family]=matches
 return result

HEAD={"User-Agent":USER_AGENT,"Accept":"application/json"}
def fetch(cik:int)->dict:
 url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
 with urlopen(Request(url,headers=HEAD),timeout=45) as resp: return json.load(resp)
def extract(src:dict,tag:tuple[str,str,str])->list[dict]:
 namespace,name,unit=tag
 entries=src.get("facts",{}).get(namespace,{}).get(name,{}).get("units",{}).get(unit,[])
 cleaned=[]
 for f in entries:
  if f.get("form") not in ("10-K","10-Q") or not f.get("end") or "val" not in f:continue
  row={k:f[k] for k in ("start","end","val","filed","accn","form","fy","fp","frame") if k in f}
  cleaned.append(row)
 # Keep latest amended filing for each period; retain original period lengths.
 newest={}
 for row in cleaned:
  key=(row.get("start"),row["end"],row["form"])
  if key not in newest or row.get("filed","")>newest[key].get("filed",""):
   newest[key]=row
 return sorted(newest.values(),key=lambda x:(x["end"],x.get("filed","")),reverse=True)[:120]
def main():
 result={"schema":2,"source":"https://data.sec.gov/api/xbrl/companyfacts/","interpretation":"As-filed XBRL facts; periods may differ. No automatic FCFE, TTM, ROIC, intrinsic value or investment recommendation.","companies":[],"errors":[]}
 for ticker,(cik,name) in COMPANIES.items():
  try:
   source=fetch(cik)
   facts={key:extract(source,tag) for key,tag in TAGS.items()}
   result["companies"].append({"ticker":ticker,"name":name,"cik":cik,
     "factsURL":f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
     "facts":facts,"tagCandidateEvidence":evidence_candidates(source),"missing":[k for k,v in facts.items() if not v]})
  except Exception as e:
   result["errors"].append({"ticker":ticker,"error":type(e).__name__})
  time.sleep(.35)
 if OUT.exists():
  previous=json.loads(OUT.read_text())
  comparison={k:v for k,v in previous.items() if k!="retrievedAt"}
  if comparison==result:
   print("No changes in source reporting periods or facts")
   return
 result["retrievedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
 ROOT.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print("Official facts:",len(result["companies"]),"errors:",len(result["errors"]))
if __name__=="__main__":main()
