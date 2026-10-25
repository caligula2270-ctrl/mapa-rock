(()=>{'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','&#39;':'&#39;'}[c]));
const usd=n=>Number.isFinite(Number(n))?Number(n).toFixed(2)+' USD':'—';
let companies=[],market=[],watch=[],alerts=[],runs=[],busy=false;
function cfg(){return JSON.parse(localStorage.getItem('ir_cloud_config_v3')||'null')}
function sess(){return JSON.parse(sessionStorage.getItem('ir_cloud_session_v3')||'null')}
async function token(){
 const c=cfg(),s=sess();
 if(!c?.url||!c?.key||!s?.access_token||!s?.user?.id)throw Error('Inicia sesión en Investment Radar.');
 if(s.expires_at&&Date.now()>(Number(s.expires_at)-120)*1000){
  if(!s.refresh_token)throw Error('Sesión caducada.');
  const r=await fetch(c.url+'/auth/v1/token?grant_type=refresh_token',{method:'POST',headers:{apikey:c.key,'Content-Type':'application/json'},body:JSON.stringify({refresh_token:s.refresh_token})});
  if(!r.ok)throw Error('No se ha podido renovar la sesión.');
  const next=await r.json();sessionStorage.setItem('ir_cloud_session_v3',JSON.stringify(next));return next.access_token;
 }
 return s.access_token;
}
async function api(path,method='GET',data){
 const c=cfg(),jwt=await token();
 const r=await fetch(c.url+'/rest/v1/'+path,{method,headers:{apikey:c.key,Authorization:'Bearer '+jwt,'Content-Type':'application/json',...(method==='POST'?{Prefer:'resolution=merge-duplicates'}:{})},body:data?JSON.stringify(data):undefined,cache:'no-store'});
 if(!r.ok)throw Error('Supabase '+r.status+' ('+path.split('?')[0]+')');
 if(r.status===204)return [];
 return r.json();
}
function draw(){
 const by=Object.fromEntries(market.map(x=>[x.ticker,x])),w=Object.fromEntries(watch.map(x=>[x.ticker,x]));
 const search=$('search').value.toLowerCase(),filter=$('filter').value;
 const shown=companies.filter(x=>{
 const q=by[x.ticker],v=w[x.ticker];
 if(![x.ticker,x.sector,x.research_data?.company].some(z=>String(z||'').toLowerCase().includes(search)))return false;
 return filter==='quoted'?!!q:filter==='missing'?!q:filter==='watch'?!!v?.enabled:filter==='review'?['audit_required','pending_evidence'].includes(x.review_status):true;
 });
 $('universe').innerHTML=shown.map(x=>{
 const q=by[x.ticker],v=w[x.ticker],parts=['quality_moat','quality_returns','quality_cash','quality_balance','quality_valuation'];
 const score=parts.every(k=>x[k]!==null&&x[k]!==undefined)?parts.reduce((a,k)=>a+Number(x[k]),0)+'/100':'Pendiente';
 const hit=q&&v?.enabled&&Number(q.close_price)<=Number(v.watch_price);
 return '<tr><td><b>'+esc(x.ticker)+'</b><small>'+esc(x.research_data?.company||'')+' · '+esc(x.sector||'Sector sin confirmar')+'</small></td><td>'+usd(q?.close_price)+'</td><td>'+esc(q?.session_date||'—')+'</td><td class="'+(hit?'warn':'')+'">'+(v?.enabled?usd(v.watch_price)+(hit?' · Revisar':''):'Sin regla activa')+'</td><td>'+esc(x.review_status)+'</td><td>'+score+'</td></tr>';
 }).join('')||'<tr><td colspan="6">Sin resultados.</td></tr>';
 $('countCompanies').textContent=companies.length;$('countQuotes').textContent=market.length;$('countAlerts').textContent=alerts.length;
 $('lastMarket').textContent=market.reduce((a,x)=>x.session_date>a?x.session_date:a,'')||'—';
 $('alerts').innerHTML=alerts.slice(0,30).map(x=>'<tr><td>'+esc(x.ticker)+'<small>'+esc(x.message)+'</small></td><td>'+esc(x.session_date)+'</td><td>'+usd(x.observed_price)+' / '+usd(x.watch_price)+'</td></tr>').join('')||'<tr><td colspan="3">Sin avisos.</td></tr>';
 const last=runs[0];$('healthMessage').textContent=last?'Último resultado: '+last.status+' · '+last.symbols_received+'/'+last.symbols_requested+' símbolos':'Programación instalada. Primera ejecución no verificada.';
 $('runs').innerHTML=runs.slice(0,8).map(x=>'<tr><td>Cierre bursátil</td><td>'+esc(x.status)+'</td><td>'+esc(x.completed_at?.slice(0,19))+' UTC</td><td>'+x.symbols_received+'/'+x.symbols_requested+' · '+esc((x.missing_symbols||[]).join(', '))+'</td></tr>').join('')||'<tr><td colspan="4">Sin ejecuciones automáticas verificadas.</td></tr>';
}
function fillRule(){
 const ticker=$('ruleTicker').value,rule=watch.find(x=>x.ticker===ticker);
 $('rulePrice').value=rule?.watch_price||'';$('ruleEnabled').checked=Boolean(rule?.enabled);
 $('ruleStatus').textContent=rule?'Umbral preliminar: no supone una señal de compra.':'Introduce un precio de vigilancia fundamentado.';
}
async function load(){
 if(busy)return;busy=true;$('refresh').disabled=true;
 try{
 const [a,b,c,d,e]=await Promise.all([
 api('investment_radar_research_queue?select=*&order=ticker.asc'),
 api('investment_radar_market_closes?select=*&order=ticker.asc'),
 api('investment_radar_watch_rules?select=*&order=ticker.asc'),
 api('investment_radar_watch_events?select=*&order=created_at.desc&limit=100'),
 api('investment_radar_market_runs?select=*&order=id.desc&limit=10')]);
 companies=a;market=b;watch=c;alerts=d;runs=e;
 $('auth').hidden=true;$('private').hidden=false;
 const old=$('ruleTicker').value;$('ruleTicker').innerHTML=companies.map(x=>'<option value="'+esc(x.ticker)+'"'+(x.ticker===old?' selected':'')+'>'+esc(x.ticker)+'</option>').join('');
 fillRule();draw();
 }catch(e){$('auth').hidden=false;$('private').hidden=true;$('auth').innerHTML='<b>Acceso privado necesario</b><p>'+esc(e.message)+'</p><p><a href="./cuenta.html?next=radar-autonomo.html">Iniciar sesión aquí</a></p>'}
 finally{busy=false;$('refresh').disabled=false}
}
async function save(){
 const price=Number($('rulePrice').value),ticker=$('ruleTicker').value;if(!(price>0)){$('ruleStatus').textContent='Introduce un precio mayor que cero.';return}
 try{await api('investment_radar_watch_rules?on_conflict=user_id,ticker','POST',{user_id:sess().user.id,ticker,watch_price:price,enabled:$('ruleEnabled').checked,is_validated:false,note:'Umbral preliminar de vigilancia',updated_at:new Date().toISOString()});$('ruleStatus').textContent='Guardado en tu espacio privado.';await load()}catch(e){$('ruleStatus').textContent='Error de guardado: '+e.message}
}
$('refresh').onclick=load;$('search').oninput=draw;$('filter').onchange=draw;$('ruleTicker').onchange=fillRule;$('ruleSave').onclick=save;
load();setInterval(()=>{if(!document.hidden)load()},300000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});
})();