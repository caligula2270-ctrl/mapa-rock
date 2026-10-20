#!/usr/bin/env python3
"""SEC 13F source adapter; stores CUSIPs without inferring tickers."""
import os,json,re,time,datetime,pathlib,urllib.request,urllib.parse,xml.etree.ElementTree as ET
ua=os.getenv('SEC_USER_AGENT','').strip()
if '@' not in ua or 'example' in ua: raise SystemExit('Configure SEC_USER_AGENT repository secret with a valid organizational contact.')
heads={'User-Agent':ua,'Accept':'application/json, application/xml, text/xml'}
def get(u):
 req=urllib.request.Request(u,headers=heads)
 with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def val(e,n):
 for a in e.iter():
  if a.tag.rsplit('}',1)[-1].lower()==n.lower():return (a.text or '').strip()
 return ''
managers={'Berkshire Hathaway':1067983,'Bridgewater Associates':1350694,'Pershing Square':1336528,'Baupost Group':1061768,'Duquesne Family Office':1536411,'Appaloosa Management':1656456}
filings=[];positions=[];errors=[]
for name,cik in managers.items():
 try:
  d=json.loads(get('https://data.sec.gov/submissions/CIK%010d.json'%cik))
  a=d['filings']['recent']
  ix=next(i for i,f in enumerate(a['form']) if f in ['13F-HR','13F-HR/A'])
  acc=a['accessionNumber'][ix].replace('-','');period=a['reportDate'][ix];filed=a['filingDate'][ix]
  base=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/'
  index=json.loads(get(base+'index.json'))
  names=[p['name'] for p in index['directory']['item'] if p['name'].lower().endswith('.xml')]
  best=[];ref=''
  for filename in names[:35]:
   try:
    u=base+urllib.parse.quote(filename)
    root=ET.fromstring(get(u));rows=[]
    for el in root.iter():
     if el.tag.rsplit('}',1)[-1].lower()!='infotable':continue
     cusip=val(el,'cusip').replace(' ','').upper()
     issuer=val(el,'nameOfIssuer')
     if not re.fullmatch('[A-Z0-9]{9}',cusip) or not issuer:continue
     shares=val(el,'sshPrnamt')
     rows.append({'manager':name,'period':period,'filedAt':filed,'cusip':cusip,'issuer':issuer,'company':issuer,'ticker':None,'shares':float(shares) if shares else None,'filingUrl':u,'type':'13F'})
    if len(rows)>len(best):best,ref=rows,u
   except Exception: pass
   time.sleep(.12)
  if not best:raise ValueError('No verified information table in latest 13F')
  filings.append({'manager':name,'cik':cik,'period':period,'filedAt':filed,'filingUrl':ref,'positionCount':len(best)})
  positions+=best
 except Exception as e:errors.append({'manager':name,'error':str(e)[:200]})
 time.sleep(.25)
if not positions:raise SystemExit('No verified positions; retained prior data. '+repr(errors))
path=pathlib.Path('investment-radar/v2/data/latest-13f.json')
payload={'schema':1,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'SEC EDGAR filed 13F XML; CUSIPs are official; tickers and weights not inferred','filings':filings,'positions':positions,'errors':errors}
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
print('SEC filings',len(filings),'positions',len(positions),'errors',len(errors))
