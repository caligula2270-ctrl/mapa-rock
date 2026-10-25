"""Conservative FCFF/FCFE evidence engine, all as-filed SEC values.
Incomplete or sector-incompatible valuations fail closed, not filled by assumptions.
"""
from __future__ import annotations
from math import isfinite
from statistics import median

BANKLIKE={"insurance","industrial"}
def num(v):
 return float(v) if isinstance(v,(int,float)) and isfinite(v) else None
def annual(c,tag,end):
 rows=c.get("facts",{}).get(tag,[])
 hits=[]
 for x in rows:
  try:
   if x.get("form")!="10-K" or x.get("end")!=end or not x.get("start"):continue
   days=__import__("datetime").date.fromisoformat(x["end"])-__import__("datetime").date.fromisoformat(x["start"])
   if not 330<=days.days<=380:continue
   if num(x.get("val")) is None:continue
   hits.append(x)
  except (TypeError,ValueError):pass
 return max(hits,key=lambda x:x.get("filed","")) if hits else None

def metric(c,tag,end):
 r=annual(c,tag,end)
 return num(r["val"]) if r is not None else None

def record(c,fin):
 category=fin["category"]
 rows=[]
 for row in fin["fiscalHistory"][:5]:
  end=row["fiscalYearEnd"]
  cf=row["cashFlow"];income=row["incomeStatement"]
  rev=income["revenue"];op=income["operatingIncome"];cfo=cf["operatingCashFlow"]
  capex=cf["propertyCapex"];ni=income["netIncome"]
  sbc=cf["stockCompensation"]
  interest=metric(c,"interest_expense",end)
  tax=metric(c,"income_tax_expense",end)
  pretax=metric(c,"pretax_income",end)
  # GAAP expense tax rate is not equivalent to current marginal tax.
  reported_etr=tax/pretax if tax is not None and pretax and pretax>0 else None
  da=metric(c,"depreciation_and_amortization",end)
  capex_acc=metric(c,"ppe_accrued",end)
  bought=metric(c,"purchase_businesses_net_cash",end)
  proceeds_lt=metric(c,"proceeds_long_term_debt",end)
  repayments_lt=metric(c,"repayments_long_term_debt",end)
  proceeds_other=metric(c,"proceeds_debt",end)
  repayments_other=metric(c,"payments_debt",end)
  wc=metric(c,"operating_working_capital_change",end)
  flags=[]
  if category in BANKLIKE:flags.append("SECTOR_NOT_GENERAL_CORPORATE_FCFF")
  if cfo is None or capex is None:flags.append("CFO_OR_CAPEX_ABSENT")
  if da is None:flags.append("D_AND_A_MISSING")
  if op is None:flags.append("OPERATING_EARNINGS_MISSING")
  if interest is None:flags.append("INTEREST_EXPENSE_MISSING")
  if reported_etr is None or not 0<=reported_etr<=.5:flags.append("EFFECTIVE_TAX_RATE_NOT_USABLE")
  if wc is None:flags.append("OPERATING_WORKING_CAPITAL_DELTA_NOT_ISOLATED")
  if bought is None:flags.append("ACQUISITIONS_NOT_ISOLATED")
  if any(x is None for x in (proceeds_lt,repayments_lt,proceeds_other,repayments_other)):
   flags.append("NET_BORROWING_CATEGORIES_UNRESOLVED")
  if capex_acc is None:flags.append("CAPEX_ACCRUALS_NOT_QUANTIFIED")
  # Compute only independently supported metrics.
  simple_fcf=cfo-capex if cfo is not None and capex is not None else None
  after_sbc=simple_fcf-sbc if simple_fcf is not None and sbc is not None else None
  reported_debt_net=(proceeds_lt-repayments_lt+proceeds_other-repayments_other
     if all(x is not None for x in (proceeds_lt,repayments_lt,proceeds_other,repayments_other)) else None)
  fcfe_cash=simple_fcf+reported_debt_net if simple_fcf is not None and reported_debt_net is not None else None
  # NI + D&A - capex - WC changes + net borrowing requires sign/definitions verified.
  # FCF + debt borrowing is closest observable proxy; not necessarily full FCFE.
  debt_free_cash_before_tax_interest=simple_fcf if simple_fcf is not None else None
  fcff_via_cfo=(simple_fcf+interest*(1-reported_etr) if simple_fcf is not None and
    interest is not None and reported_etr is not None and category not in BANKLIKE else None)
  # Independent EBIT bridge only if D&A and WC rollforward are source supported.
  fcff_ebit=(op*(1-reported_etr)+da-capex-wc if all(x is not None
     for x in (op,reported_etr,da,capex,wc)) and category not in BANKLIKE else None)
  rel=(abs(fcff_via_cfo-fcff_ebit)/max(abs(fcff_ebit),1)
    if fcff_via_cfo is not None and fcff_ebit is not None else None)
  if rel is not None and rel>.10:flags.append("FCFF_BRIDGES_DISAGREE_OVER_10PCT")
  source={}
  for tag in ("interest_expense","income_tax_expense","pretax_income","depreciation_and_amortization",
       "operating_working_capital_change","proceeds_long_term_debt","repayments_long_term_debt",
       "proceeds_debt","payments_debt","purchase_businesses_net_cash","ppe_accrued"):
   src=annual(c,tag,end)
   if src:source[tag]={k:src.get(k) for k in ("start","end","filed","accn","form")}
  rows.append({"fiscalYearEnd":end,
    "sourceTags":source,
    "reported":{"revenue":rev,"EBIT":op,"netIncome":ni,"cashFromOperations":cfo,
       "capitalExpenditureCash":capex,"depreciationAndAmortization":da,
       "interestExpense":interest,"taxExpense":tax,"pretaxIncome":pretax,
       "reportedTaxRatioNotMarginal":round(reported_etr,5) if reported_etr is not None else None,
       "changeOperatingWorkingCapitalUnverifiedSign":wc,"acquisitionCash":bought,
       "unpaidPPE":capex_acc,"stockBasedCompensation":sbc,
       "debtProceedsLongTerm":proceeds_lt,"debtRepaymentsLongTerm":repayments_lt,
       "otherDebtProceeds":proceeds_other,"otherDebtRepayments":repayments_other},
    "reconciliations":{"cfoMinusPPECapex":simple_fcf,
       "cashAfterSBCProxy":after_sbc,
       "netDebtIssuedPartial":reported_debt_net,
       "fcfeCashPlusBorrowingProxy":fcfe_cash,
       "fcffFromCFOAndReportedInterestTax":fcff_via_cfo,
       "fcffEBITWorkingCapitalBridge":fcff_ebit,
       "fcffCrossCheckGapPct":round(100*rel,3) if rel is not None else None},
    "issues":flags,
    "fcffVerified":False,"fcfeVerified":False})
 # Never treat isolated GAAP tags as verified sector-normalized FCFF/FCFE.
 return {"ticker":c["ticker"],"name":c["name"],"sector":category,
    "fiscalAnnualBridges":rows,
    "verification":{"annualRows":len(rows),"fullFCFF":0,"fullFCFE":0,
      "pendingSourceEvidence":sum(len(x["issues"]) for x in rows)},
    "method":"GAAP tag-level cash bridge with strict controls; not yet normalized FCFF or FCFE"}
def build(source,fin):
 idx={x["ticker"]:x for x in source["companies"]}
 entries=[record(idx[f["ticker"]],f) for f in fin["financials"] if f["ticker"] in idx]
 return {"schema":1,"engine":"free-cash-flow-evidence-v1",
   "cautions":["Taxes are GAAP expense ratios, not normalized marginal rates",
      "Debt flows require financing-note reconciliation; missing categories are not zero",
      "CFO includes working capital and noncash SBC, so adjustment must prevent double counting",
      "Capex accrual and leases require footnote checks",
      "Sector cases (insurance, captive finance) cannot use generic FCFF"],
   "companies":entries,
   "summary":{"covered":len(entries),
      "withCashFlowSimple":sum(bool(x["fiscalAnnualBridges"] and x["fiscalAnnualBridges"][0]["reconciliations"]["cfoMinusPPECapex"] is not None) for x in entries),
      "verifiedFCFF":0,"verifiedFCFE":0}}
