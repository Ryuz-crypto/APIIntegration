"""Self-contained administration page for ec-mcp 3.0."""

PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>ec-mcp 3.0 control plane</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;--bg:#07111f;--panel:#101d30;--panel2:#15243a;--line:#2c3d55;--text:#e7eef8;--muted:#94a8c2;--brand:#38bdf8;--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444}
*{box-sizing:border-box}body{font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:radial-gradient(circle at top,#12304c 0,var(--bg) 45%);color:var(--text);margin:0;min-height:100vh}
main{max-width:1180px;margin:auto;padding:28px 18px 60px}.panel{background:rgba(16,29,48,.96);border:1px solid var(--line);border-radius:14px;padding:22px;margin-top:16px;box-shadow:0 18px 50px rgba(0,0,0,.25)}
header{display:flex;align-items:center;justify-content:space-between;gap:16px}.brand h1{margin:0;font-size:1.45rem}.brand p{margin:5px 0 0;color:var(--muted)}.badge{border:1px solid #0ea5e9;color:#7dd3fc;border-radius:999px;padding:5px 10px;font-size:.75rem}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}nav button{background:#172a43}.active-tab{background:#0369a1!important}
button{padding:10px 15px;border:0;border-radius:9px;background:#0284c7;color:white;font-weight:700;cursor:pointer}button.secondary{background:#334155}button.danger{background:#991b1b}button:disabled{opacity:.45;cursor:not-allowed}
input,select{width:100%;margin-top:5px;padding:10px 11px;background:#091525;border:1px solid var(--line);border-radius:8px;color:var(--text)}label{display:block;color:#c6d3e3;font-size:.86rem}.help{display:block;color:var(--muted);font-size:.76rem;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.group{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px;margin-top:14px}.group h3{margin:0 0 14px;color:#bae6fd}.field{margin-bottom:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.msg{padding:11px 13px;border-radius:9px;margin-top:15px;white-space:pre-wrap}.ok{background:#052e1a;border:1px solid #166534}.err{background:#3b161a;border:1px solid #991b1b}.info{background:#102a43;border:1px solid #0369a1}
.orch{padding:14px;border:1px solid var(--line);border-radius:10px;margin:9px 0}.orch-actions{float:right;display:flex;gap:7px}.secret-note{font-size:.74rem;color:#7dd3fc}.clear{display:flex;align-items:center;gap:6px;margin-top:6px}.clear input{width:auto;margin:0}
.step{display:grid;grid-template-columns:42px 1fr;gap:12px;align-items:start;padding:14px 0;border-bottom:1px solid var(--line)}.step:last-child{border:0}.num{height:34px;width:34px;border-radius:50%;background:#1e3a5f;display:grid;place-items:center;font-weight:800}.locked{opacity:.6}.mono{font-family:ui-monospace,SFMono-Regular,monospace;word-break:break-all}
dialog{border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--text);max-width:480px;width:calc(100% - 30px);padding:24px}
@media(max-width:760px){.grid{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}}
</style></head><body><main id="app">Cargando...</main>
<script>
var AUTHED=false, STATE={}, CONFIG=null, UPDATE=null;
function q(s){return document.querySelector(s)}
function esc(v){return String(v==null?'':v).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
async function api(path,body){
 var options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
 var response=await fetch(path,options);
 var data=await response.json();
 if(response.status===401){AUTHED=false;renderLogin();throw new Error('Sesión expirada');}
 return data;
}
function notice(message,type){var node=q('#notice');if(node)node.innerHTML='<div class="msg '+(type||'info')+'">'+esc(message)+'</div>'}
function renderLogin(){
 q('#app').innerHTML='<section class="panel" style="max-width:440px;margin:12vh auto"><div class="brand"><h1>ec-mcp 3.0</h1><p>Control plane administrativo</p></div><label style="margin-top:22px">Contraseña<input id="login-password" type="password" autocomplete="current-password"></label><div class="actions"><button onclick="login()">Entrar</button></div><div id="notice"></div></section>';
 q('#login-password').addEventListener('keydown',function(e){if(e.key==='Enter')login()});
}
async function login(){
 try{var r=await api('/login',{password:q('#login-password').value});if(!r.ok){notice(r.error||'Contraseña incorrecta','err');return}AUTHED=true;renderShell();await loadAll();}
 catch(e){notice(e.message,'err')}
}
async function logout(){await api('/logout',{});AUTHED=false;renderLogin()}
function renderShell(){
 q('#app').innerHTML='<header><div class="brand"><h1>ec-mcp control plane</h1><p>Configuración, operación y actualizaciones sin SSH</p></div><span class="badge">__EC_MCP_VERSION__</span></header>'+
 '<nav><button id="tab-orch" onclick="showTab(\'orch\')">Orquestadores</button><button id="tab-config" onclick="showTab(\'config\')">Variables</button><button id="tab-update" onclick="showTab(\'update\')">Actualizaciones</button><button id="tab-ztp" onclick="showTab(\'ztp\')">ZTP</button><button class="secondary" onclick="logout()">Salir</button></nav>'+
 '<div id="notice"></div><section id="workspace"></section>';
 showTab('config');
}
function showTab(name){
 document.querySelectorAll('nav button').forEach(function(b){b.classList.remove('active-tab')});
 var tab=q('#tab-'+name);if(tab)tab.classList.add('active-tab');
 if(name==='orch')renderOrchestrators();
 if(name==='config')renderConfig();
 if(name==='update')renderUpdate();
 if(name==='ztp')renderZtp();
}
async function loadAll(){
 try{var results=await Promise.all([api('/api/state'),api('/api/config'),api('/api/update/status')]);STATE=results[0];CONFIG=results[1];UPDATE={status:results[2]};renderConfig();}
 catch(e){notice(e.message,'err')}
}
function renderOrchestrators(){
 var list=(STATE.orchestrators||[]).map(function(o){return '<div class="orch"><span class="orch-actions"><button class="secondary" onclick="editOrch(\''+esc(o.name)+'\')">Editar</button><button class="danger" onclick="deleteOrch(\''+esc(o.name)+'\')">Eliminar</button></span><strong>'+esc(o.name)+'</strong> '+(o.active?'<span class="badge">activo</span>':'')+'<br><span class="help">'+esc(o.url)+'</span></div>'}).join('')||'<p class="help">No hay orquestadores guardados.</p>';
 q('#workspace').innerHTML='<section class="panel"><h2>Orquestadores</h2>'+list+
 '<div class="group"><h3>Agregar o actualizar</h3><div class="grid"><label>Nombre<input id="o-name"></label><label>URL<input id="o-url" placeholder="https://orchestrator.example.com"></label><label>API key<input id="o-key" type="password"></label><label>Usuario<input id="o-user"></label><label>Password<input id="o-password" type="password"></label><label>Verificar TLS<select id="o-tls"><option>true</option><option>false</option></select></label><label>Usuario SSH<input id="o-ssh-user"></label><label>Password SSH<input id="o-ssh-password" type="password"></label><label>Password enable<input id="o-enable" type="password"></label><label>Host SSH<input id="o-ssh-host"></label></div><div class="actions"><button onclick="saveOrch()">Guardar</button><button class="secondary" onclick="applyOrch()">Aplicar al .env</button></div></div></section>';
}
function editOrch(name){var o=(STATE.orchestrators||[]).find(function(x){return x.name===name});if(!o)return;q('#o-name').value=o.name;q('#o-url').value=o.url;q('#o-tls').value=String(o.verify_tls);q('#o-ssh-user').value=o.ssh_user||'';q('#o-ssh-host').value=o.ssh_host||''}
async function saveOrch(){
 try{var r=await api('/api/orchestrators',{name:q('#o-name').value.trim(),url:q('#o-url').value.trim(),api_key:q('#o-key').value,username:q('#o-user').value,password:q('#o-password').value,verify_tls:q('#o-tls').value==='true',ssh_user:q('#o-ssh-user').value,ssh_password:q('#o-ssh-password').value,ssh_enable_password:q('#o-enable').value,ssh_host:q('#o-ssh-host').value});notice(r.message||r.error,r.ok?'ok':'err');STATE=await api('/api/state');renderOrchestrators()}catch(e){notice(e.message,'err')}
}
async function deleteOrch(name){if(!confirm('Eliminar '+name+'?'))return;await api('/api/orchestrators/delete',{name:name});STATE=await api('/api/state');renderOrchestrators()}
async function applyOrch(){try{var r=await api('/api/apply',{name:q('#o-name').value.trim()});notice(r.message||r.error,r.ok?'ok':'err');CONFIG=await api('/api/config')}catch(e){notice(e.message,'err')}}
function fieldHtml(f){
 var id='cfg-'+f.key, input='';
 if(f.kind==='boolean')input='<select id="'+id+'" data-key="'+f.key+'"><option value="true">true</option><option value="false">false</option></select>';
 else if(f.kind==='choice')input='<select id="'+id+'" data-key="'+f.key+'">'+f.choices.map(function(v){return '<option>'+esc(v)+'</option>'}).join('')+'</select>';
 else input='<input id="'+id+'" data-key="'+f.key+'" type="'+(f.secret?'password':(f.kind==='integer'||f.kind==='number'?'number':'text'))+'" value="'+esc(f.value)+'" placeholder="'+(f.secret&&f.configured?'Configurado; vacío conserva el secreto':'')+'">';
 var clear=f.secret&&f.configured?'<label class="clear"><input type="checkbox" data-clear="'+f.key+'">Eliminar secreto guardado</label>':'';
 return '<div class="field"><label>'+esc(f.label)+input+'</label>'+(f.secret?'<span class="secret-note">'+(f.configured?'Secreto configurado; no se muestra.':'Sin configurar.')+'</span>':'')+(f.help?'<span class="help">'+esc(f.help)+'</span>':'')+clear+'</div>';
}
function renderConfig(){
 if(!CONFIG){q('#workspace').innerHTML='<section class="panel">Cargando variables...</section>';return}
 var groups={};CONFIG.fields.forEach(function(f){(groups[f.group]||(groups[f.group]=[])).push(f)});
 var html=Object.keys(groups).map(function(name){return '<section class="group"><h3>'+esc(name)+'</h3><div class="grid">'+groups[name].map(fieldHtml).join('')+'</div></section>'}).join('');
 q('#workspace').innerHTML='<section class="panel"><h2>Variables del servicio</h2><p>Se guardan en <span class="mono">'+esc(CONFIG.env_file)+'</span>. Los secretos nunca regresan al navegador.</p>'+html+'<div class="actions"><button onclick="saveConfig()">Guardar variables</button><button class="secondary" onclick="restartServices()">Guardar y reiniciar servicios</button></div></section>';
 CONFIG.fields.forEach(function(f){var el=q('#cfg-'+f.key);if(el&&!f.secret)el.value=f.value});
}
async function saveConfig(restart){
 var values={},clear=[];
 CONFIG.fields.forEach(function(f){var el=q('#cfg-'+f.key);if(!el)return;if(!f.secret||el.value!=='')values[f.key]=el.value;var c=document.querySelector('[data-clear="'+f.key+'"]');if(c&&c.checked)clear.push(f.key)});
 try{var r=await api('/api/config',{values:values,clear_secrets:clear});notice(r.message||r.error,r.ok?'ok':'err');if(!r.ok)return;CONFIG=await api('/api/config');if(restart)await doRestart();else renderConfig()}catch(e){notice(e.message,'err')}
}
async function restartServices(){await saveConfig(true)}
async function doRestart(){try{var r=await api('/api/restart',{});notice(r.message||r.error,r.state==='pending'?'ok':'err');if(r.state==='pending')pollRestart(0)}catch(e){notice(e.message,'err')}}
async function pollRestart(attempt){
 try{var s=await api('/api/restart/result');
  if(s.request_pending){if(attempt<15){setTimeout(function(){pollRestart(attempt+1)},4000)}else{notice('El reinicio sigue pendiente. Verifica ec-mcp-update.timer con: systemctl status ec-mcp-update.timer','err')}return}
  if(s.state==='success'){notice('Servicios reiniciados correctamente'+(s.completed_at?' ('+s.completed_at.replace('T',' ').split('.')[0]+' UTC)':'')+'. La configuración guardada ya está activa.','ok')}
  else if(s.state==='error'){notice('El reinicio falló: '+(s.message||'sin detalle')+(s.diagnostic?'\n'+s.diagnostic:''),'err')}
 }catch(e){if(attempt<15)setTimeout(function(){pollRestart(attempt+1)},4000)}
}
function renderUpdate(){
 var s=UPDATE&&UPDATE.status?UPDATE.status:{state:'idle'};
 q('#workspace').innerHTML='<section class="panel"><h2>Actualizaciones desde GitHub</h2><p>Detecta la rama configurada, fija el commit exacto y delega la instalación a un worker separado. Para repositorios privados configura usuario y token en <b>Variables → Actualizaciones</b>.</p><div class="group"><h3>Estado del worker</h3><p><span class="badge">'+esc(s.state||'idle')+'</span> '+esc(s.message||'Sin operaciones pendientes')+'</p>'+(s.diagnostic?'<pre class="mono">'+esc(s.diagnostic)+'</pre>':'')+'</div><div id="update-detail"></div><div class="actions"><button onclick="checkUpdate()">Detectar GitHub</button></div></section>';
}
async function checkUpdate(){
 try{var r=await api('/api/update/check',{});if(r.error)throw new Error(r.error);UPDATE=r;var remote=r.remote;var detail='<section class="group"><h3>'+esc(r.repository)+' · '+esc(r.branch)+'</h3><p>Instalado: <span class="mono">'+esc(r.current_short_sha||'desconocido')+'</span><br>GitHub: <span class="mono">'+esc(remote.short_sha)+'</span> · '+esc(remote.message)+'</p><p>'+(r.update_available?'Hay una actualización disponible.':'No hay una actualización pendiente o no se pudo determinar el commit instalado.')+'</p>';if(r.update_available)detail+='<label>Confirmación<input id="update-confirm" placeholder="'+esc(r.confirmation)+'"></label><div class="actions"><button onclick="applyUpdate(\''+esc(remote.sha)+'\',\''+esc(r.confirmation)+'\')">Aplicar actualización</button></div>';detail+='</section>';q('#update-detail').innerHTML=detail;notice('GitHub consultado correctamente.','ok')}catch(e){notice(e.message,'err')}
}
async function applyUpdate(sha,expected){var confirmation=q('#update-confirm').value;if(confirmation!==expected){notice('Escribe exactamente: '+expected,'err');return}try{var r=await api('/api/update/apply',{remote_sha:sha,confirmation:confirmation});notice(r.message||r.error,r.state==='pending'?'ok':'err');UPDATE.status=r;setTimeout(pollStatus,2000)}catch(e){notice(e.message,'err')}}
async function pollStatus(){try{var s=await api('/api/update/status');UPDATE.status=s;renderUpdate();if(s.state==='pending'||s.state==='running')setTimeout(pollStatus,3000)}catch(e){notice(e.message,'err')}}
function renderZtp(){
 q('#workspace').innerHTML='<section class="panel"><h2>Ruta ZTP</h2><p>Esta base prepara el control plane. Las escrituras de adopción siguen bloqueadas hasta que cada etapa tenga preview, aprobación y auditoría.</p>'+
 '<div class="step"><span class="num">1</span><div><strong>Discover</strong><p class="help">Inventario y candidatos detectados por Orchestrator.</p></div></div>'+
 '<div class="step locked"><span class="num">2</span><div><strong>Seleccionar template</strong><p class="help">Variables tipadas, compatibilidad y validación previa.</p></div></div>'+
 '<div class="step locked"><span class="num">3</span><div><strong>Adoptar</strong><p class="help">Vincular el equipo con identidad y autorización explícita.</p></div></div>'+
 '<div class="step locked"><span class="num">4</span><div><strong>Preview / diff</strong><p class="help">Mostrar exactamente qué configuración se aplicará.</p></div></div>'+
 '<div class="step locked"><span class="num">5</span><div><strong>Confirmar y planchar</strong><p class="help">Ejecución auditable con estado, health check y rollback.</p></div></div></section>';
}
renderLogin();
</script></body></html>"""
