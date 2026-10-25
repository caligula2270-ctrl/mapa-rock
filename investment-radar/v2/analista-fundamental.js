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
 metrics(c)+screening(c)+sources(c)+(link?'<p><a href="'+esc(link)+'" target="_blank" rel="noopener">Consultar datos originales SEC XBRL</a></p>':'')+
 '<p class="bad">Estado de inversión: BLOQUEADO. La nota integral y el precio de compra no se generan automáticamente.</p></details>';
}
function render(){
 const d=dataset;
 $('loaded').hidden=false;
 $('notice').innerHTML='<b>Motor ejecutado:</b> '+esc(d.engine)+' · Datos recuperados '+esc(d.sourceRetrievedAt||'fecha no disponible')+
 ' · '+d.summary.withAnnualFacts+' empresas con datos anuales. <b>0 recomendaciones automáticas.</b>';
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
async function load(){
 try{
  const res=await fetch('./data/fundamental-research.json?'+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('La primera ejecución del motor no está disponible: HTTP '+res.status);
  const d=await res.json();if(d.schema!==1||!Array.isArray(d.companies)||!d.summary)throw Error('Archivo de análisis incompatible');
  dataset=d;render();
 }catch(e){$('notice').textContent='Motor pendiente o no disponible: '+e.message}
}
$('search').oninput=()=>dataset&&render();$('filter').onchange=()=>dataset&&render();load();
})();