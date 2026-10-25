(()=>{'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','&#39;':'&#39;'}[c]));
const num=x=>typeof x==='number'&&Number.isFinite(x)?new Intl.NumberFormat('es-ES',{maximumFractionDigits:2}).format(x):'—';
const money=x=>typeof x==='number'&&Number.isFinite(x)?num(x/1e6)+' MUSD':'—';
const pct=x=>typeof x==='number'&&Number.isFinite(x)?num(100*x)+'%':'—';
let dataset=null;
const CATEGORY={software:'Software',payments:'Redes de pagos',insurance:'Seguros',exchange:'Mercados financieros',digital_platform:'Plataforma digital',distribution:'Distribución industrial',industrial:'Industria y financiera cautiva'};
const issueNames={
 NO_ANNUAL_CFO:'Caja operativa anual no disponible',STALE_REPORT:'Cuentas desactualizadas',
 INSUFFICIENT_ANNUAL_FCF:'Faltan tres años de FCF anual',MISSING_CAPEX:'CAPEX oficial ausente',
 MISSING_DILUTED_SHARES:'Acciones diluidas no conciliadas',INVALID_SHARES:'Acciones diluidas inválidas',
 SECTOR_INSURANCE_MODEL:'Seguros: no se admite CFO−CAPEX como caja del accionista',
 FINANCE_ARM_SEGMENT:'Separar maquinaria y financiera cautiva',
 CLEARING_CLIENT_ASSETS:'Colateral de clientes no es caja propia',
 AI_CAPEX_NORMALIZATION:'Normalizar reinversión de infraestructura IA',
 WORKING_CAPITAL_CYCLE:'Normalizar capital circulante y ciclo',
 STOCK_COMP_AND_DEBT:'Conciliar remuneración en acciones, deuda y recompras',
 REVENUE_TAG_CONFLICT:'Etiquetas de ingresos discordantes',
 BALANCE_MISMATCH:'Balance contable requiere conciliación',
 NEGATIVE_FCF:'FCF simple negativo',DILUTION_15PCT:'Incremento importante de acciones diluidas',
 INTERIM_FCF_NOT_COMPARABLE:'Flujo de caja interino incompleto o períodos no comparables',
 INTERIM_PERIOD_NOT_IN_FY_SCREEN:'Existe información 10-Q reciente fuera del último ejercicio anual',
 OPERATING_CASH_COLLAPSE:'Caída de caja operativa superior al 30% interanual',
 FCF_DROP_40PCT:'FCF simple cae más del 40% interanual',
 OPERATING_MARGIN_DROP:'Caída del margen operativo superior a 5 puntos',
 HIGH_STOCK_COMP:'Remuneración en acciones >30% de caja operativa',
 SEC_DOWNLOAD_MISSING:'Falta descarga oficial SEC'
};
function url(x){return typeof x==='string'&&x.startsWith('https://data.sec.gov/')?x:null}
function latest(c){return c.annual?.[0]||null}
function issue(c){
 const severe=(c.issues||[]).filter(x=>x.severity==='block');
 return severe.length?'<b class="bad">'+severe.length+' bloqueo(s)</b>':'<b class="caution">Revisión obligatoria</b>';
}
function metrics(c){
 const a=latest(c);if(!a)return '<p class="dim">Sin cuentas anuales normalizadas verificadas.</p>';
 const items=[['Ingresos',money(a.revenue)],['Resultado operativo',money(a.operatingIncome)],
 ['Caja operativa',money(a.operatingCashFlow)],['CAPEX tangible',money(a.capex)],
 ['FCF simple',money(a.freeCashFlowSimple)],['Acciones diluidas medias',num(a.weightedDilutedShares)],
 ['Margen operativo',pct(a.operatingMargin)],['FCF / ingresos',pct(a.freeCashFlowMargin)],
 ['Conversión de caja',num(a.cashConversion)+'×']];
 return '<div class="cols"><div><h3>Último ejercicio anual ('+esc(a.yearEnd)+')</h3><ul>'+items.map(x=>'<li><b>'+esc(x[0])+':</b> '+x[1]+'</li>').join('')+'</ul></div>'+
 '<div><h3>Auditoría y controles</h3><ul>'+c.issues.map(x=>'<li class="issue"><span class="'+(x.severity==='block'?'bad':'caution')+'">'+esc(x.severity)+'</span>: '+esc(issueNames[x.code]||x.detail||x.code)+(x.period?' ('+esc(x.period)+')':'')+'</li>').join('')+'</ul></div></div>';
}
function sources(c){
 const a=latest(c);if(!a)return '';
 const fields=['operating_cash_flow','property_capex','revenue_contract','revenue','diluted_weighted_shares'];
 return '<h3>Trazabilidad de cifras</h3><div class="scroller"><table><thead><tr><th>Concepto SEC</th><th>Período</th><th>Presentado</th><th>Expediente / unidad</th></tr></thead><tbody>'+
 fields.filter(k=>a.sources?.[k]).map(k=>{const x=a.sources[k];return '<tr><td>'+esc(k)+'</td><td>'+esc(x.start||'instant')+' a '+esc(x.end)+'</td><td>'+esc(x.filed)+'</td><td>'+esc(x.accession)+' · '+esc(x.unit)+'</td></tr>'}).join('')+
 '</tbody></table></div>';
}
function interim(c){
 const y=c.interimYTD;
 if(!y)return '<p class="fine">No consta un 10-Q interino posterior al último ejercicio 10-K con flujo operativo anual acumulado identificable.</p>';
 const m=y.metrics||{};
 return '<div class="banner"><h3>Datos posteriores al ejercicio · 10-Q original</h3><p><b>Período interino YTD, no anualizado:</b> '+esc(y.start)+' a '+esc(y.end)+' · presentación '+esc(y.filed)+'</p>'+
 '<p>Caja operativa '+money(m.operatingCashFlow)+'; CAPEX '+money(m.capex)+'; FCF simple interino '+money(m.freeCashFlowSimple)+'.</p>'+
 '<p class="fine">Estas cifras trimestrales/acumuladas no se convierten automáticamente en TTM ni se extrapolan: la estacionalidad y el CAPEX pueden ser importantes.</p></div>';
}
function screening(c){
 const s=c.screening;if(!s)return '<p class="bad">No se calcula siquiera un cribado de FCF por falta de datos suficientes o por incompatibilidad sectorial.</p>';
 const ys=s.illustrativeAtYields;
 return '<h3>Sensibilidad matemática — NO es valor intrínseco</h3><p>Mediana de FCF simple de los últimos tres ejercicios: <b>'+money(s.normalized3FYFCF)+'</b>, por acción diluida media del último ejercicio: <b>'+num(s.proxyFCFPerWeightedDilutedShare)+' USD</b>.</p>'+
 '<p class="fine">Precio hipotético por división FCF/acción entre un rendimiento exigido constante, sin crecimiento ni conciliación de financiación:</p>'+
 '<div class="scroller"><table><thead><tr><th>FCF yield 10%</th><th>FCF yield 8%</th><th>FCF yield 6%</th></tr></thead><tbody><tr><td>'+num(ys['0.10'])+' USD</td><td>'+num(ys['0.08'])+' USD</td><td>'+num(ys['0.06'])+' USD</td></tr></tbody></table></div>'+
 '<p class="fine"><b>No es FCFE, no es un DCF, no es precio de compra.</b> Falta deuda, caja atribuible, dilución normalizada, necesidades de reinversión y previsiones por negocio.</p>';
}
function detail(c){
 const head='<summary>'+esc(c.ticker)+' · '+esc(c.name)+' — '+(c.status==='blocked'?'DATOS/MODELO BLOQUEADOS':'REVISIÓN OBLIGATORIA')+'</summary>';
 const link=url(c.sourceURL);
 return '<details>'+head+'<p><span class="tag">'+esc(CATEGORY[c.category]||c.category||'Sector no cubierto')+'</span> · último ejercicio: '+esc(c.latestFiscalYearEnd||'sin fecha')+
 ' · '+esc(c.fiscalAgeDays)+' días desde cierre · estado: '+esc(c.status)+'</p>'+
 metrics(c)+interim(c)+screening(c)+sources(c)+(link?'<p><a href="'+esc(link)+'" target="_blank" rel="noopener">Consultar datos originales SEC XBRL</a></p>':'')+
 '<p class="bad">Estado de inversión: BLOQUEADO. La nota integral y el precio de compra no se generan automáticamente.</p></details>';
}
function render(){
 const d=dataset;
 $('loaded').hidden=false;
 const cutoff=Date.parse(d.sourceRetrievedAt||'');
 const ageDays=Number.isFinite(cutoff)?Math.floor((Date.now()-cutoff)/86400000):Infinity;
 const stale=!Number.isFinite(ageDays)||ageDays>7;
 const failures=Number(d.summary.sourceErrors||0);
 $('notice').innerHTML=(stale?'<b class="bad">DATOS OBSOLETOS: última ejecución comprobable hace '+ageDays+' días.</b><p>No utilices resultados de cribado hasta que se restaure la actualización automática.</p>':'<b class="ok">Datos oficiales recientes.</b> ')+
 '<br>Motor: '+esc(d.engine)+' · Recuperados '+esc(d.sourceRetrievedAt||'fecha no disponible')+
 ' · '+d.summary.withAnnualFacts+' empresas con ejercicio anual.'+
 (failures?'<p class="bad">'+failures+' errores de descarga SEC: cifras incompletas.</p>':'')+
 '<p><strong>Ninguna recomendación ni precio de compra automático.</strong></p>';
 $('tracked').textContent=d.summary.tracked;
 $('annual').textContent=d.summary.withAnnualFacts;
 $('blocked').textContent=d.summary.blocked;
 $('approved').textContent=d.summary.decisionReady;
 const term=$('search').value.trim().toLowerCase(),filter=$('filter').value;
 const rows=d.companies.filter(c=>(c.ticker+' '+c.name+' '+c.category).toLowerCase().includes(term)&&(filter==='all'||filter===c.status));
 $('table').innerHTML=rows.map(c=>{const a=latest(c);return '<tr><td><b>'+esc(c.ticker)+'</b><small>'+esc(c.name)+' · '+esc(CATEGORY[c.category]||c.category||'—')+'</small></td><td>'+esc(c.latestFiscalYearEnd||'—')+'</td><td>'+money(a?.freeCashFlowSimple)+'</td><td>'+pct(a?.freeCashFlowMargin)+'</td><td>'+num(a?.cashConversion)+'×</td><td>'+issue(c)+'</td><td>Sin validar</td></tr>'}).join('')||'<tr><td colspan="7">Sin emisores para el filtro.</td></tr>';
 $('details').innerHTML=rows.map(detail).join('')||'<p>Sin resultados.</p>';
 $('limits').innerHTML=d.limitations.map(x=>'<li>'+esc(x)+'</li>').join('');
}
async function loadSECtagCandidates(){
 try{
  const res=await fetch('./data/cashflow-evidence.json?'+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('HTTP '+res.status);
  const d=await res.json(),audit=d.tagReview||[];
  $('tagStatus').textContent=audit.length+' emisores revisados; '+(d.summary.candidateFamiliesFound||0)+' familias con etiquetas documentales alternativas. Ningún candidato se sustituye automáticamente.';
  $('tagReview').innerHTML=audit.map(c=>{
   const families=Object.entries(c.candidates||{}).filter(([k,v])=>v.length);
   return '<details><summary>'+esc(c.ticker)+' · '+families.length+' familias detectadas</summary>'+
     families.map(([group,items])=>'<p><b>'+esc(group)+':</b> '+items.map(item=>esc(item.taxonomy+':'+item.tag)+' ('+esc(item.latest?.end||'?')+', '+esc(item.latest?.form||'?')+')').join(' · ')+'</p>').join('')+'</details>';
  }).join('');
 }catch(e){$('tagStatus').textContent='Etiquetas pendientes: '+e.message}
}
async function loadFCFFFCFE(){
 try{
  const res=await fetch('./data/cashflow-evidence.json?'+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('HTTP '+res.status);
  const d=await res.json();
  $('cashflowStatus').textContent='Cobertura: '+d.summary.covered+' emisores; '+d.summary.withCashFlowSimple+' con CFO menos CAPEX anual; '+d.summary.verifiedFCFF+' FCFF y '+d.summary.verifiedFCFE+' FCFE totalmente verificados. Los puentes parciales no son valores intrínsecos.';
  const fmt=n=>typeof n==='number'?num(n/1e6)+' MUSD':'No verificable';
  $('cashflowRows').innerHTML=d.companies.map(x=>{
   const latest=x.fiscalAnnualBridges?.[0],v=latest?.reconciliations||{};
   return '<tr><td><b>'+esc(x.ticker)+'</b></td><td>'+esc(latest?.fiscalYearEnd||'—')+'</td><td>'+fmt(v.cfoMinusPPECapex)+'</td><td>'+fmt(v.fcffFromCFOAndReportedInterestTax)+'</td><td>'+fmt(v.fcfeCashPlusBorrowingProxy)+'</td><td>'+esc(latest?.issues?.length||0)+' pendientes</td></tr>';
  }).join('');
 }catch(e){$('cashflowStatus').textContent='Conciliación FCFF/FCFE no disponible: '+e.message}
}
async function loadAutoResearch(){
 try{
  const response=await fetch('./data/autonomous-analysis.json?'+Date.now(),{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const d=await response.json();
  $('autoStatus').textContent='Analizadas '+d.summary.covered+' empresas; '+d.summary.withDiagnostics+' con escenarios reproducibles, '+d.summary.blocked+' bloqueadas, '+d.summary.approved+' homologadas.';
  $('autoRows').innerHTML=d.companies.map(x=>{
   const fmt=n=>typeof n==='number'?num(n)+' USD':'—';
   const scenario=x.scenarios||{},g=x.assumptions?.blendedForwardGrowth;
   return '<tr><td><b>'+esc(x.ticker)+'</b></td><td>'+esc(x.readiness)+'</td><td>'+(typeof g==='number'?num(100*g)+'%':'—')+'</td><td>'+fmt(scenario.downside?.illustrativeCashFlowProxyPerShareUSD)+'</td><td>'+fmt(scenario.central?.illustrativeCashFlowProxyPerShareUSD)+'</td><td>'+fmt(scenario.upside?.illustrativeCashFlowProxyPerShareUSD)+'</td><td>'+x.hardGates.length+' pendientes</td></tr>';
  }).join('');
  $('autoDetails').innerHTML=d.companies.map(x=>{
   const sens=x.sensitivity,show=n=>typeof n==='number'?num(n):'—';
   const grid=sens?'<div class="scroller"><table><thead><tr><th>Descuento / Δ crecimiento</th>'+sens.growthDeltas.map(v=>'<th>'+num(100*v)+' pp</th>').join('')+'</tr></thead><tbody>'+sens.rows.map(row=>'<tr><td>'+num(row.discount*100)+'%</td>'+row.values.map(v=>'<td>'+show(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>':'<p>Sin escenarios: datos o modelo sectorial insuficientes.</p>';
   return '<details><summary>'+esc(x.ticker)+' · '+esc(x.name)+' · '+esc(x.readiness)+'</summary><p><b>Hipótesis:</b> '+esc(x.assumptions?.growthMethod||'Modelo sectorial pendiente')+'.</p><p><b>Comprobaciones pendientes:</b> '+esc(x.hardGates.join(', '))+'</p>'+grid+'<p><b>Precio aprobado:</b> ninguno. Fuente: '+(x.evidence?.sourceURL?'<a href="'+esc(x.evidence.sourceURL)+'" target="_blank" rel="noopener">SEC oficial</a>':'pendiente')+'</p></details>';
  }).join('');
 }catch(e){$('autoStatus').textContent='No disponible: '+e.message}
}
async function loadFilingAudit(){
 try{
 const r=await fetch('./data/filing-audit.json?'+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error('HTTP '+r.status);
 const audit=await r.json();
 $('filingStatus').textContent=audit.summary.reconciledFY+' conciliaciones de cierre fiscal; '+audit.summary.closedValuations+' valoraciones homologadas. Liquidez restringida y datos interinos sujetos a revisión adicional.';
 const fmt=n=>typeof n==='number'?num(n)+' USD':'—';
 $('filingRows').innerHTML=audit.companies.map(c=>{
 const b=c.balance,range=c.sensitivity?.range;
 return '<tr><td><b>'+esc(c.ticker)+'</b></td><td>'+ (b?num(b.netDebtMillions)+' MUSD':'Pendiente')+'</td><td>'+fmt(range?.low)+'</td><td>'+fmt(range?.central)+'</td><td>'+fmt(range?.high)+'</td><td>'+(typeof c.sensitivity?.spreadPct==='number'?num(c.sensitivity.spreadPct)+'%':'—')+'</td><td><span class="bad">'+esc(c.auditVerdict)+'</span>'+(b?'<small><a href="'+esc(b.sourceURL)+'" target="_blank" rel="noopener">Fuente SEC</a></small>':'')+'</td></tr>'
 }).join('');
 }catch(e){$('filingStatus').textContent='Conciliaciones todavía no disponibles: '+e.message}
}
async function loadSectorModels(){
 try{
  const [a,b]=await Promise.all(['sector-models.json','normalized-financials.json'].map(async n=>{const r=await fetch('./data/'+n+'?'+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(n+' HTTP '+r.status);return r.json()}));
  const index=Object.fromEntries(b.financials.map(x=>[x.ticker,x]));
  $('sectorStatus').textContent='9 modelos sectoriales, '+a.summary.modelsWithScenarios+' con escenarios orientativos; '+a.summary.closedValuations+' valoraciones aprobadas. La deuda neta y el puente de caja al accionista siguen bloqueados mientras no estén conciliados.';
  $('sectorModels').innerHTML=a.companies.map(m=>{
   const f=index[m.ticker],coverage=f?.coverage||{};
   const price=x=>typeof x==='number'?num(x)+' USD':'—';
   const scenarios=m.scenarios||{};
   const label=m.model==='adjusted_book_required'?'Valor contable ajustado (pendiente)':m.model==='sum_of_parts_required'?'Suma de partes (pendiente)':'Descuento de proxy de caja (NO DCF validado)';
   return '<tr><td><b>'+esc(m.ticker)+'</b></td><td>'+esc(label)+'</td><td>'+price(scenarios.conservative?.illustrativePricePerShare)+'</td><td>'+price(scenarios.central?.illustrativePricePerShare)+'</td><td>'+price(scenarios.optimistic?.illustrativePricePerShare)+'</td><td><small>Deuda: '+(coverage.debtFullyReconciled?'conciliada':'SIN CONCILIAR')+'; acciones: '+(coverage.dilutedSharesLatest?'identificadas':'pendientes')+'; incidencias: '+m.hardGates.length+'</small></td><td><b class="bad">No homologado</b></td></tr>'
  }).join('');
 }catch(e){$('sectorStatus').textContent='Información sectorial pendiente: '+e.message}
}
async function load(){
 try{
  const res=await fetch('./data/fundamental-research.json?'+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('La primera ejecución del motor no está disponible: HTTP '+res.status);
  const d=await res.json();if(d.schema!==1||!Array.isArray(d.companies)||!d.summary)throw Error('Archivo de análisis incompatible');
  dataset=d;render();await loadSectorModels();await loadFilingAudit();await loadAutoResearch();await loadFCFFFCFE();await loadSECtagCandidates();
 }catch(e){$('notice').textContent='Motor pendiente o no disponible: '+e.message}
}
$('search').oninput=()=>dataset&&render();$('filter').onchange=()=>dataset&&render();load();
})();