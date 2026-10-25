#!/usr/bin/env python3
"""Deterministic SEC fundamental accounting normalization. Standard library only.

Safety: do not annualize quarterly data, impute missing facts, or issue buy signals.
All metrics carry official source accession, reporting period and filing date.
"""
from __future__ import annotations
import datetime as dt
import math
from statistics import median

CATEGORIES = {
 "MSFT":"software", "ADBE":"software", "V":"payments", "MA":"payments",
 "CB":"insurance", "CME":"exchange", "GOOGL":"digital_platform",
 "FERG":"distribution", "DE":"industrial",
}
FACT_FIELDS = ("start","end","val","filed","accn","form")
DURATION_MIN, DURATION_MAX = 330, 380

def annual_facts(company:dict, tag:str)->dict:
    """Use full 10-K ~12-month periods; revisions: latest filed per period."""
    result = {}
    for raw in company.get("facts",{}).get(tag,[]):
        if raw.get("form")!="10-K" or not all(k in raw for k in FACT_FIELDS):
            continue
        try:
            days=(dt.date.fromisoformat(raw["end"])-dt.date.fromisoformat(raw["start"])).days
            val=float(raw["val"])
            if not DURATION_MIN<=days<=DURATION_MAX or not math.isfinite(val):
                continue
        except (ValueError,TypeError): continue
        end=raw["end"]
        if end not in result or raw["filed"]>result[end]["filed"]:
            result[end]={k:raw[k] for k in FACT_FIELDS}
    return result

def instants(company:dict, tag:str)->dict:
    """Use annual 10-K instant facts, explicitly no start date."""
    result={}
    for raw in company.get("facts",{}).get(tag,[]):
        if raw.get("form")!="10-K" or "start" in raw: continue
        if not all(k in raw for k in ("end","val","filed","accn")):continue
        try:
            val=float(raw["val"])
            if not math.isfinite(val): continue
        except (ValueError,TypeError): continue
        end=raw["end"]
        if end not in result or raw["filed"]>result[end]["filed"]:
            result[end]={k:raw[k] for k in ("end","val","filed","accn","form")}
    return result

def interim_ytd(company:dict, tag:str, latest_fy_end:str):
    """Latest as-filed 10-Q YTD after FY close. Never extrapolate to FY/TTM."""
    rows=[]
    for raw in company.get("facts",{}).get(tag,[]):
        if raw.get("form")!="10-Q" or not all(k in raw for k in FACT_FIELDS):continue
        try:
            start=dt.date.fromisoformat(raw["start"])
            end=dt.date.fromisoformat(raw["end"])
            value=float(raw["val"])
            duration=(end-start).days
            if not 65<=duration<=305 or not math.isfinite(value):continue
            if end<=dt.date.fromisoformat(latest_fy_end):continue
            if start!=dt.date.fromisoformat(latest_fy_end)+dt.timedelta(days=1):continue
        except (TypeError,ValueError):continue
        rows.append({k:raw[k] for k in FACT_FIELDS})
    rows.sort(key=lambda x:(x["end"],x["filed"]),reverse=True)
    return rows[0] if rows else None

def interim_snapshot(company:dict,fy_end:str):
    """Cash generation after last FY, with matching start/end across cash and CAPEX."""
    fields={"operatingCashFlow":"operating_cash_flow","capex":"property_capex",
            "revenue":"revenue_contract","netIncome":"net_income"}
    cash=interim_ytd(company,"operating_cash_flow",fy_end)
    if not cash:return None
    out={"type":"as_file_ytd_10q_not_annualized","start":cash["start"],"end":cash["end"],
         "filed":cash["filed"],"metrics":{},"sources":{}}
    for display,field in fields.items():
        row=cash if field=="operating_cash_flow" else interim_ytd(company,field,fy_end)
        if row and (row["start"],row["end"])==(cash["start"],cash["end"]):
            out["metrics"][display]=float(row["val"])
            out["sources"][display]={"accn":row["accn"],"filed":row["filed"],"unit":"USD"}
        else:out["metrics"][display]=None
    c,cap=out["metrics"]["operatingCashFlow"],out["metrics"]["capex"]
    out["metrics"]["freeCashFlowSimple"]=c-cap if c is not None and cap is not None else None
    return out

def latest_row(d:dict,end:str):
    return d.get(end)

def metric(raw):
    return None if raw is None else float(raw["val"])

def safe_div(x,y):
    return round(x/y,6) if x is not None and y not in (None,0) else None

def evaluate(company:dict, today:dt.date)->dict:
    ticker=company.get("ticker","?")
    category=CATEGORIES.get(ticker,"unknown")
    tags=("operating_cash_flow","property_capex","revenue_contract","revenue","net_income",
          "operating_income","diluted_weighted_shares","stock_compensation","shareholder_equity",
          "assets","liabilities","cash","current_debt","long_term_debt","short_term_debt")
    flows={t:annual_facts(company,t) for t in tags}
    dates=sorted(flows["operating_cash_flow"].keys(),reverse=True)
    issues=[]
    if not dates:
        return {"ticker":ticker,"name":company.get("name",ticker),"category":category,
          "status":"blocked","issues":[{"severity":"block","code":"NO_ANNUAL_CFO","detail":"No comparable annual operating cash flow in SEC 10-K"}],
          "annual":[],"dataQuality":{},"partialScore":{},"screening":None,"investmentSignal":"disabled"}
    latest=dates[0]
    try:
        age=(today-dt.date.fromisoformat(latest)).days
    except ValueError:age=9999
    if age>470:issues.append({"severity":"block","code":"STALE_REPORT","detail":"Latest full fiscal year ends more than 470 days ago"})
    end_dates=dates[:5]
    annual=[]
    for end in end_dates:
        row={}
        sources={}
        def get(tag,instant=False):
            raw=latest_row(instants(company,tag),end) if instant else latest_row(flows[tag],end)
            if raw is not None:sources[tag]={"accession":raw["accn"],"filed":raw["filed"],"end":raw["end"],"start":raw.get("start"),"form":raw["form"],"unit":"shares" if "shares" in tag else "USD"}
            return metric(raw)
        row["yearEnd"]=end
        row["operatingCashFlow"]=get("operating_cash_flow")
        row["capex"]=get("property_capex")
        a,b=get("revenue_contract"),get("revenue")
        row["revenue"]=a if a is not None else b
        if a is not None and b is not None and abs(a-b)>0.05*max(abs(a),abs(b),1):
            issues.append({"severity":"review","code":"REVENUE_TAG_CONFLICT","period":end,"detail":"Different US GAAP revenue tags differ by >5%"})
        row["netIncome"]=get("net_income")
        row["operatingIncome"]=get("operating_income")
        row["weightedDilutedShares"]=get("diluted_weighted_shares")
        row["stockCompensation"]=get("stock_compensation")
        row["equity"]=get("shareholder_equity",True)
        row["assets"]=get("assets",True)
        row["liabilities"]=get("liabilities",True)
        row["cash"]=get("cash",True)
        row["currentDebt"]=get("current_debt",True)
        row["longDebt"]=get("long_term_debt",True)
        row["shortDebt"]=get("short_term_debt",True)
        if row["operatingCashFlow"] is not None and row["capex"] is not None:
            row["freeCashFlowSimple"]=row["operatingCashFlow"]-row["capex"]
        else:row["freeCashFlowSimple"]=None
        row["operatingMargin"]=safe_div(row["operatingIncome"],row["revenue"])
        row["freeCashFlowMargin"]=safe_div(row["freeCashFlowSimple"],row["revenue"])
        row["cashConversion"]=safe_div(row["operatingCashFlow"],row["netIncome"])
        row["fcfPerDilutedShare"]=safe_div(row["freeCashFlowSimple"],row["weightedDilutedShares"])
        row["sources"]=sources
        if all(row[k] is not None for k in ("assets","liabilities","equity")):
            a=row["assets"]
            if a>0 and abs(a-row["liabilities"]-row["equity"])/a>0.025:
                issues.append({"severity":"review","code":"BALANCE_MISMATCH","period":end,"detail":"Assets differ from liabilities+equity >2.5%; noncontrolling interest or tag basis may differ"})
        annual.append(row)
    complete=[a for a in annual if a["freeCashFlowSimple"] is not None]
    if len(complete)<3:
        issues.append({"severity":"block","code":"INSUFFICIENT_ANNUAL_FCF","detail":"Three full-fiscal-year CFO and CAPEX periods required"})
    if any(r["capex"] is None for r in annual[:3]):
        issues.append({"severity":"block","code":"MISSING_CAPEX","detail":"CAPEX omitted rather than treated as zero"})
    if annual[0]["weightedDilutedShares"] in (None,0):
        issues.append({"severity":"block","code":"MISSING_DILUTED_SHARES","detail":"No as-filed annual weighted diluted share base"})
    elif annual[0]["weightedDilutedShares"]<0:
        issues.append({"severity":"block","code":"INVALID_SHARES","detail":"Diluted shares must be positive"})
    elif len(annual)>1 and annual[1]["weightedDilutedShares"] not in (None,0):
        if annual[0]["weightedDilutedShares"]>1.15*annual[1]["weightedDilutedShares"]:
            issues.append({"severity":"review","code":"DILUTION_15PCT","detail":"Weighted diluted share count grew more than 15% in one year"})
    if category in ("insurance",):
        issues.append({"severity":"block","code":"SECTOR_INSURANCE_MODEL","detail":"CFO minus capex is not insurance distributable owner earnings; use reserves and adjusted book valuation"})
    if category=="industrial" and ticker=="DE":
        issues.append({"severity":"block","code":"FINANCE_ARM_SEGMENT","detail":"Industrial and captive finance cash flows must be separated before valuation"})
    if category=="exchange":
        issues.append({"severity":"review","code":"CLEARING_CLIENT_ASSETS","detail":"Clearing collateral is not shareholder cash"})
    if category=="digital_platform":
        issues.append({"severity":"review","code":"AI_CAPEX_NORMALIZATION","detail":"Forecast capital expenditure and financing must be separated from reported simple FCF"})
    if category=="distribution":
        issues.append({"severity":"review","code":"WORKING_CAPITAL_CYCLE","detail":"Normalize inventories, receivables, seasonality and M&A"})
    if category in ("payments","software"):
        issues.append({"severity":"review","code":"STOCK_COMP_AND_DEBT","detail":"Reconcile stock compensation, buybacks, net borrowing and fully diluted shares"})
    if any(a["freeCashFlowSimple"] is not None and a["freeCashFlowSimple"]<0 for a in annual[:3]):
        issues.append({"severity":"review","code":"NEGATIVE_FCF","detail":"At least one latest-year simple FCF is negative"})
    if len(complete)>=3 and annual[0]["weightedDilutedShares"] and category not in ("insurance","industrial"):
        vals=[a["freeCashFlowSimple"] for a in annual[:3] if a["freeCashFlowSimple"] is not None]
        normalized=median(vals) if len(vals)==3 else None
        if normalized is not None and normalized>0:
            per=normalized/annual[0]["weightedDilutedShares"]
            screening={"method":"illustrative_simple_fcf_yield","normalized3FYFCF":round(normalized,2),
              "proxyFCFPerWeightedDilutedShare":round(per,4),"unit":"USD/share",
              "illustrativeAtYields":{"0.06":round(per/.06,2),"0.08":round(per/.08,2),"0.10":round(per/.10,2)},
              "caveat":"CFO-CAPEX is not FCFE; debt flows, dilution and reinvestment not reconciled; NOT intrinsic value or buy price"}
        else:screening=None
    else:screening=None
    fcf=[a["freeCashFlowSimple"] for a in annual[:3]]
    positives=sum(v is not None and v>0 for v in fcf)
    cash_score=(10 if positives==3 else 5 if positives==2 else 0) if len(annual)>=3 else None
    recent=annual[0]
    if cash_score is not None and recent["cashConversion"] is not None:
        cash_score+=5 if recent["cashConversion"]>=1 else 2 if recent["cashConversion"]>=.8 else 0
    score={"moat":None,"returns":None,"cash":cash_score,"balance":None,"valuation":None,"total":None,
      "explanation":"Quantitative cash persistence proxy only; moat, ROIC and valuation are not evidenced by XBRL alone"}
    interim=interim_snapshot(company,latest)
    if interim and interim["metrics"]["freeCashFlowSimple"] is None:
        issues.append({"severity":"review","code":"INTERIM_FCF_NOT_COMPARABLE",
           "period":interim["end"],"detail":"10-Q YTD CFO and CAPEX do not match or capex is missing"})
    if interim:
        issues.append({"severity":"review","code":"INTERIM_PERIOD_NOT_IN_FY_SCREEN",
           "period":interim["end"],"detail":"Newer interim YTD information exists; prior fiscal-year screen excludes it"})
    if len(annual)>=2:
        first,prior=annual[:2]
        for key,code,drop in (
            ("operatingCashFlow","OPERATING_CASH_COLLAPSE",.30),
            ("freeCashFlowSimple","FCF_DROP_40PCT",.40),
        ):
            x,y=first.get(key),prior.get(key)
            if x is not None and y is not None and y>0 and x<y*(1-drop):
                issues.append({"severity":"review","code":code,
                    "detail":"Latest full-year "+key+" fell by more than "+str(int(drop*100))+"% from prior FY"})
        curr,prev=first.get("operatingMargin"),prior.get("operatingMargin")
        if curr is not None and prev is not None and curr<prev-.05:
            issues.append({"severity":"review","code":"OPERATING_MARGIN_DROP",
                "detail":"Latest annual operating margin declined by more than five percentage points"})
    if recent["stockCompensation"] is not None and recent["operatingCashFlow"] and recent["operatingCashFlow"]>0:
        if recent["stockCompensation"]/recent["operatingCashFlow"]>.30:
            issues.append({"severity":"review","code":"HIGH_STOCK_COMP",
                "detail":"Stock compensation exceeds 30% of operating cash flow; normalize share count and owner earnings"})
    blocked=any(x["severity"]=="block" for x in issues)
    return {"ticker":ticker,"name":company.get("name",ticker),"cik":company.get("cik"),
       "sourceURL":company.get("factsURL"),"category":category,"latestFiscalYearEnd":latest,
       "fiscalAgeDays":age,"status":"blocked" if blocked else "review_required",
       "annual":annual,"interimYTD":interim,"partialScore":score,"screening":screening,
       "issues":issues,"investmentSignal":"disabled","decisionReady":False}
