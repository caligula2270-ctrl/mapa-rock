#!/usr/bin/env python3
"""SEC financial statement normalization and source-to-period tie-out.
Only as-filed values from fundamental_core; no invented balancing items.
"""
from __future__ import annotations
import datetime as dt

def ratio(a,b):
    return round(a/b,8) if a is not None and b is not None and b>0 else None

def normalized_company(c:dict)->dict:
    years=c.get("annual") or []
    result=[]
    issues=[]
    for i,a in enumerate(years):
        prov=a.get("sources",{})
        def val(key):return a.get(key)
        fcf=val("freeCashFlowSimple")
        sbc=val("stockCompensation")
        owner=(fcf-sbc) if fcf is not None and sbc is not None else None
        op=val("operatingIncome")
        rev=val("revenue")
        equity=val("equity")
        assets=val("assets")
        liabilities=val("liabilities")
        # Missing debt facts are unknown, NEVER assumed to be zero.
        debt_parts=(val("currentDebt"),val("longDebt"),val("shortDebt"))
        confirmed_debt=sum(x for x in debt_parts if x is not None)
        complete_debt=all(x is not None for x in debt_parts)
        gross_debt=confirmed_debt if complete_debt else None
        net_debt=(gross_debt-val("cash")) if gross_debt is not None and val("cash") is not None else None
        ids=[(k,v.get("accession")) for k,v in prov.items()
             if k in ("operating_cash_flow","property_capex","revenue_contract","revenue","net_income","diluted_weighted_shares")]
        accessions=set(x[1] for x in ids)
        if len(accessions)>1:
            issues.append({"yearEnd":a["yearEnd"],"code":"MIXED_FILING_ACCESSIONS",
                "severity":"review","detail":"Core SEC metrics for the same period originate in different accession numbers; recheck comparability",
                "accessions":sorted(accessions)})
        if fcf is None:issues.append({"yearEnd":a["yearEnd"],"code":"MISSING_FCF_SOURCE","severity":"block","detail":"CFO or PPE capex absent; simple FCF not computed"})
        if owner is None:issues.append({"yearEnd":a["yearEnd"],"code":"MISSING_OWNER_CASH_PROXY","severity":"block","detail":"SBC, CFO or PPE capex absent"})
        if not complete_debt:issues.append({"yearEnd":a["yearEnd"],"code":"DEBT_TAGS_INCOMPLETE","severity":"review","detail":"One or more debt categories have no SEC tag; net debt cannot be asserted"})
        if val("weightedDilutedShares") is None:issues.append({"yearEnd":a["yearEnd"],"code":"DILUTED_SHARES_MISSING","severity":"block","detail":"Weighted annual diluted shares unavailable"})
        if assets is not None and liabilities is not None and equity is not None and assets>0:
            difference=assets-liabilities-equity
            balance_delta=round(difference/assets,8)
            if abs(balance_delta)>.025:
                issues.append({"yearEnd":a["yearEnd"],"code":"BALANCE_GAP","severity":"review","detail":"Assets - liabilities - equity differs materially; might include noncontrolling interests"})
        else:balance_delta=None
        if i+1<len(years):
            prev=years[i+1]
            prior_revenue=prev.get("revenue")
            revenue_growth=round(rev/prior_revenue-1,7) if rev is not None and prior_revenue and prior_revenue>0 else None
            prior_shares=prev.get("weightedDilutedShares")
            dilution=round(val("weightedDilutedShares")/prior_shares-1,7) if val("weightedDilutedShares") is not None and prior_shares and prior_shares>0 else None
        else:revenue_growth=dilution=None
        row={"fiscalYearEnd":a["yearEnd"],"currency":"USD","filingPeriodsAreFiscalYears":True,
            "incomeStatement":{"revenue":rev,"operatingIncome":op,"netIncome":val("netIncome"),
                "operatingMargin":ratio(op,rev),"revenueYoY":revenue_growth},
            "cashFlow":{"operatingCashFlow":val("operatingCashFlow"),"propertyCapex":val("capex"),
                "simpleFCF":fcf,"stockCompensation":sbc,"ownerCashProxyAfterSBC":owner,
                "capexToRevenue":ratio(val("capex"),rev),"ownerProxyMargin":ratio(owner,rev)},
            "balanceSheet":{"assets":assets,"liabilities":liabilities,"equity":equity,
                "cash":val("cash"),"reportedCurrentDebt":debt_parts[0],
                "reportedLongTermDebt":debt_parts[1],"reportedShortTermBorrowings":debt_parts[2],
                "grossDebt":gross_debt,"netDebt":net_debt,"netDebtCoverageComplete":complete_debt,
                "assetsLessLiabilitiesLessEquityOverAssets":balance_delta},
            "shareCapital":{"weightedDilutedShares":val("weightedDilutedShares"),
                "dilutionYoY":dilution,"simpleFCFPerShare":ratio(fcf,val("weightedDilutedShares")),
                "ownerCashProxyPerShare":ratio(owner,val("weightedDilutedShares")),
                "bookValuePerWeightedDilutedShare":ratio(equity,val("weightedDilutedShares"))},
            "sourceIndex":prov}
        result.append(row)
    first=result[0] if result else None
    cash_series=[r["cashFlow"]["ownerCashProxyAfterSBC"] for r in result[:3]]
    valid_owner=len(cash_series)==3 and all(x is not None and x>0 for x in cash_series)
    shares=first["shareCapital"]["weightedDilutedShares"] if first else None
    financials={"ticker":c["ticker"],"name":c.get("name"),"category":c.get("category"),
        "sourceURL":c.get("sourceURL"),"fiscalHistory":result,"issues":issues,
        "interimYTD":c.get("interimYTD"),
        "coverage":{"annualPeriods":len(result),"ownerCashProxy3FY":valid_owner,
            "debtFullyReconciled":bool(first and first["balanceSheet"]["netDebtCoverageComplete"]),
            "dilutedSharesLatest":bool(shares and shares>0),
            "cashflowSourceAvailable":bool(first and first["cashFlow"]["operatingCashFlow"] is not None),
            "sourceAccessionAvailable":bool(first and first["sourceIndex"])},
        "warnings":["Reported CFO less capex less SBC is an EQUITY-CASH SCREENING PROXY, not FCFE or FCFF.",
            "Debt missing categories are UNKNOWN, not zero.",
            "Fiscal periods and XBRL tag conventions differ between issuers.",
            "The result is not a complete audited three-statement model."]}
    return financials

def normalized_report(research:dict)->dict:
    if research.get("schema")!=1:raise ValueError("Fundamental research schema mismatch")
    companies=[normalized_company(c) for c in research["companies"] if c.get("annual")]
    return {"schema":1,"engine":"SEC-annual-statement-normalizer-v1",
        "sourceRetrievedAt":research.get("sourceRetrievedAt"),
        "periodConvention":"10-K full fiscal periods: do NOT annualize quarters or combine incompatible fiscal periods",
        "financials":companies,
        "summary":{"companies":len(companies),
            "withOwnerCashProxy3FY":sum(c["coverage"]["ownerCashProxy3FY"] for c in companies),
            "debtFullyReconciled":sum(c["coverage"]["debtFullyReconciled"] for c in companies),
            "completeDilutedShares":sum(c["coverage"]["dilutedSharesLatest"] for c in companies),
            "qualityFlags":sum(len(c["issues"]) for c in companies)}}
