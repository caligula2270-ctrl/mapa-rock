"""Adobe pilot: documented SEC cash bridge and explicit reinvestment FCFF DCF.
All monetary inputs and share counts in millions. Research estimates, not trade signals.
"""
from datetime import date
from math import isfinite
from statistics import median

def finite(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x)

def check_cash_row(row):
    calc=sum(row[k] for k in ("ni","da","sbc","deferredTax","impairment","otherNoncash"))+sum(row["wc"])
    return calc-row["cfo"]

def dcf(revenue,margin,tax,growth,roic,wacc,terminal,terminal_roic,net_debt,shares):
    if not all(finite(v) for v in (revenue,margin,tax,growth,roic,wacc,terminal,terminal_roic,net_debt,shares)):
        raise ValueError("Missing or non-finite assumption")
    if min(revenue,shares,roic,terminal_roic)<=0 or not 0<margin<1 or not 0<=tax<1 or not 0<=terminal<wacc or not 0<=growth<roic or terminal>=terminal_roic:
        raise ValueError("Invalid discount, growth, return or denominator")
    rows=[];pv=0.
    for year in range(1,11):
        g=growth if year<=5 else growth+(terminal-growth)*(year-5)/5
        r=roic if year<=5 else roic+(terminal_roic-roic)*(year-5)/5
        revenue*=1+g
        nopat=revenue*margin*(1-tax)
        reinvest=nopat*g/r
        fcff=nopat-reinvest
        discounted=fcff/(1+wacc)**year
        rows.append({"year":year,"revenue":round(revenue,3),"growth":g,"ebitMargin":margin,"nopat":round(nopat,3),"netReinvestment":round(reinvest,3),"fcff":round(fcff,3),"discountedFCFF":round(discounted,3)})
        pv+=discounted
    terminal_nopat=revenue*(1+terminal)*margin*(1-tax)
    terminal_fcff=terminal_nopat*(1-terminal/terminal_roic)
    tv=terminal_fcff/(wacc-terminal)
    tvpv=tv/(1+wacc)**10
    ev=pv+tvpv
    equity=ev-net_debt
    return {"enterpriseValueMillions":round(ev,3),"equityValueMillions":round(equity,3),"perShareUSD":round(equity/shares,2),"terminalValueShare":round(tvpv/ev,4),"projectedCashflows":rows}

def period_values(ledger):
    periods=ledger["periods"]
    if any(abs(check_cash_row(p))>1 for p in periods.values()):raise ValueError("CFO reconciliation failed")
    fy,cur,prev=[periods[k] for k in ("fy","ytd","prior")]
    keys=("revenue","ebit","ni","cfo","capex","sbc","da","interestPaid","borrow","repay","acquisitions")
    ttm={k:fy[k]+cur[k]-prev[k] for k in keys}
    ttm["workingCapitalCashEffect"]=sum(fy["wc"])+sum(cur["wc"])-sum(prev["wc"])
    ttm["reportedFCFE"]=ttm["cfo"]-ttm["capex"]+ttm["borrow"]-ttm["repay"]
    ttm["economicFCFEAfterSBCAndAcquisitions"]=ttm["reportedFCFE"]-ttm["sbc"]-ttm["acquisitions"]
    ttm["historicalFCFFCashBridgeBeforeOtherNonoperatingAdjustments"]=round(ttm["cfo"]-ttm["capex"]-ttm["sbc"]+ttm["interestPaid"]*(1-ledger["guidance"]["gaapTax"]),3)
    return ttm

def build(ledger,raw,research,asof):
    c=next((x for x in research.get("companies",[]) if x.get("ticker")=="ADBE"),None)
    rawc=next((x for x in raw.get("companies",[]) if x.get("ticker")=="ADBE"),None)
    latest=max([r.get("end","") for r in (rawc or {}).get("facts",{}).get("operating_cash_flow",[]) if r.get("form") in ("10-K","10-Q")],default="")
    expected=ledger["periods"]["ytd"]["end"]
    b=ledger["balance"];ttm=period_values(ledger)
    if abs(b["assets"]-b["liabilities"]-b["equity"])>1:raise ValueError("Balance sheet does not tie")
    # Compare FY/YTD/prior values directly to raw SEC facts where the exact tag is present.
    comparisons=[];fail=[]
    tagmap={"operating_cash_flow":"cfo","property_capex":"capex","stock_compensation":"sbc","operating_income":"ebit","net_income":"ni"}
    for key,p in ledger["periods"].items():
        for tag,field in tagmap.items():
            matching=[r for r in (rawc or {}).get("facts",{}).get(tag,[]) if r.get("end")==p["end"] and r.get("start") and (330<=(date.fromisoformat(r["end"])-date.fromisoformat(r["start"])).days<=380 if key=="fy" else 240<=(date.fromisoformat(r["end"])-date.fromisoformat(r["start"])).days<=290)]
            if not matching:continue
            fact=max(matching,key=lambda r:r.get("filed",""))
            delta=fact["val"]/1e6-p[field]
            comparisons.append({"period":p["end"],"field":field,"differenceMillions":delta,"accn":fact.get("accn")})
            if abs(delta)>1.1:fail.append("XBRL_CONFLICT:"+field+":"+p["end"])
    source_date=raw.get("retrievedAt")
    source_fresh=False
    try:source_fresh=0<=(asof-date.fromisoformat(source_date[:10])).days<=7
    except (TypeError,ValueError):pass
    if not source_fresh:fail.append("SEC_REFRESH_STALE")
    if not c or not rawc or latest!=expected:fail.append("NEW_OR_MISSING_FILING_RECONCILIATION_REQUIRED")
    if len(comparisons)<6:fail.append("INSUFFICIENT_XBRL_CROSSCHECKS")
    if (asof-date.fromisoformat(expected)).days>125:fail.append("DOCUMENTED_QUARTER_STALE")
    reserve=ttm["revenue"]*ledger["policy"]["operatingCashReservePct"]
    net_debt=b["debtCurrent"]+b["debtLong"]-max(0,b["cash"]+b["investments"]-reserve)
    shares=max(b["sharesAtBalance"],b["quarterDiluted"])
    # Independent analyst scenarios: first five years anchored below / near management ARR outlook.
    cases={"downside":(.05,.30,.20,.12,.02),"central":(.08,.35,.30,.10,.025),"upside":(.105,.38,.40,.09,.03)}
    scenarios={}
    for name,(g,m,roic,wacc,t) in cases.items():
        result=dcf(ttm["revenue"],m,ledger["guidance"]["gaapTax"],g,roic,wacc,t,ledger["policy"]["terminalROIC"],net_debt,shares)
        scenarios[name]={"assumptions":{"growth":g,"margin":m,"incrementalROIC":roic,"WACC":wacc,"terminalGrowth":t,"tax":ledger["guidance"]["gaapTax"],"terminalROIC":ledger["policy"]["terminalROIC"]},**result}
    low,mid,high=[scenarios[x]["perShareUSD"] for x in cases]
    if not 0<low<mid<high:fail.append("SCENARIO_ORDER")
    if any(x["terminalValueShare"]>.80 for x in scenarios.values()):fail.append("TERMINAL_VALUE_DOMINATES")
    sens=[]
    for w in (.08,.09,.10,.11,.12):
        vals=[dcf(ttm["revenue"],.35,ledger["guidance"]["gaapTax"],.08,.30,w,t,.20,net_debt,shares)["perShareUSD"] for t in (.015,.02,.025,.03,.035)]
        sens.append({"wacc":w,"values":vals})
    # Trigger is a research threshold, not an approved buy price.
    threshold=round(mid*(1-ledger["policy"]["marginOfSafety"]),2) if not fail else None
    return {"schema":1,"ticker":"ADBE","asOf":asof.isoformat(),"sourceRetrievedAt":source_date,"financialPeriod":expected,
       "status":"research_model_current" if not fail else "review_required","blockingIssues":fail,"sources":ledger["sources"],
       "ttmMillions":ttm,"netDebtReportedMillions":b["debtCurrent"]+b["debtLong"]-b["cash"]-b["investments"],"minimumCashAssumptionMillions":reserve,"netDebtForDCFMillions":net_debt,"sharesMillions":shares,
       "checks":{"cashFlowTieouts":{k:check_cash_row(v) for k,v in ledger["periods"].items()},"balanceSheetTieout":b["assets"]-b["liabilities"]-b["equity"],"xbrlComparisons":comparisons},
       "guidance":ledger["guidance"],"scenarios":scenarios,"sensitivity":{"terminalGrowth":[.015,.02,.025,.03,.035],"rows":sens},
       "reviewThresholdUSD":threshold,"marginOfSafetyAssumption":ledger["policy"]["marginOfSafety"],"decisionReady":False,
       "limitations":ledger["notes"]+["FCFE is a historical reported cash measure; cash flows include non-operating items. Forecast is FCFF from GAAP operating margin, normalized taxes and incremental ROIC; reinvestment g/ROIC is an assumption, not measured historical ROIC. Scenario WACC is not a calibrated market WACC. When a later filing appears, the threshold is disabled until documentary bridge is refreshed. No trading or purchase approval."]}

if __name__=="__main__":
    from pathlib import Path
    import json
    base=Path("investment-radar/v2/data")
    load=lambda name:json.loads((base/name).read_text())
    out=build(load("adbe-reviewed-evidence.json"),load("sec-financial-facts.json"),load("fundamental-research.json"),date.today())
    (base/"adbe-fcff-review.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print("Adobe review model:",out["status"],out["blockingIssues"],"range",[x["perShareUSD"] for x in out["scenarios"].values()],"threshold",out["reviewThresholdUSD"])
