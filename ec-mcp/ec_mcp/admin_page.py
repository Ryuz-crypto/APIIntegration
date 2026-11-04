"""Self-contained administration page for ec-mcp 3.0."""

PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>ec-mcp 3.0 control plane</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light;--green:#01a982;--ink:#102a43;--cyan:#00c8ff;--brand-header:#073b4c;--blue:#00739d;--rose:#d94f70;--gold:#f2b900;--line:#c8d6df;--page-bg:#edf5f6;--surface:#fff;--text:#102a43;--muted:#5d7480;--brand:var(--green);--brand-header:#073b4c;--cyan:#00c8ff}
*{box-sizing:border-box}
body{font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:var(--page-bg);color:var(--text);margin:0;min-height:100vh}
main{max-width:1500px;margin:0 auto;padding-bottom:40px}
header.topbar{min-height:68px;padding:12px 32px;display:flex;align-items:center;justify-content:space-between;gap:16px;color:#fff;background:var(--brand-header);border-bottom:4px solid var(--brand);transition:background .3s ease,border-color .3s ease}
.brand{display:flex;align-items:center;gap:10px;color:var(--cyan)}
.logo{width:34px;height:34px;object-fit:contain}
.brand strong{display:block;font-size:20px;color:#fff}
.brand span{display:block;color:#d7eff3;font-size:12px}
.topbar-actions{display:flex;align-items:center;gap:10px}
.version{font-size:12px;padding:5px 9px;border:1px solid #4f7080;border-radius:4px;color:#d7eff3;white-space:nowrap}
nav{display:flex;gap:2px;padding:0 32px;background:#fff;border-bottom:1px solid var(--line);overflow-x:auto}
nav button{flex:0 0 auto;border:0;padding:14px 18px 12px;color:#506b78;background:transparent;border-bottom:3px solid transparent;font-weight:600;cursor:pointer;font-size:14px}
nav button.active-tab{color:var(--blue);border-bottom-color:var(--green);font-weight:700}
.panel{background:var(--surface);border:1px solid var(--line);border-top:4px solid var(--brand);border-radius:6px;padding:20px;margin:16px 32px 0;box-shadow:0 8px 18px rgba(16,42,67,.08)}
#notice{margin:16px 32px 0}
.msg{padding:10px 13px;border-left:4px solid var(--green);background:#e2f8ef;color:#075842;border-radius:4px;white-space:pre-wrap}
.msg.err{border-left-color:var(--rose);background:#fde5ec;color:#8b2140}
.msg.info{border-left-color:var(--blue);background:#e3f2fa;color:#0b4a6b}
.group{background:#f8fbfc;border:1px solid var(--line);border-radius:6px;padding:15px;margin-top:14px}
.group>summary{cursor:pointer;list-style:none}
.group>summary::-webkit-details-marker{display:none}
.group h3{margin:0;color:var(--blue);font-size:14px;font-weight:700;display:inline}
.count{display:inline-grid;place-items:center;min-width:24px;height:22px;margin-left:8px;padding:0 6px;background:#d5f7eb;color:#05684e;border-radius:4px;font-size:11px;font-weight:800;vertical-align:middle}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}
.field{margin-bottom:12px}
label{display:block;color:#385563;font-size:13px;font-weight:700;margin:12px 0 0}
input,select,textarea{display:block;width:100%;margin-top:5px;min-height:39px;padding:8px 10px;color:var(--text);background:var(--surface);border:1px solid #aebfca;border-radius:4px;outline:none;font:inherit}
input:focus,select:focus,textarea:focus{border-color:var(--green);box-shadow:0 0 0 3px rgba(1,169,130,.14)}
.help{display:block;color:#617985;font-size:12px;margin-top:5px}
.actions{display:flex;gap:9px;margin-top:18px;flex-wrap:wrap}
button{border-radius:4px;display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:38px;padding:8px 12px;font-weight:700;border:1px solid var(--green);background:var(--green);color:#06261f;cursor:pointer;font:inherit}
button:hover{background:#00c495}
button.secondary{color:#14546a;background:#fff;border:1px solid #8eabb7}
button.secondary:hover{border-color:var(--blue);color:var(--blue);background:#fff}
button.danger{color:#fff;background:#a12449;border-color:#a12449}
button.danger:hover{background:#c22c58}
button:disabled{opacity:.5;cursor:not-allowed}
.badge{display:inline-block;padding:3px 8px;border:1px solid var(--line);border-radius:4px;font-size:11px;font-weight:700;background:#edf2f4;color:#4e6672}
.orch{padding:12px 14px;border:1px solid var(--line);border-radius:5px;margin:8px 0;background:#fff}
.orch-actions{float:right;display:flex;gap:6px}
.orch-actions button{min-height:31px;padding:5px 8px;font-size:12px}
.secret-note{font-size:11px;color:#0f766e}
.clear{display:flex;align-items:center;gap:6px;margin-top:6px;font-weight:400}
.clear input{width:auto;margin:0;min-height:0}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}
.req{color:#a12449;font-weight:800}
.diff{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
.diff td{padding:8px 10px;border-bottom:1px solid #e3eaed;vertical-align:top}
.wizbar{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.sw{width:18px;height:18px;border-radius:50%;display:inline-block;cursor:pointer;border:2px solid #fff;box-shadow:0 0 0 1px #8eabb7}
.sw.active{box-shadow:0 0 0 2px #fff,0 0 0 4px var(--brand)}
.chrome{display:flex;gap:8px;align-items:center}
.chip{display:flex;align-items:center;background:rgba(255,255,255,.08);border:1px solid #4f7080;color:#bffce8;border-radius:4px;padding:6px 10px;font-size:12px;cursor:pointer;list-style:none}
.chip:hover{border-color:var(--cyan);color:#fff}
details.menu{position:relative}
details.menu .menu-body{position:absolute;right:0;top:36px;background:#fff;border:1px solid var(--line);border-radius:6px;box-shadow:0 8px 24px rgba(7,59,76,.25);padding:8px;display:flex;flex-direction:column;gap:6px;min-width:200px;z-index:20}
details.menu .menu-body button{width:100%;justify-content:flex-start}
dialog{border:1px solid var(--line);border-top:5px solid var(--gold);border-radius:6px;background:#fff;color:var(--text);max-width:520px;width:calc(100% - 30px);padding:22px;box-shadow:0 20px 60px rgba(4,31,42,.35)}
dialog::backdrop{background:rgba(7,59,76,.68)}
textarea{min-height:110px;font-family:ui-monospace,Consolas,monospace;font-size:12px}
.kv{display:grid;grid-template-columns:180px 1fr;gap:6px 10px;font-size:13px;margin-top:10px}
.kv dt{color:#617985;font-weight:700}
.kv dd{margin:0;word-break:break-all}
.cert-status{display:grid;gap:6px;margin:12px 0 16px;padding:14px;border-left:4px solid #8da2aa;background:#edf3f5;border-radius:4px}
.cert-status.active{border-left-color:var(--green);background:#e2f8ef}
.cert-status span{color:#4c6874;font-size:12px;overflow-wrap:anywhere}
.confirm-code{display:block;padding:10px;overflow-wrap:anywhere;color:#704f00;background:#fff5ce;border:1px solid #e6c65a;border-radius:4px;font-family:ui-monospace,Consolas,monospace;font-size:12px}
@media(max-width:900px){header.topbar,nav{padding-left:16px;padding-right:16px}.panel,#notice{margin-left:16px;margin-right:16px}.grid{grid-template-columns:1fr}}

.panel{animation:fadein .25s ease}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
button{transition:background .15s ease,border-color .15s ease,color .15s ease,transform .1s ease}
button:active{transform:scale(.97)}
.orch{transition:border-color .15s ease,box-shadow .15s ease}
.orch:hover{border-color:var(--brand);box-shadow:0 2px 10px rgba(16,42,67,.08)}
.tools-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin-top:14px}
.tool-card{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border:1px solid var(--line);border-left:4px solid var(--brand);border-radius:5px;background:#f9fcfc}
.tool-card strong{font-size:12.5px;word-break:break-all}
.tool-card .help{margin-top:3px}
.switch{position:relative;display:inline-block;width:40px;height:22px;flex:0 0 auto}
.switch input{opacity:0;width:0;height:0}
.slider{position:absolute;inset:0;background:#c3d2d9;border-radius:999px;transition:background .2s ease;cursor:pointer}
.slider::before{content:"";position:absolute;height:16px;width:16px;left:3px;top:3px;background:#fff;border-radius:50%;transition:transform .2s ease;box-shadow:0 1px 3px rgba(0,0,0,.25)}
.switch input:checked+.slider{background:var(--brand)}
.switch input:checked+.slider::before{transform:translateX(18px)}
.color-controls{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:10px}
.color-controls label{margin:0}
.color-controls input[type=color]{height:44px;padding:3px;min-height:0;cursor:pointer}
.icon-picker{display:flex;gap:8px;margin-top:7px;flex-wrap:wrap}
.icon-picker button{width:44px;height:40px;display:grid;place-items:center;color:#385563;background:#f8fbfc;border:1px solid var(--line);border-radius:4px;font-size:18px;min-height:0;padding:0}
.icon-picker button.selected{color:#075842;border:2px solid var(--brand);background:#e1f9f0}
.brand-preview{border-top:4px solid var(--preview-primary,#01a982);margin-top:14px}
.brand-preview>div{display:flex;align-items:center;gap:12px;margin:12px 0;padding:16px;color:#fff;background:var(--preview-header,#073b4c);border-radius:4px}
.brand-preview strong{display:block;font-size:18px}
.brand-preview span{display:block;color:#d7eff3;font-size:12px}
.brand-preview .logo{width:34px;height:34px;object-fit:contain;font-size:26px;background:transparent}
@media(max-width:900px){.tools-grid{grid-template-columns:1fr 1fr}.color-controls{grid-template-columns:1fr}}
</style></head><body><main id="app">Cargando...</main>
<script>
var AUTHED=false, STATE={}, CONFIG=null, UPDATE=null, ME=null, WIZARD=null, WSTEP=0, WDRAFT={}, CURTAB='wizard';
var LANG=localStorage.getItem('ec-lang')||'es';
var ACCENTS=[{n:'HPE Green',c:'#01a982'},{n:'Cyan',c:'#00c8ff'},{n:'Blue',c:'#00739d'},{n:'Gold',c:'#f2b900'},{n:'Rose',c:'#d94f70'},{n:'Header teal',c:'#073b4c'}];
var I18N={es:{nav_wizard:'Asistente',nav_orch:'Orquestadores',nav_sse:'Plataformas SSE',nav_svc:'Servicios',nav_config:'Variables',nav_update:'Actualizaciones',nav_users:'Usuarios',nav_out:'Salir',tagline:'Configuración, operación y actualizaciones sin SSH',login_title:'Control plane administrativo',login_user:'Usuario (opcional si hay varios)',login_pass:'Contraseña',login_enter:'Entrar',h2_orch:'Orquestadores',h2_sse:'Plataformas SSE (multi-tenant)',h2_svc:'Servicios',h2_config:'Variables del servicio',h2_update:'Actualizaciones desde GitHub',h2_users:'Usuarios del panel',h2_wizard:'Asistente de configuración',btn_save:'Guardar',btn_save_vars:'Guardar variables',btn_save_restart:'Guardar y reiniciar servicios',btn_save_restart_short:'Guardar y reiniciar',btn_recheck:'Volver a comprobar',btn_detect:'Detectar GitHub',btn_apply_update:'Aplicar actualización',btn_back:'Atrás',btn_next:'Siguiente',btn_review:'Revisar cambios',btn_probe:'Probar',btn_dup:'Duplicar',btn_ren:'Renombrar',btn_default:'Por defecto',btn_edit:'Editar',btn_delete:'Eliminar',btn_save_orch:'Guardar orquestador',btn_save_sse:'Guardar plataforma SSE',loading:'Cargando...',wiz_loading:'Cargando pasos...',secret_set:'Secreto configurado; no se muestra.',secret_unset:'Sin configurar.'},en:{nav_wizard:'Wizard',nav_orch:'Orchestrators',nav_sse:'SSE platforms',nav_svc:'Services',nav_config:'Settings',nav_update:'Updates',nav_users:'Users',nav_out:'Sign out',tagline:'Configuration, operations and updates without SSH',login_title:'Administrative control plane',login_user:'User (optional when there are several)',login_pass:'Password',login_enter:'Sign in',h2_orch:'Orchestrators',h2_sse:'SSE platforms (multi-tenant)',h2_svc:'Services',h2_config:'Service settings',h2_update:'Updates from GitHub',h2_users:'Panel users',h2_wizard:'Setup wizard',btn_save:'Save',btn_save_vars:'Save settings',btn_save_restart:'Save and restart services',btn_save_restart_short:'Save and restart',btn_recheck:'Re-check',btn_detect:'Check GitHub',btn_apply_update:'Apply update',btn_back:'Back',btn_next:'Next',btn_review:'Review changes',btn_probe:'Test',btn_dup:'Duplicate',btn_ren:'Rename',btn_default:'Default',btn_edit:'Edit',btn_delete:'Delete',btn_save_orch:'Save orchestrator',btn_save_sse:'Save SSE platform',loading:'Loading...',wiz_loading:'Loading steps...',secret_set:'Secret configured; never displayed.',secret_unset:'Not configured.'}};
function t(k,v){var d=I18N[LANG]||I18N.es;var s=d[k]||I18N.es[k]||k;if(v){for(var x in v){s=s.split('{'+x+'}').join(v[x])}}return s}
function setLang(l){LANG=l;localStorage.setItem('ec-lang',l);if(AUTHED){renderShell();showTab(CURTAB)}else{renderLogin()}}
function setAccent(c){document.documentElement.style.setProperty('--brand',c);localStorage.setItem('ec-accent',c);if(AUTHED){renderShell();showTab(CURTAB)}else{renderLogin()}}

function siteName(){return localStorage.getItem('ec-site-name')||'ec-mcp control plane'}
function siteLogo(){return localStorage.getItem('ec-logo')||''}
function siteIcon(){return localStorage.getItem('ec-icon')||''}
function brandHtml(){var ic=siteIcon();var logo=siteLogo();return '<div class="brand">'+(logo?'<img class="logo" src="'+logo+'" alt="logo">':(ic?'<span class="logo">'+esc(ic)+'</span>':''))+'<div><strong>'+esc(siteName())+'</strong><span>'+t('tagline')+'</span></div></div>'}
var ICONS=['⚡','🌐','🛰️','🔒','📡','🧭','🖧','⛓️'];
function openCustom(){
 var d=q('#custom-dlg');if(!d){q('#app').innerHTML+=customDialogHtml();d=q('#custom-dlg')}
 if(!d)return;
 q('#custom-name').value=siteName();
 q('#app-accent').value=localStorage.getItem('ec-accent')||'#01a982';
 q('#app-header').value=localStorage.getItem('ec-header')||'#073b4c';
 q('#app-cyan').value=localStorage.getItem('ec-cyan')||'#00c8ff';
 renderIconPicker();
 previewBrand();
 d.showModal?d.showModal():d.setAttribute('open','');
}
function renderIconPicker(){var cur=siteIcon();q('#icon-picker').innerHTML=ICONS.map(function(ic){return '<button type="button" class="'+(ic===cur?'selected':'')+'" onclick="pickIcon(\''+ic+'\')">'+ic+'</button>'}).join('')}
function pickIcon(ic){localStorage.setItem('ec-icon',ic);localStorage.removeItem('ec-logo');renderIconPicker();previewBrand();applySavedTheme();refreshBrand()}
function previewBrand(){var p=q('#brand-preview');if(!p||!p.style||!p.querySelector)return;p.style.setProperty('--preview-primary',localStorage.getItem('ec-accent')||'#01a982');p.style.setProperty('--preview-header',localStorage.getItem('ec-header')||'#073b4c');var ic=siteIcon();var logo=siteLogo();var pv=p.querySelector('.pv-brand');if(pv)pv.innerHTML=(logo?'<img class="logo" src="'+logo+'">':(ic?'<span class="logo">'+esc(ic)+'</span>':''))+'<div><strong>'+esc(q('#custom-name').value||siteName())+'</strong><span>'+t('tagline')+'</span></div>'}
function refreshBrand(){if(AUTHED){renderShell();showTab(CURTAB)}else{renderLogin()}}
function closeCustom(){var d=q('#custom-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
function saveCustom(){
 var name=q('#custom-name')?q('#custom-name').value.trim():'';if(name)localStorage.setItem('ec-site-name',name);
 var a=q('#app-accent');if(a)localStorage.setItem('ec-accent',a.value);
 var h=q('#app-header');if(h)localStorage.setItem('ec-header',h.value);
 var c=q('#app-cyan');if(c)localStorage.setItem('ec-cyan',c.value);
 var f=q('#custom-logo');
 if(f&&f.files&&f.files[0]){var r=new FileReader();r.onload=function(e){try{localStorage.setItem('ec-logo',String(e.target.result));localStorage.removeItem('ec-icon')}catch(err){notice(t('file_too_big'),'err')}applySavedTheme();closeCustom();refreshBrand()};r.readAsDataURL(f.files[0]);return}
 applySavedTheme();closeCustom();refreshBrand();
}
function customDialogHtml(){return '<dialog id="custom-dlg"><h3>'+t('custom_title')+'</h3><label>'+t('custom_name')+'<input id="custom-name" oninput="previewBrand()"></label><div class="color-controls"><label>'+t('app_accent')+'<input type="color" id="app-accent" oninput="previewBrand()"></label><label>'+t('app_header')+'<input type="color" id="app-header" oninput="previewBrand()"></label><label>'+t('app_cyan')+'<input type="color" id="app-cyan" oninput="previewBrand()"></label></div><label style="margin-top:12px">'+t('app_icon')+'<span class="icon-picker" id="icon-picker"></span></label><label style="margin-top:10px">'+t('custom_logo')+'<input id="custom-logo" type="file" accept="image/png,image/*"></label><div class="panel brand-preview" id="brand-preview"><div class="pv-brand"></div></div><div class="actions"><button onclick="saveCustom()">'+t('custom_save')+'</button><button class="secondary" onclick="closeCustom()">'+t('custom_cancel')+'</button></div></dialog>'}
function userChip(){return '<details class="menu"><summary class="chip">'+esc(ME&&ME.user?ME.user:'')+' · '+esc(ME&&ME.role?ME.role:'')+'</summary><div class="menu-body"><button class="secondary" onclick="showTab(\'users\')">'+t('menu_users')+'</button><button class="secondary" onclick="openCustom()">'+t('menu_custom')+'</button><button class="danger" onclick="logout()">'+t('nav_out')+'</button></div></details>'}

function chromeHtml(){return '<span class="chrome"><button class="secondary" style="padding:4px 9px;font-size:.75rem" onclick="setLang(LANG===\'es\'?\'en\':\'es\')">'+(LANG==='es'?'EN':'ES')+'</button><button class="secondary" style="padding:4px 9px;font-size:.75rem" title="'+t('menu_custom')+'" onclick="openCustom()">&#9881;</button></span>'}
function applySavedTheme(){
 var root=document.documentElement.style;
 root.setProperty('--brand',localStorage.getItem('ec-accent')||'#01a982');
 root.setProperty('--brand-header',localStorage.getItem('ec-header')||'#073b4c');
 root.setProperty('--cyan',localStorage.getItem('ec-cyan')||'#00c8ff');
}
applySavedTheme();

var I18N2={es:{wiz_step:'Asistente · paso {a} de {b}',badge_active:'activo',badge_default:'por defecto',no_orch:'No hay orquestadores guardados.',no_sse:'No hay plataformas SSE guardadas.',per_target:'Configuración por target',view_target:'Ver configuración de',all_targets:'(todas las variables globales)',blob_set:'configurado',blob_unset:'vacío',nav_tls:'Certificados',menu_users:'Usuarios y contraseña',menu_custom:'Personalizar panel',f_name:'Nombre',f_url:'URL',f_apikey:'API key',f_user:'Usuario',f_pass:'Password',f_tls:'Verificar TLS',f_ssh_user:'Usuario SSH',f_ssh_pass:'Password SSH',f_enable:'Password enable',f_ssh_host:'Host SSH',f_provider:'Proveedor',f_baseurl:'URL base',f_token:'Token admin (Bearer JWT)',f_timeout:'Timeout (s)',add_update:'Agregar o actualizar',apply_env:'Aplicar al .env',add_update_sse:'Agregar o actualizar plataforma SSE',saved_in:'Se guardan en',secrets_note:'Los secretos nunca regresan al navegador.',clear_secret:'Eliminar secreto guardado',checking:'Comprobando...',svc_checked:'Estado verificado con peticiones reales el',latency:'latencia',orch_label:'Orchestrator',sse_label:'SSE',upd_worker:'Worker de actualizaciones',mcp_label:'Transporte MCP',review_title:'Revisar cambios antes de guardar',review_desc:'Preview sobre',review_nowrite:'; todavía no se escribe nada.',no_changes:'Sin cambios en variables.',targets_h:'Targets (orquestadores / SSE)',wiz_targets_help:'Guarda varios orquestadores y varias plataformas SSE a la vez; elige cuál queda por defecto para los tools sin target explícito.',probing:'probando...',probe_ok:'OK: ',probe_fail:'Fallo: ',no_users:'Sin usuarios todavía: se usa la contraseña única (EC_ADMIN_PASSWORD).',hashes_note:'Los hashes nunca se muestran ni se devuelven.',add_user:'Agregar o actualizar usuario',change_pass:'Cambiar contraseña',u_name:'Usuario',u_pass:'Contraseña',u_role:'Rol',u_old:'Contraseña actual',u_new:'Nueva contraseña',u_empty:'Usuario (vacío = mi sesión)',users_file:'Archivo',tls_title:'Certificados HTTPS',tls_desc:'Sube el certificado y la llave privada (PEM) del panel. Los archivos se guardan con permisos 0600 y el panel puede servirse en HTTPS con EC_ADMIN_TLS_ENABLED=true.',tls_cert:'Certificado PEM',tls_key:'Llave privada PEM',tls_upload:'Subir certificado',tls_delete:'Eliminar certificado',tls_enabled:'HTTPS activo',tls_disabled:'HTTPS desactivado',tls_fp:'Huella SHA-256',tls_present:'presente',tls_missing:'ausente',tls_none:'Sin certificado subido.',custom_title:'Personalizar panel',custom_name:'Nombre del sitio',custom_logo:'Icono PNG',custom_save:'Guardar',custom_cancel:'Cancelar',target_info:'Configuración guardada en el registro para'},en:{wiz_step:'Wizard · step {a} of {b}',badge_active:'active',badge_default:'default',no_orch:'No orchestrators saved.',no_sse:'No SSE platforms saved.',per_target:'Per-target settings',view_target:'Show settings for',all_targets:'(all global variables)',blob_set:'configured',blob_unset:'empty',nav_tls:'Certificates',menu_users:'Users & password',menu_custom:'Customize panel',f_name:'Name',f_url:'URL',f_apikey:'API key',f_user:'User',f_pass:'Password',f_tls:'Verify TLS',f_ssh_user:'SSH user',f_ssh_pass:'SSH password',f_enable:'Enable password',f_ssh_host:'SSH host',f_provider:'Provider',f_baseurl:'Base URL',f_token:'Admin token (Bearer JWT)',f_timeout:'Timeout (s)',add_update:'Add or update',apply_env:'Apply to .env',add_update_sse:'Add or update SSE platform',saved_in:'Saved in',secrets_note:'Secrets are never returned to the browser.',clear_secret:'Remove saved secret',checking:'Checking...',svc_checked:'Status verified with real requests at',latency:'latency',orch_label:'Orchestrator',sse_label:'SSE',upd_worker:'Update worker',mcp_label:'MCP transport',review_title:'Review changes before saving',review_desc:'Preview on',review_nowrite:'; nothing is written yet.',no_changes:'No variable changes.',targets_h:'Targets (orchestrators / SSE)',wiz_targets_help:'Save several orchestrators and SSE platforms at once; choose which one is default for tools without an explicit target.',probing:'checking...',probe_ok:'OK: ',probe_fail:'Fail: ',no_users:'No users yet: the single password (EC_ADMIN_PASSWORD) is used.',hashes_note:'Hashes are never shown or returned.',add_user:'Add or update user',change_pass:'Change password',u_name:'User',u_pass:'Password',u_role:'Role',u_old:'Current password',u_new:'New password',u_empty:'User (empty = my session)',users_file:'File',tls_title:'HTTPS certificates',tls_desc:'Upload the panel certificate and private key (PEM). Files are stored with 0600 and the panel can serve HTTPS with EC_ADMIN_TLS_ENABLED=true.',tls_cert:'Certificate PEM',tls_key:'Private key PEM',tls_upload:'Upload certificate',tls_delete:'Delete certificate',tls_enabled:'HTTPS enabled',tls_disabled:'HTTPS disabled',tls_fp:'SHA-256 fingerprint',tls_present:'present',tls_missing:'missing',tls_none:'No certificate uploaded.',custom_title:'Customize panel',custom_name:'Site name',custom_logo:'PNG icon',custom_save:'Save',custom_cancel:'Cancel',target_info:'Registry settings for'}};
for(var k2 in I18N2.es){I18N.es[k2]=I18N2.es[k2]}
for(var k2 in I18N2.en){I18N.en[k2]=I18N2.en[k2]}

var I18N3={es:{tls_mode:'Formato',tls_cert_file:'Certificado (archivo)',tls_key_file:'Llave privada (archivo)',tls_pfx_file:'Archivo PFX / P12 / PKCS12',tls_bundle_file:'Bundle PEM (certificado y llave juntos)',tls_pw:'Contraseña de la llave o contenedor, si aplica',tls_note:'Los archivos se validan en el servidor, se normalizan a PEM y solo se instala si la llave corresponde al certificado. El certificado anterior se respalda (cert.pem.bak). Límite 3 MB.',tls_confirm:'Confirmación',tls_confirm_code:'INSTALAR CERTIFICADO',tls_install:'Instalar certificado',tls_installed:'Certificado instalado',tls_subject:'Sujeto',tls_issuer:'Emisor',tls_expires:'Vence',fmt_pem:'PEM: certificado y llave separados',fmt_bundle:'PEM bundle: certificado y llave juntos',fmt_pfx:'PFX / PKCS12',fmt_der:'DER: certificado y llave separados',file_too_big:'El archivo excede el límite de 3 MB'},en:{tls_mode:'Format',tls_cert_file:'Certificate (file)',tls_key_file:'Private key (file)',tls_pfx_file:'PFX / P12 / PKCS12 file',tls_bundle_file:'PEM bundle (certificate and key together)',tls_pw:'Key or container password, if any',tls_note:'Files are validated server-side, normalized to PEM and installed only if the key matches the certificate. The previous certificate is backed up (cert.pem.bak). 3 MB limit.',tls_confirm:'Confirmation',tls_confirm_code:'INSTALAR CERTIFICADO',tls_install:'Install certificate',tls_installed:'Certificate installed',tls_subject:'Subject',tls_issuer:'Issuer',tls_expires:'Expires',fmt_pem:'PEM: certificate and key separate',fmt_bundle:'PEM bundle: certificate and key together',fmt_pfx:'PFX / PKCS12',fmt_der:'DER: certificate and key separate',file_too_big:'File exceeds the 3 MB limit'}};
for(var k3 in I18N3.es){I18N.es[k3]=I18N3.es[k3]}
for(var k3 in I18N3.en){I18N.en[k3]=I18N3.en[k3]}

var I18N4={es:{yes:'Sí',no:'No',nav_tools:'Tools',global_vars:'Global (.env)',tools_title:'Tools MCP',tools_desc:'Activa o desactiva tools del servidor MCP (se guarda en EC_MCP_DISABLED_TOOLS y aplica al reiniciar).',tools_total:'tools totales',tools_disabled:'desactivadas',tool_on:'Activada:',tool_off:'Desactivada:',agent_btn:'Sugerencia para AI Agent',agent_title:'Prompt sugerido para el AI Agent',agent_desc:'Copia este texto al contexto de tu agente (skill) para que use ec-mcp de la mejor manera. Incluye los skills de docs/.',copy:'Copiar',copied:'Copiado al portapapeles'},en:{yes:'Yes',no:'No',nav_tools:'Tools',global_vars:'Global (.env)',tools_title:'MCP tools',tools_desc:'Enable or disable MCP server tools (saved to EC_MCP_DISABLED_TOOLS, applied on restart).',tools_total:'total tools',tools_disabled:'disabled',tool_on:'Enabled:',tool_off:'Disabled:',agent_btn:'AI Agent suggestion',agent_title:'Suggested prompt for the AI Agent',agent_desc:'Copy this text into your agent context (skill) so it uses ec-mcp the right way. Includes the docs/ skills.',copy:'Copy',copied:'Copied to clipboard'}};
for(var k4 in I18N4.es){I18N.es[k4]=I18N4.es[k4]}
for(var k4 in I18N4.en){I18N.en[k4]=I18N4.en[k4]}

var I18N5={es:{app_accent:'Color de acento',app_header:'Color de cabecera',app_cyan:'Color de acento secundario',app_icon:'Icono'},en:{app_accent:'Accent color',app_header:'Header color',app_cyan:'Secondary accent color',app_icon:'Icon'}};
for(var k5 in I18N5.es){I18N.es[k5]=I18N5.es[k5]}
for(var k5 in I18N5.en){I18N.en[k5]=I18N5.en[k5]}






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
 q('#app').innerHTML='<section class="panel" style="max-width:440px;margin:12vh auto"><div class="brand"><h1>'+esc(siteName())+'</h1><p>'+t('login_title')+'</p></div>'+chromeHtml()+'<label style="margin-top:22px">'+t('login_user')+'<input id="login-user" autocomplete="username"></label><label style="margin-top:12px">'+t('login_pass')+'<input id="login-password" type="password" autocomplete="current-password"></label><div class="actions"><button onclick="login()">'+t('login_enter')+'</button></div><div id="notice"></div></section>';
 q('#login-password').addEventListener('keydown',function(e){if(e.key==='Enter')login()});
 if(!q('#custom-dlg'))q('#app').innerHTML+=customDialogHtml();
}
async function login(){
 try{var r=await api('/login',{username:q('#login-user').value,password:q('#login-password').value});if(!r.ok){notice(r.error||'Contraseña incorrecta','err');return}ME=r;AUTHED=true;renderShell();await loadAll();}
 catch(e){notice(e.message,'err')}
}
async function logout(){await api('/logout',{});AUTHED=false;renderLogin()}
function renderShell(){
 q('#app').innerHTML='<header class="topbar">'+brandHtml()+'<div class="topbar-actions"><span class="version">__EC_MCP_VERSION__</span>'+userChip()+chromeHtml()+'</div></header>'+
 '<nav><button id="tab-wizard" onclick="showTab(\'wizard\')">'+t('nav_wizard')+'</button><button id="tab-orch" onclick="showTab(\'orch\')">'+t('nav_orch')+'</button><button id="tab-sse" onclick="showTab(\'sse\')">'+t('nav_sse')+'</button><button id="tab-svc" onclick="showTab(\'svc\')">'+t('nav_svc')+'</button><button id="tab-config" onclick="showTab(\'config\')">'+t('nav_config')+'</button><button id="tab-tls" onclick="showTab(\'tls\')">'+t('nav_tls')+'</button><button id="tab-tools" onclick="showTab(\'tools\')">'+t('nav_tools')+'</button><button id="tab-update" onclick="showTab(\'update\')">'+t('nav_update')+'</button><button id="tab-users" onclick="showTab(\'users\')">'+t('nav_users')+'</button></nav>'+
 '<div id="notice"></div><section id="workspace"></section>'+customDialogHtml();
 if(ME&&ME.role!=='admin'){var ub=q('#tab-users');if(ub)ub.style.display='none'}
 showTab('wizard');
}
function showTab(name){
 CURTAB=name;
 var ntc=q('#notice');if(ntc)ntc.innerHTML='';
 document.querySelectorAll('nav button').forEach(function(b){b.classList.remove('active-tab')});
 var tab=q('#tab-'+name);if(tab)tab.classList.add('active-tab');
 if(name==='wizard')renderWizard();
 if(name==='orch')renderOrchestrators();
 if(name==='sse')renderSse();
 if(name==='svc')renderServices();
 if(name==='config')renderConfig();
 if(name==='update')renderUpdate();
 if(name==='users')renderUsers();
 if(name==='tls')renderTls();
 if(name==='tools')renderTools();
}
async function renderServices(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_svc')+'</h2><p class="help">'+t('checking')+'</p></section>';
 try{var r=await api('/api/services/status');var h='<section class="panel"><h2>'+t('h2_svc')+'</h2><p class="help">'+t('svc_checked')+''+esc((r.checked_at||'').replace('T',' ').split('.')[0])+' UTC. Ningún servicio se muestra como activo sin comprobación.</p>';
 var orch=(r.orchestrators||[]).map(function(s){return svcRow(t('orch_label')+': '+s.name,s)}).join('');
 var sse=(r.sse_platforms||[]).map(function(s){return svcRow(t('sse_label')+': '+s.name,s)}).join('');
 var up=svcRow(''+t('upd_worker')+'',r.update_worker||{});
 var mcp=r.mcp_transport||{};var mcpRow=svcRow(t('mcp_label')+' ('+esc(mcp.url||'localhost')+')',mcp);
 h+=orch+sse+mcpRow+up+'<div class="actions"><button onclick="renderServices()">'+t('btn_recheck')+'</button></div></section>';
 q('#workspace').innerHTML=h;}catch(e){notice(e.message,'err')}
}
function svcRow(label,s){var up=s.state==='up'||s.state==='success'||s.state==='idle';var st=s.state||'unknown';var cls=up?'ok':'err';var extra=s.error?esc(s.error):(s.latency!==undefined?(t('latency')+' '+s.latency.toFixed(2)+'s'):'');return '<div class="orch"><strong>'+esc(label)+'</strong> <span class="badge" data-state="'+esc(st)+'">'+esc(st)+'</span><br><span class="help">'+extra+'</span></div>'}

async function loadAll(){
 try{var results=await Promise.all([api('/api/state'),api('/api/config'),api('/api/update/status')]);STATE=results[0];CONFIG=results[1];UPDATE={status:results[2]};showTab(CURTAB);}
 catch(e){notice(e.message,'err')}
}
function renderOrchestrators(){
 var list=(STATE.orchestrators||[]).map(function(o){return '<div class="orch"><span class="orch-actions"><button class="secondary" onclick="probeTarget(\'orchestrator\',\'+esc(o.name)+\')">'+t('btn_probe')+'</button><button class="secondary" onclick="dupTarget(\'orchestrator\',\'+esc(o.name)+\')">'+t('btn_dup')+'</button><button class="secondary" onclick="renTarget(\'orchestrator\',\'+esc(o.name)+\')">'+t('btn_ren')+'</button><button class="secondary" onclick="setDefaultTarget(\'orchestrator\',\'+esc(o.name)+\')">'+t('btn_default')+'</button><button class="secondary" onclick="editOrch(\'+'+esc(o.name)+'\')">'+t('btn_edit')+'</button><button class="danger" onclick="deleteOrch(\'+'+esc(o.name)+'\')">'+t('btn_delete')+'</button></span><strong>'+esc(o.name)+'</strong> '+(o.active?'<span class="badge">'+t('badge_active')+'</span>':'')+(o.default?'<span class="badge">'+t('badge_default')+'</span>':'')+'<br><span class="help">'+esc(o.url)+'</span> <span id="probe-orchestrator-'+esc(o.name)+'"></span></div>'}).join('')||'<p class="help">'+t('no_orch')+'</p>';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_orch')+'</h2>'+list+
 '<div class="group"><h3>'+t('add_update')+'</h3><div class="grid"><label>'+t('f_name')+'<input id="o-name"></label><label>'+t('f_url')+'<input id="o-url" placeholder="https://orchestrator.example.com"></label><label>'+t('f_apikey')+'<input id="o-key" type="password"></label><label>'+t('f_user')+'<input id="o-user"></label><label>'+t('f_pass')+'<input id="o-password" type="password"></label><label>'+t('f_tls')+'<select id="o-tls"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select></label><label>'+t('f_ssh_user')+'<input id="o-ssh-user"></label><label>'+t('f_ssh_pass')+'<input id="o-ssh-password" type="password"></label><label>'+t('f_enable')+'<input id="o-enable" type="password"></label><label>'+t('f_ssh_host')+'<input id="o-ssh-host"></label></div><div class="actions"><button onclick="saveOrch()">'+t('btn_save')+'</button><button class="secondary" onclick="applyOrch()">'+t('apply_env')+'</button></div></div></section>';
}
function editOrch(name){var o=(STATE.orchestrators||[]).find(function(x){return x.name===name});if(!o)return;q('#o-name').value=o.name;q('#o-url').value=o.url;q('#o-tls').value=String(o.verify_tls);q('#o-ssh-user').value=o.ssh_user||'';q('#o-ssh-host').value=o.ssh_host||''}
async function saveOrch(){
 try{var r=await api('/api/orchestrators',{name:q('#o-name').value.trim(),url:q('#o-url').value.trim(),api_key:q('#o-key').value,username:q('#o-user').value,password:q('#o-password').value,verify_tls:q('#o-tls').value==='true',ssh_user:q('#o-ssh-user').value,ssh_password:q('#o-ssh-password').value,ssh_enable_password:q('#o-enable').value,ssh_host:q('#o-ssh-host').value});notice(r.message||r.error,r.ok?'ok':'err');STATE=await api('/api/state');renderOrchestrators()}catch(e){notice(e.message,'err')}
}
async function deleteOrch(name){if(!confirm('Eliminar '+name+'?'))return;await api('/api/orchestrators/delete',{name:name});STATE=await api('/api/state');renderOrchestrators()}
async function applyOrch(){try{var r=await api('/api/apply',{name:q('#o-name').value.trim(),kind:'orchestrator'});notice(r.message||r.error,r.ok?'ok':'err');CONFIG=await api('/api/config')}catch(e){notice(e.message,'err')}}
function renderSse(){
 var list=(STATE.sse_platforms||[]).map(function(o){return '<div class="orch"><span class="orch-actions"><button class="secondary" onclick="probeTarget(\'sse\',\'+esc(o.name)+\')">'+t('btn_probe')+'</button><button class="secondary" onclick="dupTarget(\'sse\',\'+esc(o.name)+\')">'+t('btn_dup')+'</button><button class="secondary" onclick="renTarget(\'sse\',\'+esc(o.name)+\')">'+t('btn_ren')+'</button><button class="secondary" onclick="setDefaultTarget(\'sse\',\'+esc(o.name)+\')">'+t('btn_default')+'</button><button class="secondary" onclick="editSse(\'+'+esc(o.name)+'\')">'+t('btn_edit')+'</button><button class="danger" onclick="deleteSse(\'+'+esc(o.name)+'\')">'+t('btn_delete')+'</button></span><strong>'+esc(o.name)+'</strong> '+(o.active?'<span class="badge">'+t('badge_active')+'</span>':'')+(o.default?'<span class="badge">'+t('badge_default')+'</span>':'')+' <span class="badge">'+esc(o.provider)+'</span><br><span class="help">'+esc(o.base_url)+'</span> <span id="probe-sse-'+esc(o.name)+'"></span></div>'}).join('')||'<p class="help">'+t('no_sse')+'</p>';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_sse')+'</h2><p>Administra N plataformas SSE de forma independiente (p. ej. varias instancias de Axis Security). Cada una guarda su propio token y URL.</p>'+list+
 '<div class="group"><h3>'+t('add_update_sse')+'</h3><div class="grid"><label>'+t('f_name')+'<input id="s-name" placeholder="axis-prod"></label><label>'+t('f_provider')+'<select id="s-provider"><option>axis</option></select></label><label>'+t('f_baseurl')+'<input id="s-url" placeholder="https://admin-api.axissecurity.com"></label><label>'+t('f_token')+'<input id="s-token" type="password"></label><label>Verificar TLS<select id="s-tls"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select></label><label>'+t('f_timeout')+'<input id="s-timeout" type="number" value="30"></label></div><div class="actions"><button onclick="saveSse()">'+t('btn_save')+'</button><button class="secondary" onclick="applySse()">'+t('apply_env')+'</button></div></div></section>';
}
function editSse(name){var o=(STATE.sse_platforms||[]).find(function(x){return x.name===name});if(!o)return;q('#s-name').value=o.name;q('#s-provider').value=o.provider;q('#s-url').value=o.base_url;q('#s-tls').value=String(o.verify_tls);q('#s-timeout').value=o.timeout}
async function saveSse(){
 try{var r=await api('/api/sse',{name:q('#s-name').value.trim(),provider:q('#s-provider').value,base_url:q('#s-url').value.trim(),admin_token:q('#s-token').value,verify_tls:q('#s-tls').value==='true',timeout:q('#s-timeout').value});notice(r.message||r.error,r.ok?'ok':'err');STATE=await api('/api/state');renderSse()}catch(e){notice(e.message,'err')}
}
async function deleteSse(name){if(!confirm('Eliminar plataforma '+name+'?'))return;await api('/api/sse/delete',{name:name});STATE=await api('/api/state');renderSse()}
async function applySse(){try{var r=await api('/api/apply',{name:q('#s-name').value.trim(),kind:'sse'});notice(r.message||r.error,r.ok?'ok':'err');CONFIG=await api('/api/config')}catch(e){notice(e.message,'err')}}
async function renderWizard(){
 if(!WIZARD){
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_wizard')+'</h2><p class="help">'+t('wiz_loading')+'</p></section>';
  try{WIZARD=await api('/api/wizard')}catch(e){notice(e.message,'err');return}
  WSTEP=0;WDRAFT={};
  WIZARD.fields.forEach(function(f){WDRAFT[f.key]=f.secret?'':f.value});
 }
 wizRenderStep();
}
function wizFields(stepId){return WIZARD.fields.filter(function(f){return f.step===stepId})}
function wizDependsOk(f){
 if(!f.depends_on)return true;
 var cur=WIZARD.fields.find(function(x){return x.key===f.depends_on[0]});
 var v=WDRAFT[f.depends_on[0]];
 if(v===undefined||v===null||v==='')v=cur?cur.value:'';
 return String(v)===f.depends_on[1];
}
function wizFieldHtml(f){
 var id='wiz-'+f.key,input='';
 if(f.kind==='boolean')input='<select id="'+id+'" data-wiz="'+f.key+'"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select>';
 else if(f.kind==='choice')input='<select id="'+id+'" data-wiz="'+f.key+'">'+f.choices.map(function(v){return '<option>'+esc(v)+'</option>'}).join('')+'</select>';
 else input='<input id="'+id+'" data-wiz="'+f.key+'" type="'+(f.secret?'password':(f.kind==='integer'||f.kind==='number'?'number':'text'))+'" placeholder="'+(f.secret&&f.configured?'Configurado; vacío conserva el secreto':'')+'">';
 var req=f.required?' <span class="req">*</span>':'';
 return '<div class="field" data-field="'+f.key+'" style="'+(wizDependsOk(f)?'':'display:none')+'"><label>'+esc(f['label_'+LANG]||f.label)+req+input+'</label>'+(f.secret?'<span class="secret-note">'+(f.configured?t('secret_set'):t('secret_unset'))+'</span>':'')+((f['help_'+LANG]||f.help)?'<span class="help">'+esc(f['help_'+LANG]||f.help)+'</span>':'')+'</div>';
}
function wizRenderStep(){
 var steps=WIZARD.steps,s=steps[WSTEP],fields=wizFields(s.id);
 var bar=steps.map(function(st,i){return '<span class="badge" style="'+(i===WSTEP?'border-color:#38bdf8;color:#bae6fd':'')+'">'+(i+1)+' '+esc(st['title_'+LANG]||st.title)+'</span>'}).join(' ');
 var targets=s.id==='targets'?wizTargetsHtml():'';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('wiz_step',{a:WSTEP+1,b:steps.length})+' '+esc(s['title_'+LANG]||s.title)+'</h2><div class="wizbar">'+bar+'</div>'+
  (s.id==='targets'?'<p class="help">'+t('wiz_targets_help')+'</p>':'')+
  '<div class="group"><div class="grid">'+fields.map(wizFieldHtml).join('')+'</div></div>'+targets+
  '<div class="actions"><button class="secondary" onclick="wizBack()" '+(WSTEP===0?'disabled':'')+'>'+t('btn_back')+'</button><button onclick="wizNext()">'+(WSTEP===steps.length-1?t('btn_review'):t('btn_next'))+'</button></div></section>';
 fields.forEach(function(f){var el=q('#wiz-'+f.key);if(el){if(!f.secret)el.value=(WDRAFT[f.key]!==undefined?WDRAFT[f.key]:f.value);el.addEventListener('change',function(){WDRAFT[f.key]=el.value;wizRefreshDepends()})}});
 wizRefreshDepends();
}
function wizRefreshDepends(){WIZARD.fields.forEach(function(f){if(!f.depends_on)return;var n=document.querySelector('[data-field="'+f.key+'"]');if(n)n.style.display=wizDependsOk(f)?'':'none'})}
function wizValidateStep(){
 var errs=[];
 wizFields(WIZARD.steps[WSTEP].id).forEach(function(f){
  if(!wizDependsOk(f))return;
  var el=q('#wiz-'+f.key),v=el?el.value:'';
  if(f.required&&v==='')errs.push(f.label+' ('+f.key+') es obligatorio');
  if(f.kind==='url'&&v&&!/^https?:\/\/[^\s]+/.test(v))errs.push(f.key+': URL inválida (http/https)');
  if((f.kind==='integer'||f.kind==='number')&&v!==''){var n=Number(v);if(isNaN(n))errs.push(f.key+': debe ser numérico');else{if(f.minimum!==null&&f.minimum!==undefined&&n<f.minimum)errs.push(f.key+': mínimo '+f.minimum);if(f.maximum!==null&&f.maximum!==undefined&&n>f.maximum)errs.push(f.key+': máximo '+f.maximum)}}
 });
 return errs;
}
function wizCollect(){var values={};WIZARD.fields.forEach(function(f){var el=q('#wiz-'+f.key);if(!el)return;var v=el.value;if(f.secret){if(v!=='')values[f.key]=v}else values[f.key]=v});return values}
async function wizNext(){
 var errs=wizValidateStep();
 wizFields(WIZARD.steps[WSTEP].id).forEach(function(f){var el=q('#wiz-'+f.key);if(el)WDRAFT[f.key]=el.value});
 if(errs.length){notice(errs.join('\n'),'err');return}
 if(WSTEP<WIZARD.steps.length-1){WSTEP++;wizRenderStep();return}
 await wizReview();
}
function wizBack(){if(WSTEP>0){WSTEP--;wizRenderStep()}}
async function wizReview(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('review_title')+'</h2><p class="help">'+t('review_desc')+'<span class="mono">'+esc(WIZARD.env_file)+'</span>'+t('review_nowrite')+'</p><div id="wiz-diff">Comprobando...</div><div class="actions"><button class="secondary" onclick="wizBack()">'+t('btn_back')+'</button><button onclick="wizSave(false)">'+t('btn_save_vars')+'</button><button onclick="wizSave(true)">'+t('btn_save_restart_short')+'</button></div></section>';
 try{
  var r=await api('/api/config/diff',{values:wizCollect()});
  var h='';
  if(r.errors&&r.errors.length)h+='<div class="msg err">'+r.errors.map(esc).join('<br>')+'</div>';
  if(r.changes&&r.changes.length)h+='<table class="diff">'+r.changes.map(function(c){return '<tr><td class="mono">'+esc(c.key)+'</td><td class="mono">'+(c.cleared?'(eliminar secreto)':esc(c.old))+'</td><td>→</td><td class="mono">'+esc(c.new)+'</td></tr>'}).join('')+'</table>';
  else if(!r.errors||!r.errors.length)h+='<p class="help">'+t('no_changes')+'</p>';
  h+='<h3 style="margin-top:16px">'+t('targets_h')+'</h3>'+wizTargetsHtml();
  q('#wiz-diff').innerHTML=h;
 }catch(e){q('#wiz-diff').innerHTML='<div class="msg err">'+esc(e.message)+'</div>'}
}
async function wizSave(restart){
 try{
  var r=await api('/api/config',{values:wizCollect()});
  if(!r.ok){notice(r.error||'Error al guardar','err');return}
  notice(r.message,'ok');CONFIG=await api('/api/config');
  if(restart)await doRestart();else{WIZARD=null;WSTEP=0;await renderWizard()}
 }catch(e){notice(e.message,'err')}
}
function wizTargetRow(o,kind,urlField){
 return '<div class="orch"><span class="orch-actions">'+
  '<button class="secondary" onclick="probeTarget(\''+kind+'\',\''+esc(o.name)+'\')">'+t('btn_probe')+'</button>'+
  '<button class="secondary" onclick="dupTarget(\''+kind+'\',\''+esc(o.name)+'\')">'+t('btn_dup')+'</button>'+
  '<button class="secondary" onclick="renTarget(\''+kind+'\',\''+esc(o.name)+'\')">'+t('btn_ren')+'</button>'+
  '<button class="secondary" onclick="setDefaultTarget(\''+kind+'\',\''+esc(o.name)+'\')">'+t('btn_default')+'</button>'+
  '<button class="danger" onclick="delTarget(\''+kind+'\',\''+esc(o.name)+'\')">'+t('btn_delete')+'</button></span>'+
  '<strong>'+esc(o.name)+'</strong> '+(o.active?'<span class="badge">'+t('badge_active')+'</span>':'')+(o.default?'<span class="badge">'+t('badge_default')+'</span>':'')+'<br><span class="help">'+esc(o[urlField]||'')+'</span> <span id="probe-'+kind+'-'+esc(o.name)+'"></span></div>';
}
function wizTargetsHtml(){
 var st=WIZARD.state||{};
 var orch=(st.orchestrators||[]).map(function(o){return wizTargetRow(o,'orchestrator','url')}).join('')||'<p class="help">'+t('no_orch')+'</p>';
 var sse=(st.sse_platforms||[]).map(function(o){return wizTargetRow(o,'sse','base_url')}).join('')||'<p class="help">'+t('no_sse')+'</p>';
 return '<div class="group"><h3>Orquestadores</h3>'+orch+
  '<div class="grid" style="margin-top:10px"><label>'+t('f_name')+'<input id="wo-name" placeholder="prod"></label><label>'+t('f_url')+'<input id="wo-url" placeholder="https://orchestrator.example.com"></label><label>'+t('f_apikey')+'<input id="wo-key" type="password"></label><label>'+t('f_user')+'<input id="wo-user"></label><label>'+t('f_pass')+'<input id="wo-pass" type="password"></label></div><div class="actions"><button onclick="wizSaveOrch()">'+t('btn_save_orch')+'</button></div></div>'+
  '<div class="group"><h3>Plataformas SSE</h3>'+sse+
  '<div class="grid" style="margin-top:10px"><label>'+t('f_name')+'<input id="ws-name" placeholder="axis-prod"></label><label>'+t('f_baseurl')+'<input id="ws-url" placeholder="https://admin-api.axissecurity.com"></label><label>'+t('f_token')+'<input id="ws-token" type="password"></label><label>'+t('f_timeout')+'<input id="ws-timeout" type="number" value="30"></label></div><div class="actions"><button onclick="wizSaveSse()">'+t('btn_save_sse')+'</button></div></div>';
}
async function reloadAfterMutation(){
 STATE=await api('/api/state');
 if(CURTAB==='wizard'){WIZARD=null;WSTEP=0;await renderWizard()}else showTab(CURTAB);
}
async function wizSaveOrch(){
 try{var r=await api('/api/orchestrators',{name:q('#wo-name').value.trim(),url:q('#wo-url').value.trim(),api_key:q('#wo-key').value||null,username:q('#wo-user').value||null,password:q('#wo-pass').value||null,verify_tls:true});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function wizSaveSse(){
 try{var r=await api('/api/sse',{name:q('#ws-name').value.trim(),provider:'axis',base_url:q('#ws-url').value.trim(),admin_token:q('#ws-token').value||null,verify_tls:true,timeout:q('#ws-timeout').value});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function probeTarget(kind,name){
 var node=document.getElementById('probe-'+kind+'-'+name);if(node)node.textContent=' '+t('probing')+'';
 try{var r=await api('/api/probe',{kind:kind,name:name});if(node)node.innerHTML=' <span class="badge">'+(r.ok?'up':'down')+'</span>';notice((r.ok?t('probe_ok'):t('probe_fail'))+kind+' '+name+(r.error?' — '+r.error:''),r.ok?'ok':'err')}
 catch(e){notice(e.message,'err')}
}
async function dupTarget(kind,name){
 var nn=prompt('Nuevo nombre para duplicar '+name+':',name+'-copia');if(!nn)return;
 var path=kind==='sse'?'/api/sse/duplicate':'/api/orchestrators/duplicate';
 try{var r=await api(path,{name:name,new_name:nn.trim()});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function renTarget(kind,name){
 var nn=prompt('Renombrar '+name+' a:',name);if(!nn||nn.trim()===name)return;
 var path=kind==='sse'?'/api/sse/rename':'/api/orchestrators/rename';
 try{var r=await api(path,{name:name,new_name:nn.trim()});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function delTarget(kind,name){
 if(!confirm('Eliminar '+name+'?'))return;
 var path=kind==='sse'?'/api/sse/delete':'/api/orchestrators/delete';
 try{await api(path,{name:name});await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function setDefaultTarget(kind,name){
 try{var r=await api('/api/default',{kind:kind,name:name});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function renderUsers(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_users')+'</h2><p class="help">'+t('loading')+'</p></section>';
 try{
  var r=await api('/api/users');
  var rows=(r.users||[]).map(function(u){return '<div class="orch"><strong>'+esc(u.username)+'</strong> <span class="badge">'+esc(u.role)+'</span><span class="orch-actions"><button class="danger" onclick="delUser(\''+esc(u.username)+'\')">'+t('btn_delete')+'</button></span></div>'}).join('')||'<p class="help">'+t('no_users')+'</p>';
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_users')+'</h2><p class="help">'+t('users_file')+' <span class="mono">'+esc(r.file)+'</span> · roles: '+esc((r.roles||[]).join(', '))+'. '+t('hashes_note')+'</p>'+rows+
  '<div class="group"><h3>'+t('add_user')+'</h3><div class="grid"><label>'+t('u_name')+'<input id="u-name"></label><label>'+t('u_pass')+'<input id="u-pass" type="password" autocomplete="new-password"></label><label>'+t('u_role')+'<select id="u-role"><option>viewer</option><option>operator</option><option>admin</option></select></label></div><div class="actions"><button onclick="saveUser()">Guardar usuario</button></div></div>'+
  '<div class="group"><h3>'+t('change_pass')+'</h3><div class="grid"><label>'+t('u_empty')+'<input id="p-user"></label><label>'+t('u_old')+'<input id="p-old" type="password" autocomplete="current-password"></label><label>'+t('u_new')+'<input id="p-new" type="password" autocomplete="new-password"></label></div><div class="actions"><button onclick="changePass()">Cambiar contraseña</button></div></div></section>';
 }catch(e){notice(e.message,'err')}
}
async function saveUser(){
 try{var r=await api('/api/users',{username:q('#u-name').value.trim(),password:q('#u-pass').value,role:q('#u-role').value});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await renderUsers()}catch(e){notice(e.message,'err')}
}
async function delUser(name){
 if(!confirm('Eliminar usuario '+name+'?'))return;
 try{var r=await api('/api/users/delete',{username:name});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await renderUsers()}catch(e){notice(e.message,'err')}
}
async function changePass(){
 try{var r=await api('/api/users/password',{username:q('#p-user').value.trim(),old_password:q('#p-old').value,new_password:q('#p-new').value});notice(r.message||r.error,r.ok?'ok':'err')}catch(e){notice(e.message,'err')}
}

var CFG_TAB='global';
function cfgTargets(){
 var r=[];
 (STATE.orchestrators||[]).forEach(function(o){r.push({id:'orchestrator:'+o.name,label:o.name,obj:o,kind:'orchestrator'})});
 (STATE.sse_platforms||[]).forEach(function(o){r.push({id:'sse:'+o.name,label:o.name,obj:o,kind:'sse'})});
 return r;
}
function targetsNavHtml(){
 var ts=cfgTargets();if(!ts.length)return '';
 var h='<div class="wizbar"><button class="secondary" style="padding:5px 10px;font-size:.78rem'+'" onclick="cfgTab(\'global\')">'+t('global_vars')+'</button>';
 ts.forEach(function(x){h+='<button class="secondary" style="padding:5px 10px;font-size:.78rem" onclick="cfgTab(\''+esc(x.id)+'\')">'+esc(x.label)+'</button>'});
 return h+'</div>';
}
function cfgTab(id){CFG_TAB=id;renderConfig()}
function targetPanelHtml(x){
 var o=x.obj;
 var rows=[['URL',o.url||o.base_url],['username',o.username||''],['ssh_host',o.ssh_host||''],['ssh_user',o.ssh_user||'']];
 var flags=[];
 if(o.has_api_key)flags.push('api_key');if(o.has_password)flags.push('password');if(o.has_ssh_password)flags.push('ssh_password');if(o.has_enable_password)flags.push('enable_password');if(o.has_admin_token)flags.push('admin_token');
 return '<div class="orch"><strong>'+esc(o.name)+'</strong> <span class="badge">'+t(x.kind==='sse'?'h2_sse':'h2_orch')+'</span> '+(o.active?'<span class="badge" style="color:#075842;background:#d8f8eb">'+t('badge_active')+'</span>':'')+(o.default?'<span class="badge" style="color:#075842;background:#d8f8eb">'+t('badge_default')+'</span>':'')+'<dl class="kv">'+rows.filter(function(r){return r[1]}).map(function(r){return '<dt>'+esc(r[0])+'</dt><dd class="mono">'+esc(r[1])+'</dd>'}).join('')+'<dt>verify_tls</dt><dd>'+(o.verify_tls?t('yes'):t('no'))+'</dd>'+(o.timeout!==undefined?'<dt>timeout</dt><dd>'+esc(o.timeout)+'</dd>':'')+'</dl>'+(flags.length?'<p class="help">secretos: '+flags.join(', ')+'</p>':'')+'<p class="help">'+t('target_info')+' · '+esc(o.name)+'</p></div>';
}
function blobsInfoHtml(){
 var b=STATE.blobs||{};
 return '<p class="help">EC_ORCHESTRATORS_JSON: '+(b.orchestrators?t('blob_set'):t('blob_unset'))+' · EC_SSE_PLATFORMS_JSON: '+(b.sse?t('blob_set'):t('blob_unset'))+'</p>';
}
async function renderTls(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('tls_title')+'</h2><p class="help">'+t('tls_desc')+'</p><p class="help">'+t('checking')+'</p></section>';
 try{
  var r=await api('/api/tls');
  var canWrite=ME&&ME.role!=='viewer';
  var st=r.cert_present?'<div class="cert-status active"><strong>'+t('tls_installed')+'</strong>'+(r.subject?'<span>'+t('tls_subject')+': '+esc(r.subject)+'</span>':'')+(r.issuer?'<span>'+t('tls_issuer')+': '+esc(r.issuer)+'</span>':'')+(r.expires_at?'<span>'+t('tls_expires')+': '+esc(r.expires_at)+'</span>':'')+(r.fingerprint?'<span>'+t('tls_fp')+': <span class="mono">'+esc(r.fingerprint)+'</span></span>':'')+'</div>':'<div class="cert-status"><strong>'+t('tls_none')+'</strong></div>';
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('tls_title')+'</h2><p class="help">'+t('tls_desc')+'</p>'+(r.enabled?'<span class="badge" style="color:#075842;background:#d8f8eb;border-color:#65cba9">'+t('tls_enabled')+'</span>':'<span class="badge">'+t('tls_disabled')+'</span>')+st+
  '<div class="group"><h3>'+t('tls_install')+'</h3>'+
  '<label>'+t('tls_mode')+'<select id="tls-mode" onchange="tlsModeChange()"><option value="pem">'+t('fmt_pem')+'</option><option value="pem-bundle">'+t('fmt_bundle')+'</option><option value="pfx">'+t('fmt_pfx')+'</option><option value="der">'+t('fmt_der')+'</option></select></label>'+
  '<label id="tls-cert-label">'+t('tls_cert_file')+'<input id="tls-cert" type="file" accept=".pem,.crt,.cer,.der,.pfx,.p12,.pkcs12"></label>'+
  '<label id="tls-key-label">'+t('tls_key_file')+'<input id="tls-key" type="file" accept=".pem,.key,.der"></label>'+
  '<label>'+t('tls_pw')+'<input id="tls-pw" type="password" autocomplete="new-password"></label>'+
  '<p class="help">'+t('tls_note')+'</p><code class="confirm-code">'+t('tls_confirm_code')+'</code><label>'+t('tls_confirm')+'<input id="tls-confirm"></label>'+
  '<div class="actions">'+(canWrite?'<button onclick="saveTls()">'+t('tls_upload')+'</button><button class="danger" onclick="delTls()">'+t('tls_delete')+'</button>':'')+'</div></div></section>';
 }catch(e){notice(e.message,'err')}
}
function tlsModeChange(){
 var m=q('#tls-mode').value;
 var keyRow=q('#tls-key-label');if(keyRow)keyRow.style.display=(m==='pem'||m==='der')?'':'none';
 var cl=q('#tls-cert-label');if(cl&&cl.firstChild)cl.firstChild.textContent=(m==='pfx'?t('tls_pfx_file'):m==='pem-bundle'?t('tls_bundle_file'):t('tls_cert_file'));
 var ci=q('#tls-cert');if(ci)ci.accept=m==='pfx'?'.pfx,.p12,.pkcs12':m==='der'?'.der,.cer,.crt':'.pem,.crt,.cer';
}
async function fileB64(id){
 var f=q(id);if(!f||!f.files||!f.files[0])return '';
 var file=f.files[0];if(file.size>3000000){notice(t('file_too_big'),'err');return ''}
 return await new Promise(function(res,rej){var r=new FileReader();r.onload=function(){res(String(r.result).split(',')[1]||'')};r.onerror=rej;r.readAsDataURL(file)});
}
async function saveTls(){
 try{
  var r=await api('/api/tls/upload',{mode:q('#tls-mode').value,certificateData:await fileB64('#tls-cert'),keyData:await fileB64('#tls-key'),password:q('#tls-pw').value,confirmation:q('#tls-confirm').value});
  notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await renderTls();
 }catch(e){notice(e.message,'err')}
}
async function delTls(){
 if(!confirm(t('tls_delete')+'?'))return;
 try{var r=await api('/api/tls/delete',{});notice(r.message||r.error,r.ok?'ok':'err');await renderTls()}catch(e){notice(e.message,'err')}
}
async function renderTools(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('tools_title')+'</h2><p class="help">'+t('tools_desc')+'</p><p class="help">'+t('checking')+'</p></section>';
 try{
  var r=await api('/api/tools');
  var canWrite=ME&&ME.role!=='viewer';
  var rows=r.tools.map(function(x){return '<div class="tool-card"><div><strong>'+esc(x.name)+'</strong><span class="help">'+esc(x.description)+'</span></div><label class="switch" title="'+(x.disabled?t('tool_off'):t('tool_on'))+'"><input type="checkbox" '+(x.disabled?'':'checked')+' '+(canWrite?'onchange="toggleTool(\''+esc(x.name)+'\',this.checked)"':'disabled')+'><span class="slider"></span></label></div>'}).join('');
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('tools_title')+'</h2><p class="help">'+t('tools_desc')+'</p><p><span class="badge">'+r.total+'</span> '+t('tools_total')+' · <span class="badge">'+r.disabled.length+'</span> '+t('tools_disabled')+'</p><div class="actions"><button class="secondary" onclick="showAgentPrompt()">'+t('agent_btn')+'</button></div><div class="tools-grid" id="tools-list">'+rows+'</div></section>';
 }catch(e){notice(e.message,'err')}
}
async function toggleTool(name,enabled){
 try{var r=await api('/api/tools/toggle',{name:name,enabled:enabled});notice(r.ok?((enabled?t('tool_on'):t('tool_off'))+' '+name):(r.error||'Error'),r.ok?'ok':'err');if(r.ok)await renderTools()}catch(e){notice(e.message,'err')}
}
async function showAgentPrompt(){
 try{var r=await api('/api/agent-prompt');if(!q('#agent-dlg'))q('#app').innerHTML+=agentDialogHtml();q('#agent-text').textContent=r.prompt;var d=q('#agent-dlg');d.showModal?d.showModal():d.setAttribute('open','')}catch(e){notice(e.message,'err')}
}
function agentDialogHtml(){return '<dialog id="agent-dlg" style="max-width:780px;width:calc(100% - 30px)"><h3>'+t('agent_title')+'</h3><p class="help">'+t('agent_desc')+'</p><pre id="agent-text" style="max-height:52vh;overflow:auto;background:#f6f8f9;border:1px solid var(--line);border-radius:4px;padding:12px;font-size:11px;white-space:pre-wrap"></pre><div class="actions"><button onclick="copyAgent()">'+t('copy')+'</button><button class="secondary" onclick="closeAgent()">'+t('custom_cancel')+'</button></div></dialog>'}
function copyAgent(){var el=q('#agent-text');if(el&&navigator.clipboard){navigator.clipboard.writeText(el.textContent)}notice(t('copied'),'ok')}
function closeAgent(){var d=q('#agent-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
function fieldHtml(f){
 var id='cfg-'+f.key, input='';
 if(f.kind==='boolean')input='<select id="'+id+'" data-key="'+f.key+'"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select>';
 else if(f.kind==='choice')input='<select id="'+id+'" data-key="'+f.key+'">'+f.choices.map(function(v){return '<option>'+esc(v)+'</option>'}).join('')+'</select>';
 else input='<input id="'+id+'" data-key="'+f.key+'" type="'+(f.secret?'password':(f.kind==='integer'||f.kind==='number'?'number':'text'))+'" value="'+esc(f.value)+'" placeholder="'+(f.secret&&f.configured?'Configurado; vacío conserva el secreto':'')+'">';
 var clear=f.secret&&f.configured?'<label class="clear"><input type="checkbox" data-clear="'+f.key+'">'+t('clear_secret')+'</label>':'';
 return '<div class="field"><label>'+esc(f['label_'+LANG]||f.label)+input+'</label>'+(f.secret?'<span class="secret-note">'+(f.configured?t('secret_set'):t('secret_unset'))+'</span>':'')+((f['help_'+LANG]||f.help)?'<span class="help">'+esc(f['help_'+LANG]||f.help)+'</span>':'')+clear+'</div>';
}
function renderConfig(){
 if(!CONFIG){q('#workspace').innerHTML='<section class="panel">Cargando variables...</section>';return}
 if(CFG_TAB!=='global'){var ts=cfgTargets();var x=ts.find(function(v){return v.id===CFG_TAB});q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_config')+'</h2>'+targetsNavHtml()+(x?targetPanelHtml(x):'<p class="help">'+t('no_orch')+'</p>')+'</section>';return}
 var groups={};CONFIG.fields.forEach(function(f){var gk=f['group_'+LANG]||f.group;(groups[gk]||(groups[gk]=[])).push(f)});
 var stepOrder={};(CONFIG.steps||[]).forEach(function(s,i){stepOrder[s.id]=i});var gnames=Object.keys(groups).sort(function(a,b){var fa=groups[a][0],fb=groups[b][0];return (stepOrder[fa.step]??99)-(stepOrder[fb.step]??99)||a.localeCompare(b)});var html=gnames.map(function(name){return '<details class="group" open><summary><h3>'+esc(name)+'<span class="count">'+groups[name].length+'</span></h3></summary><div class="grid">'+groups[name].map(fieldHtml).join('')+'</div></details>'}).join('');
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_config')+'</h2><p>'+t('saved_in')+'<span class="mono">'+esc(CONFIG.env_file)+'</span>. '+t('secrets_note')+'</p>'+targetsNavHtml()+html+blobsInfoHtml()+'<div class="actions"><button onclick="saveConfig()">'+t('btn_save_vars')+'</button><button class="secondary" onclick="restartServices()">'+t('btn_save_restart')+'</button></div></section>';
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
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_update')+'</h2><p>Detecta la rama configurada, fija el commit exacto y delega la instalación a un worker separado. Para repositorios privados configura usuario y token en <b>Variables → Actualizaciones</b>.</p><div class="group"><h3>Estado del worker</h3><p><span class="badge">'+esc(s.state||'idle')+'</span> '+esc(s.message||'Sin operaciones pendientes')+'</p>'+(s.diagnostic?'<pre class="mono">'+esc(s.diagnostic)+'</pre>':'')+'</div><div id="update-detail"></div><div class="actions"><button onclick="checkUpdate()">'+t('btn_detect')+'</button></div></section>';
}
async function checkUpdate(){
 try{var r=await api('/api/update/check',{});if(r.error)throw new Error(r.error);UPDATE=r;var remote=r.remote;var detail='<section class="group"><h3>'+esc(r.repository)+' · '+esc(r.branch)+'</h3><p>Instalado: <span class="mono">'+esc(r.current_short_sha||'desconocido')+'</span><br>GitHub: <span class="mono">'+esc(remote.short_sha)+'</span> · '+esc(remote.message)+'</p><p>'+(r.update_available?'Hay una actualización disponible.':'No hay una actualización pendiente o no se pudo determinar el commit instalado.')+'</p>';if(r.update_available)detail+='<label>Confirmación<input id="update-confirm" placeholder="'+esc(r.confirmation)+'"></label><div class="actions"><button onclick="applyUpdate(\''+esc(remote.sha)+'\',\''+esc(r.confirmation)+'\')">'+t('btn_apply_update')+'</button></div>';detail+='</section>';q('#update-detail').innerHTML=detail;notice('GitHub consultado correctamente.','ok')}catch(e){notice(e.message,'err')}
}
async function applyUpdate(sha,expected){var confirmation=q('#update-confirm').value;if(confirmation!==expected){notice('Escribe exactamente: '+expected,'err');return}try{var r=await api('/api/update/apply',{remote_sha:sha,confirmation:confirmation});notice(r.message||r.error,r.state==='pending'?'ok':'err');UPDATE.status=r;setTimeout(pollStatus,2000)}catch(e){notice(e.message,'err')}}
async function pollStatus(){try{var s=await api('/api/update/status');UPDATE.status=s;renderUpdate();if(s.state==='pending'||s.state==='running')setTimeout(pollStatus,3000)}catch(e){notice(e.message,'err')}}
renderLogin();
</script></body></html>"""
