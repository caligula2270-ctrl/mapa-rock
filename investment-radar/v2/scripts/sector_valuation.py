"""Sector-aware indicative intrinsic value scenarios with strict research gates.
Not a price target unless critical reconciliations and evidence are approved.
"""
from __future__ import annotations
from statistics import median
import math

SECTOR={
 "software":{"method":"dcf_owner_proxy","discount":.105,"growth":.07,"terminal":.03,"margin":.25},
 "payments":{"method":"dcf_owner_proxy","discount":.10,"growth":.065,"terminal":.03,"margin":.25},
 "exchange":{"method":"dcf_owner_proxy","discount":.10,"growth":.04,"terminal":.025,"margin":.30},
 "digital_platform":{"method":"dcf_owner_proxy","discount":.12,"growth":.05,"terminal":.025,"margin":.35},
 "distribution":{"method":"dcf_owner_proxy","discount":.115,"growth":.035,"terminal":.025,"margin":.30},
 "insurance":{"method":"adjusted_book_required","discount":None,"growth":None,"terminal":None,"margin":.30},
 "industrial":{"method":"sum_of_parts_required","discount":None,"growth":None,"terminal":None,"margin":.30},
}
def discounted_proxy(cash,shares,discount,growth,terminal,years=10):
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (cash,shares,discount,growth,terminal)):
        return None
    if cash<=0 or shares<=0 or discount<=terminal or discount<=0:return None
    pv=sum(cash*(1+growth)**i/(1+discount)**i for i in range(1,years+1))
    end_cash=cash*(1+growth)**years
    terminal_value=end_cash*(1+terminal)/(discount-terminal)/(1+discount)**years
    return round((pv+terminal_value)/shares,2)
def valuation(fin:dict, fundamental:dict)->dict:
    ticker=fin["ticker"];cat=fin["category"];policy=SECTOR.get(cat)
    if not policy:raise ValueError("Sector without appropriate method")
    h=fin["fiscalHistory"];cur=h[0] if h else None
    issues=[]
    if not cur:issues.append("NO_FINANCIAL_HISTORY")
    if fundamental.get("status")=="blocked":issues.append("FUNDAMENTAL_DATA_BLOCKED")
    if not fin["coverage"]["ownerCashProxy3FY"]:issues.append("OWNER_CASH_PROXY_3FY_MISSING")
    if not fin["coverage"]["debtFullyReconciled"]:issues.append("NET_DEBT_UNRECONCILED")
    if not fin["coverage"]["dilutedSharesLatest"]:issues.append("DILUTED_SHARE_COUNT_MISSING")
    if cat=="insurance":issues.append("INSURANCE_RESERVES_AND_BOOK_BRIDGE_REQUIRED")
    if cat=="industrial":issues.append("INDUSTRIAL_CAPTIVE_FINANCE_SEGMENTS_REQUIRED")
    if cat=="digital_platform":issues.append("AI_CAPEX_AND_GROWTH_REINVESTMENT_REQUIRED")
    if cat=="exchange":issues.append("CLEARING_ASSETS_NOT_SHAREHOLDER_CASH")
    if cat=="distribution":issues.append("WORKING_CAPITAL_AND_MA_NORMALIZATION")
    if cat in ("software","payments"):issues.append("SBC_BUYBACKS_AND_SHARE_COUNT_RECONCILIATION")
    # Even perfect deterministic accounting cannot establish competitive moat or approval.
    issues+=["MOAT_EVIDENCE_AND_NORMALIZED_ROIC_REQUIRED","SCENARIO_ASSUMPTIONS_UNDERWRITING_REQUIRED"]
    owners=[v["cashFlow"]["ownerCashProxyAfterSBC"] for v in h[:3]]
    cash=median(owners) if len(owners)==3 and all(v is not None and v>0 for v in owners) else None
    shares=cur["shareCapital"]["weightedDilutedShares"] if cur else None
    model={"ticker":ticker,"category":cat,"model":policy["method"],
           "status":"not_validated","decisionReady":False,"priceTarget":None,"purchasePrice":None,
           "hardGates":list(dict.fromkeys(issues)),"scenarios":None,
           "source":"Audited SEC as-filed annual cash flows; no forecast consensus or subjective moat"}
    if cash is None or shares is None or policy["method"]!="dcf_owner_proxy":
        return model
    # Diagnostic sensitivities: in contrast to an enterprise DCF, these exclude
    # debt financing and cannot equate to the intrinsic fair value of equity.
    discount,growth,terminal=policy["discount"],policy["growth"],policy["terminal"]
    scenarios={}
    for name,mult,g_offset,d_offset in (("conservative",.8,-.025,.015),
                                       ("central",1.,0.,0.),
                                       ("optimistic",1.15,.02,-.01)):
        d=discount+d_offset;g=max(0.,growth+g_offset);t=terminal
        v=discounted_proxy(cash*mult,shares,d,g,t)
        scenarios[name]={"illustrativePricePerShare":v,"normalizedOwnerCashProxy":round(cash*mult,2),
                         "discountRate":round(d,4),"growthAssumption":round(g,4),
                         "terminalGrowth":t,"assumedDilutedShares":shares,
                         "classification":"diagnostic_only_not_intrinsic_value"}
    model["scenarios"]=scenarios
    model["assumptions"]={"explicitlyIllustrative":True,"years":10,
                          "baseOwnerCashProxy3FYMedian":cash,"sector":cat,
                          "noDebtEquityBridge":True,"noDilutionForecast":True,
                          "noMoatROICProof":True,
                          "terminalSensitivityRisk":"Material: not independently validated"}
    return model

def create_report(financial:dict,research:dict)->dict:
    idx={x["ticker"]:x for x in research["companies"]}
    models=[valuation(c,idx[c["ticker"]]) for c in financial["financials"]]
    return {"schema":1,"engine":"sector-valuation-gated-v1",
            "retrievedAt":financial.get("sourceRetrievedAt"),
            "warning":"SCENARIOS ARE ILLUSTRATIVE DIAGNOSTICS, NOT FAIR VALUES OR BUY PRICES",
            "modelPolicies":SECTOR,"companies":models,
            "summary":{"covered":len(models),
                       "modelsWithScenarios":sum(m["scenarios"] is not None for m in models),
                       "decisionReady":sum(m["decisionReady"] for m in models),
                       "closedValuations":sum(m["priceTarget"] is not None for m in models)}}
