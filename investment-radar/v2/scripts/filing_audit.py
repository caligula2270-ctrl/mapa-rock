"""Audited filing balance bridge, sensitivity and strict non-approval gates. Stdlib."""
from __future__ import annotations
from math import isfinite

def reconcile(record):
 d=record
 debt=sum(float(d[x]) for x in ("debtCurrent","debtNoncurrent","otherDebt"))
 liquidity=float(d["cash"])+float(d["liquidInvestments"])-float(d["restrictedInvestmentsIncluded"])
 if liquidity<0:raise ValueError("restricted investments exceed liquid assets")
 shares=float(d["weightedDilutedShares"])
 if shares<=0:raise ValueError("invalid shares")
 return {"ticker":d["ticker"],"date":d["date"],"debtMillions":round(debt,3),
         "availableLiquidAssetsBeforeOperatingReserveMillions":round(liquidity,3),
         "netDebtMillions":round(debt-liquidity,3),"weightedDilutedSharesMillions":shares,
         "pointInTimeSharesMillions":d.get("pointInTimeShares"),
         "sourceURL":d["sourceURL"],"notes":d["notes"],
         "status":"balance_filed_reconciled_only"}
def sensitivity(m,bridge):
 scenarios=m.get("scenarios") or {}
 center=scenarios.get("central",{}).get("illustrativePricePerShare")
 if center is None:return {"range":None,"checks":["NO_CASH_PROXY_SCENARIO"],"status":"blocked"}
 values=[r.get("illustrativePricePerShare") for r in scenarios.values()]
 if len(values)!=3 or any(v is None or not isfinite(v) or v<=0 for v in values):
  return {"range":None,"checks":["INVALID_SCENARIOS"],"status":"blocked"}
 lo,hi=min(values),max(values)
 if not lo<center<hi:return {"range":None,"checks":["SCENARIO_ORDER"],"status":"blocked"}
 # Scenario price is an UNLEVERED proxy, not an equity valuation;
 # display leverage-shift separately only as a dimensional diagnostic.
 debt_per_share=bridge["netDebtMillions"]/bridge["weightedDilutedSharesMillions"]
 return {"range":{"low":lo,"central":center,"high":hi},
         "spreadPct":round((hi-lo)/center*100,2),
         "netDebtPerWeightedDilutedShare":round(debt_per_share,2),
         "checks":["SCENARIO_ORDER_OK","NET_DEBT_RECONCILED_AT_FY_DATE",
                   "EQUITY_VALUE_NOT_DERIVABLE_FROM_OWNER_CASH_PROXY",
                   "SBC_ALREADY_DEDUCTED_PROVISIONALLY",
                   "NO_OPERATING_CASH_RESERVE",
                   "NO_DILUTION_FORECAST",
                   "NO_COST_OF_CAPITAL_MARKET_CALIBRATION"],
         "status":"not_decision_ready"}
def report(filings,models):
 bridges={x["ticker"]:reconcile(x) for x in filings["bridges"]}
 results=[]
 for m in models["companies"]:
  b=bridges.get(m["ticker"])
  if b:
   test=sensitivity(m,b)
   results.append({"ticker":m["ticker"],"balance":b,"sensitivity":test,
    "auditVerdict":"Not ready",
    "criticalOpenIssues":["CURRENT_INTERIM_DEBT_BRIDGE","MINIMUM_OPERATING_CASH",
     "DILUTION_SHARE_COUNT","CASH_FLOW_NORMALIZATION","SECTOR_UNDERWRITING",
     "MOAT_ROIC_EVIDENCE","DISCOUNT_RATE_CREDIBILITY"]})
  else:
   results.append({"ticker":m["ticker"],"auditVerdict":"Not assessable",
     "criticalOpenIssues":["FISCAL_BALANCE_BRIDGE_MISSING"],
     "sensitivity":{"status":"blocked"}})
 return {"schema":1,"method":"documentary_fiscal_balance_reconciliation_v1",
  "notes":"FY reconciliations do not substitute for latest interim notes, FCFE/FCFF modeling or analyst approval.",
  "companies":results,"summary":{"reconciledFY":len(bridges),
     "modeled":len(results),"decisionReady":0,"closedValuations":0}}
