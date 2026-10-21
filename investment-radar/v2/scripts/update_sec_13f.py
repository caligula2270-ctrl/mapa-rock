#!/usr/bin/env python3
"""Collect official SEC 13F information tables and compare consecutive filing periods.
Latest positions are kept as raw SEC line items; share-change comparisons are
aggregated per CUSIP for ordinary SH holdings only. 13F isn't a live portfolio.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
if "@" not in USER_AGENT or "example" in USER_AGENT.lower():
    raise SystemExit("Configure SEC_USER_AGENT in repository Actions secrets with a valid contact.")
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml"}
MANAGERS = {
    "Berkshire Hathaway": 1067983,
    "Bridgewater Associates": 1350694,
    "Pershing Square": 1336528,
    "Baupost Group": 1061768,
    "Duquesne Family Office": 1536411,
    "Appaloosa Management": 1656456,
}
OUTFILE = Path("investment-radar/v2/data/latest-13f.json")


def fetch(url):
    with urlopen(Request(url, headers=HEADERS), timeout=40) as response:
        content = response.read()
    time.sleep(0.18)
    return content


def text(element, tag):
    for node in element.iter():
        if node.tag.rsplit("}", 1)[-1].lower() == tag.lower():
            return (node.text or "").strip()
    return ""


def filing_periods(cik):
    submission = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    rec = submission["filings"]["recent"]
    by_period = {}
    for i, form in enumerate(rec["form"]):
        # A 13F-HR/A can be a partial NEW HOLDINGS amendment. Do not treat it
        # as a complete quarter or silently merge it with the original filing.
        if form != "13F-HR":
            continue
        period = rec["reportDate"][i]
        if not period or period in by_period:
            continue
        by_period[period] = {
            "period": period, "filedAt": rec["filingDate"][i],
            "accession": rec["accessionNumber"][i].replace("-", ""),
            "form": form,
        }
    return sorted(by_period.values(), key=lambda f: f["period"], reverse=True)[:2]


def parse_table(cik, manager, filing):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{filing['accession']}/"
    folder = json.loads(fetch(base + "index.json"))
    candidates = [
        x["name"] for x in folder["directory"]["item"]
        if x["name"].lower().endswith(".xml")
    ]
    # SEC directories can include cover documents and XML metadata.
    candidates.sort(key=lambda n: (
        0 if any(k in n.lower() for k in ("infotable", "informationtable", "13f_")) else 1,
        len(n),
    ))
    largest, evidence = [], None
    for name in candidates[:35]:
        try:
            url = base + quote(name)
            root = ET.fromstring(fetch(url))
            rows = []
            for row in root.iter():
                if row.tag.rsplit("}", 1)[-1].lower() != "infotable":
                    continue
                cusip = text(row, "cusip").upper().replace(" ", "")
                issuer = text(row, "nameOfIssuer")
                if not re.fullmatch("[A-Z0-9]{9}", cusip) or not issuer:
                    continue
                shares_text = text(row, "sshPrnamt").replace(",", "")
                amount_type = text(row, "sshPrnamtType").upper() or "UNKNOWN"
                option = text(row, "putCall").upper()
                try:
                    shares = float(shares_text) if shares_text else None
                except ValueError:
                    shares = None
                rows.append({
                    "manager": manager, "period": filing["period"],
                    "filedAt": filing["filedAt"], "cusip": cusip,
                    "issuer": issuer, "company": issuer, "ticker": None,
                    "shares": shares, "amountType": amount_type,
                    "putCall": option or None, "filingUrl": url, "type": "13F",
                })
            if len(rows) > len(largest):
                largest, evidence = rows, url
        except (ET.ParseError, OSError, ValueError):
            continue
    if not largest:
        raise ValueError(f"No verified 13F information table for {manager} / {filing['period']}")
    return largest, evidence


def group_shares(rows):
    """Sum only ordinary reported share lines by CUSIP; never include options/PRN."""
    by_cusip = {}
    for item in rows:
        if item.get("putCall") or item.get("amountType") != "SH":
            continue
        if item["shares"] is None or item["shares"] < 0:
            continue
        key = item["cusip"]
        if key not in by_cusip:
            by_cusip[key] = {
                "cusip": key, "issuer": item["issuer"], "shares": 0,
                "lineCount": 0, "manager": item["manager"],
                "period": item["period"], "filingUrl": item["filingUrl"],
            }
        by_cusip[key]["shares"] += item["shares"]
        by_cusip[key]["lineCount"] += 1
    return by_cusip


def compute_changes(manager, latest, prior, current_period, previous_period):
    left, right = group_shares(prior), group_shares(latest)
    changes = []
    for cusip in sorted(left.keys() | right.keys()):
        a, b = left.get(cusip), right.get(cusip)
        prev, now = (a["shares"] if a else 0), (b["shares"] if b else 0)
        if prev == now:
            continue
        # A disappearance from a 13F is NOT proof that the stock was sold.
        category = ("newly_reported" if not a else
                    "no_longer_reported" if not b else
                    "increase" if now > prev else "decrease")
        changes.append({
            "manager": manager, "period": current_period,
            "previousPeriod": previous_period, "cusip": cusip,
            "issuer": (b or a)["issuer"], "category": category,
            "previousShares": prev, "currentShares": now,
            "deltaShares": now - prev,
            "deltaPct": round(100 * (now / prev - 1), 2) if prev else None,
            "filingUrl": (b or a)["filingUrl"],
            "caveat": "Share count not adjusted for splits, transfers or corporate actions.",
        })
    return changes


def main():
    filings, latest_positions, history, changes, errors = [], [], [], [], []
    previous = {}
    if OUTFILE.exists():
        try:
            previous = json.loads(OUTFILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    for manager, cik in MANAGERS.items():
        try:
            matched = filing_periods(cik)
            if not matched:
                raise ValueError("No original 13F-HR reported")
            gathered = []
            for f in matched:
                rows, evidence = parse_table(cik, manager, f)
                summary = {
                    "manager": manager, "cik": cik, "period": f["period"],
                    "filedAt": f["filedAt"], "filingUrl": evidence,
                    "positionCount": len(rows), "form": "13F-HR",
                    "sourceType": "original_13f_hr",
                    "amendmentsReviewed": False,
                }
                gathered.append((summary, rows))
            newest, newest_rows = gathered[0]
            filings.append(newest)
            latest_positions.extend(newest_rows)
            for item, rows in gathered:
                for holding in group_shares(rows).values():
                    history.append(holding)
            if len(gathered) == 2:
                earlier, earlier_rows = gathered[1]
                changes.extend(compute_changes(
                    manager, newest_rows, earlier_rows,
                    newest["period"], earlier["period"]
                ))
        except Exception as exc:
            errors.append({"manager": manager, "error": str(exc)[:240]})
            # Keep last verified snapshot for a manager if a temporary SEC
            # outage occurs; explicitly surface an error and stale metadata.
            former = next((f for f in previous.get("filings", [])
                           if f.get("manager") == manager), None)
            if former:
                filings.append({**former, "stale": True})
                latest_positions.extend(x for x in previous.get("positions", [])
                                        if x.get("manager") == manager)
                history.extend(x for x in previous.get("history", [])
                               if x.get("manager") == manager)
                changes.extend(x for x in previous.get("changes", [])
                               if x.get("manager") == manager)
    if not latest_positions:
        raise SystemExit("No verified SEC positions downloaded. Retaining previous file.")
    payload = {
        "schema": 2,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": "Official SEC EDGAR 13F-HR XML. Raw line items are separate from aggregated SH/CUSIP change indicators. Amendments not merged, tickers/weights not inferred.",
        "filings": filings, "positions": latest_positions,
        "history": history, "changes": changes, "errors": errors,
        "caveats": [
            "Reporting lag; 13F is not real time and may exclude holdings.",
            "Original 13F-HR used; partial amendments not merged. Recheck 13F-HR/A.",
            "Only ordinary SH (not PUT/CALL or PRN) used for share-count comparisons.",
            "Changes are unadjusted for splits/corporate actions. Disappearance is not proof of sale.",
            "Cross-manager overlaps can compare different dates; periods are displayed.",
        ],
    }
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Managers {len(filings)}; raw positions {len(latest_positions)}; "
          f"aggregated holdings {len(history)}; changes {len(changes)}; "
          f"errors {len(errors)}")


if __name__ == "__main__":
    main()
