"""Cost-free autonomous fundamental analyst with evidence-gated estimates.
Receives normalized audited SEC fundamentals, source-linked balance reconciliations,
sector diagnostics. Emits RESEARCH, not personalized investment instructions.
No prices or investment recommendations are invented.
"""
from __future__ import annotations
from datetime import date
from statistics import median
from math import isfinite

CONFIG={
 "software":{"equity_discount":.105,"growth_cap":.12,"terminal":.025,"base_growth":.05,"method":"owner_cash_proxy_equity_dcf"},
 "payments":{"equity_discount":.105,"growth_cap":.11,"terminal":.025,"base_growth":.05,"method":"owner_cash_proxy_equity_dcf"},
 "exchange":{"equity_discount":.105,"growth_cap":.07,"terminal":.025,"base_growth":.035,"method":"owner_cash_proxy_equity_dcf"},
 "digital_platform":{"equity_discount":.12,"growth_cap":.10,"terminal":.025,"base_growth":.05,"method":"owner_cash_proxy_equity_dcf"},
 "distribution":{"equity_discount":.115,"growth_cap":.065,"terminal":.025,"base_growth":.035,"method":"owner_cash_proxy_equity_dcf"},
 "insurance":{"method":"adjusted_book_and_normalized_core_roe_required"},
 "industrial":{"method":"sum_of_industrial_finance_parts_required"}
}

def cash_dcf(cash:float, shares:float, discount:float, growth:float, terminal:float,years=10):
    """Equity-cash-flow proxy sensitivity ONLY. No debt valuation bridge."""
    if not all(isinstance(v,(float,int)) and isfinite(v) for v in [cash,shares,discount,growth,terminal]):return None
    if cash<=0 or shares<=0 or discount<=terminal or discount<=0 or growth<=-.99 or terminal<0:return None
    # Two-stage 10yr fade toward terminal growth, fixed over first five years.
    flows=[]
    current=cash
    for t in range(1,years+1):
        g=growth if t<=5 else growth+(terminal-growth)*(t-5)/(years-5)
        current*=1+g
        flows.append(current/(1+discount)**t)
    horizon_cash=current
    residual=horizon_cash*(1+terminal)/(discount-terminal)/(1+discount)**years
    return round((sum(flows)+residual)/shares,4)

def choose_growth(history,policy):
    observed=[]
    for i in range(min(3,len(history)-1)):
        now=history[i]["incomeStatement"]["revenue"]
        before=history[i+1]["incomeStatement"]["revenue"]
        if now is not None and before is not None and before>0:
            observed.append(now/before-1)
    if len(observed)<2:return None,observed
    raw=median(observed)
    # Floors negative trend at -5%, caps implausible extrapolation.
    bounded=max(-.05,min(policy["growth_cap"],raw))
    return round(.5*bounded+.5*policy["base_growth"],5),observed

def analyze(fin,source,bridge,asof:date):
    ticker=fin["ticker"];h=fin["fiscalHistory"]
    sector=fin["category"];p=CONFIG[sector];gates=[];checks={}
    if not h:return {"ticker":ticker,"status":"not_assessable","gates":["NO_FISCAL_HISTORY"],"scenarios":None,"decisionReady":False}
    fy=h[0]
    def gate(code,flag):checks[code]=bool(flag);gates.append(code) if not flag else None
    age=(asof-date.fromisoformat(fy["fiscalYearEnd"])).days
    gate("FISCAL_YEAR_CURRENT",age>=0 and age<=470)
    gate("SEC_PRIMARY_SOURCE",bool(source.get("sourceURL")) and bool(fy.get("sourceIndex")))
    gate("THREE_ANNUAL_CASH_PERIODS",fin["coverage"]["ownerCashProxy3FY"] and len(h)>=3)
    gate("DILUTED_SHARES_PRESENT",fin["coverage"]["dilutedSharesLatest"])
    gate("NET_DEBT_DOCUMENTED",bool(bridge and bridge.get("balance") and bridge["balance"]["date"]==fy["fiscalYearEnd"]))
    if bridge and bridge.get("balance"):
        b=bridge["balance"]
    yr_cash=fy["balanceSheet"]["cash"]
    raw_bridge_cash=(bridge or {}).get("balance",{}).get("cashRawMillions")
    if raw_bridge_cash is not None and yr_cash is not None:
        gate("REPORTED_CASH_RECONCILED",abs(raw_bridge_cash-yr_cash/1e6)<max(.2,yr_cash/1e6*.001))
    else:gate("REPORTED_CASH_RECONCILED",False)
    if bridge and bridge.get("balance"):
        w=bridge["balance"].get("weightedDilutedSharesMillions")
        shares=fy["shareCapital"]["weightedDilutedShares"]
        gate("DILUTED_SHARES_TIED",shares is not None and w is not None and abs(w-shares/1e6)/max(w,1)<.015)
    else:gate("DILUTED_SHARES_TIED",False)
    gate("CAPEX_VALID",all(v["cashFlow"]["propertyCapex"] is not None for v in h[:3]))
    gate("NO_MATERIAL_SOURCE_GAPS",not any(x["severity"]=="block" for x in fin["issues"] if x["yearEnd"]==fy["fiscalYearEnd"]))
    gate("NO_FUNDAMENTAL_BLOCK",source.get("status")!="blocked")
    tags=set((x["code"] for x in source.get("issues",[])))
    gate("NO_REVENUE_CONFLICT","REVENUE_TAG_CONFLICT" not in tags)
    gate("NO_MAJOR_MARGIN_SHOCK","OPERATING_MARGIN_DROP" not in tags)
    gate("CURRENT_QUARTER_REVIEWED",source.get("interimYTD") is None)
    gate("SECTOR_ACCOUNTING_BRIDGE",False)
    gate("MOAT_ROIC_EVIDENCE",False)
    gate("FORWARD_REINVESTMENT_FORECAST",False)
    gate("COST_OF_EQUITY_CALIBRATION",False)
    # No output can be marked decision grade on unreviewed underwriting.
    scenarios=None;sensitivity=None
    growth,observed=choose_growth(h,p) if "equity_discount" in p else (None,[])
    owner=[x["cashFlow"]["ownerCashProxyAfterSBC"] for x in h[:3]]
    shares=fy["shareCapital"]["weightedDilutedShares"]
    if growth is not None and len(owner)==3 and all(x is not None and x>0 for x in owner) and shares and shares>0:
        basis=median(owner)
        rate=p["equity_discount"];terminal=p["terminal"]
        case_params={
            "downside":{"initialCashFactor":.75,"discount":rate+.02,"growth":max(-.05,growth-.035)},
            "central":{"initialCashFactor":1.,"discount":rate,"growth":growth},
            "upside":{"initialCashFactor":1.2,"discount":max(terminal+.035,rate-.015),"growth":min(p["growth_cap"],growth+.025)}
        }
        scenarios={}
        for name,x in case_params.items():
            v=cash_dcf(basis*x["initialCashFactor"],shares,x["discount"],x["growth"],terminal)
            scenarios[name]={"illustrativeCashFlowProxyPerShareUSD":v,
                "assumptions":{"normalizedCashUSD":round(basis*x["initialCashFactor"],2),
                    "discountRate":x["discount"],"annualGrowth":x["growth"],"terminalGrowth":terminal,
                    "shares":shares,"horizonYears":10}}
        sens=[]
        for discount in [rate-.02,rate-.01,rate,rate+.01,rate+.02]:
            vals=[]
            for delta in [-.04,-.02,0,.02,.04]:
                vals.append(cash_dcf(basis,shares,discount,max(-.05,min(p["growth_cap"],growth+delta)),terminal))
            sens.append({"discount":round(discount,4),"values":vals})
        sensitivity={"growthDeltas":[-.04,-.02,0,.02,.04],"rows":sens}
        low=scenarios["downside"]["illustrativeCashFlowProxyPerShareUSD"]
        mid=scenarios["central"]["illustrativeCashFlowProxyPerShareUSD"]
        high=scenarios["upside"]["illustrativeCashFlowProxyPerShareUSD"]
        gate("SCENARIO_ORDER_VALID",low is not None and mid is not None and high is not None and low<mid<high)
        gate("SENSITIVITY_FINITE",all(v is not None and 0<v<1e7 for row in sens for v in row["values"]))
    else:
        gate("VALUATION_INPUTS_COMPLETE",False)
    if sector=="insurance":
        gate("INSURANCE_RESERVES_AND_ROE",False)
    if sector=="industrial":
        gate("CAPTIVE_FINANCE_SEPARATED",False)
    if sector=="digital_platform":
        gate("AI_CAPEX_SCENARIOS_UNDERWRITTEN",False)
    warnings=[]
    if fy["cashFlow"]["ownerCashProxyAfterSBC"] is not None:
        rev=fy["incomeStatement"]["revenue"]
        if rev and fy["cashFlow"]["ownerCashProxyAfterSBC"]/rev<.05:warnings.append("LATEST_YEAR_OWNER_PROXY_MARGIN_BELOW_5PCT")
    cap=fy["cashFlow"]["propertyCapex"];rev=fy["incomeStatement"]["revenue"]
    if rev and cap and cap/rev>.2:warnings.append("CAPEX_OVER_20PCT_OF_REVENUE")
    if age>350:warnings.append("FULL_YEAR_REPORT_OLDER_THAN_350_DAYS")
    return {"ticker":ticker,"name":fin["name"],"sector":sector,"model":p["method"],
       "asOf":asof.isoformat(),"lastFiscalYear":fy["fiscalYearEnd"],
       "latestInterimYTD":source.get("interimYTD",{}).get("end") if source.get("interimYTD") else None,
       "evidence":{"sourceURL":source.get("sourceURL"),
           "normalizedFactsAccession":fy["sourceIndex"].get("operating_cash_flow",{}).get("accession"),
           "balanceBridgeURL":(bridge or {}).get("balance",{}).get("sourceURL")},
       "revenueGrowth3FY":observed,"assumptions":{"growthMethod":"median of recent YoY revenue changes, capped by sector; blended 50% sector baseline",
         "blendedForwardGrowth":growth,"sectorPolicy":p,
         "cashBasis":"median of 3 annual (CFO minus PPE capex minus SBC) proxies; NOT verified FCFE or FCFF",
         "missingOwnerCashTreatment":"no projection"},
       "scenarios":scenarios,"sensitivity":sensitivity,
       "checks":checks,"hardGates":gates,"warnings":warnings,
       "readiness":"blocked" if any(not checks[c] for c in ("FISCAL_YEAR_CURRENT","SEC_PRIMARY_SOURCE","THREE_ANNUAL_CASH_PERIODS","DILUTED_SHARES_PRESENT","NO_FUNDAMENTAL_BLOCK")) else "research_only",
       "decisionReady":False,"approvedFairValueUSD":None,"approvedEntryPriceUSD":None,
       "summary":"Automated cash proxy scenarios for research. Sector ROIC, moat, cost of capital, reinvestment and equity reconciliation require independent evidence."}

def make_report(financials,raw,filing,asof):
    source={x["ticker"]:x for x in raw["companies"]}
    audits={x["ticker"]:x for x in filing.get("companies",[])}
    arr=[analyze(f,source[f["ticker"]],audits.get(f["ticker"]),asof) for f in financials["financials"]]
    arr.sort(key=lambda x:x["ticker"])
    return {"schema":1,"model":"research-analyst-evidence-gated-v1","asOf":asof.isoformat(),
      "sourceRetrievedAt":raw.get("sourceRetrievedAt"),
      "policy":"ZERO automatic buy/entry recommendations; values are diagnostics only.",
      "companies":arr,
      "summary":{"covered":len(arr),"withDiagnostics":sum(x["scenarios"] is not None for x in arr),
        "blocked":sum(x["readiness"]=="blocked" for x in arr),"researchOnly":sum(x["readiness"]=="research_only" for x in arr),
        "approved":0,"warnings":sum(len(x["warnings"]) for x in arr)}}
