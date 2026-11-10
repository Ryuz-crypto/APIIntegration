"""Self-contained administration page for ec-mcp."""

PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>EdgeConnect MCP · Centro de administración</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light;--green:#01a982;--ink:#102a43;--cyan:#00c8ff;--brand-header:#073b4c;--blue:#00739d;--rose:#d94f70;--gold:#f2b900;--line:#c8d6df;--page-bg:#edf5f6;--surface:#fff;--text:#102a43;--muted:#5d7480;--brand:var(--green);--brand-header:#073b4c;--cyan:#00c8ff}
*{box-sizing:border-box}
body{font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:var(--page-bg);color:var(--text);margin:0;min-height:100vh}
main{max-width:1500px;margin:0 auto;padding-bottom:40px}
header.topbar{min-height:68px;padding:12px 32px;display:flex;align-items:center;justify-content:space-between;gap:16px;color:#fff;background:var(--brand-header);border-bottom:4px solid transparent;position:relative;transition:background .3s ease}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--blue);outline-offset:2px}
header.topbar::after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:linear-gradient(90deg,var(--brand),var(--cyan),var(--brand));background-size:200% 100%;animation:accentbar 7s linear infinite}
@keyframes accentbar{to{background-position:200% 0}}
nav button{transition:color .15s ease,border-color .15s ease}
.tool-card{transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease}
.tool-card:hover{transform:translateY(-2px);border-left-color:var(--cyan);box-shadow:0 6px 16px rgba(16,42,67,.12)}
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
.orch::after{content:\"\";display:table;clear:both}
.orch-actions{float:right;display:flex;gap:6px}
.orch-actions button{min-height:31px;padding:5px 8px;font-size:12px}
.secret-note{font-size:11px;color:#0f766e}
.clear{display:flex;align-items:center;gap:6px;margin-top:6px;font-weight:400}
.clear input{width:auto;margin:0;min-height:0}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}
.req{color:#a12449;font-weight:800}
.diff{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
.diff td{padding:8px 10px;border-bottom:1px solid #e3eaed;vertical-align:top;word-break:break-word}.diff td.mono{word-break:break-all}
.wizbar{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.sw{width:18px;height:18px;border-radius:50%;display:inline-block;cursor:pointer;border:2px solid #fff;box-shadow:0 0 0 1px #8eabb7}
.sw.active{box-shadow:0 0 0 2px #fff,0 0 0 4px var(--brand)}
.chrome{display:flex;gap:8px;align-items:center}
.chip{display:flex;align-items:center;background:rgba(255,255,255,.08);border:1px solid #4f7080;color:#bffce8;border-radius:4px;padding:6px 10px;font-size:12px;cursor:pointer;list-style:none}
.chip:hover{border-color:var(--cyan);color:#fff}
details.menu{position:relative}
details.menu .menu-body{z-index:50;position:absolute;right:0;top:36px;background:#fff;border:1px solid var(--line);border-radius:6px;box-shadow:0 8px 24px rgba(7,59,76,.25);padding:8px;display:flex;flex-direction:column;gap:6px;min-width:200px;z-index:20}
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
.tool-card>div{min-width:0;flex:1}.tool-card .help{display:block;margin-top:3px;word-break:break-word}.tool-card .switch{margin-left:10px}
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

.powered-footer{display:flex;align-items:center;justify-content:center;gap:14px;padding:18px 32px 26px;color:#5f7681;font-size:11px}
.donate{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:999px;background:var(--gold);color:#4a3400;font-weight:800;text-decoration:none;border:1px solid #d9a900;transition:transform .12s ease,box-shadow .12s ease}
.donate:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(242,185,0,.4)}

/* Overview: a logical map, not a live traffic graph. */
.topology{margin:20px 32px 0;background:#f3f9fa;color:#102a43;border-radius:14px;border:1px solid #c8dadd;overflow:hidden}
.topology-hero{background:linear-gradient(120deg,#073b4c,#075b65 58%,#087d75);color:white;padding:30px;position:relative}
.topology-hero h1{font-size:clamp(24px,3vw,38px);line-height:1.15;margin:4px 0 8px}.topology-hero p{max-width:70ch;color:#d5eff0;margin:0}
.topology-eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#76edd5}
.topology-body{padding:24px 28px}.topology-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.topology-head h2{margin:0;font-size:20px}
.topology-flow{display:grid;grid-template-columns:minmax(160px,1fr) 36px minmax(180px,1fr) 36px minmax(240px,1.5fr);align-items:center;gap:8px;margin:22px 0}
.topology-stack{display:grid;gap:10px}.topology-arrow{text-align:center;color:#078a78;font-size:24px;font-weight:800}
.topology-card{width:100%;text-align:left;border:1px solid #c9dddd;border-radius:10px;background:#fff;color:#153746;padding:16px;min-height:112px;box-shadow:0 5px 16px rgba(7,59,76,.06);cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
.topology-card:hover{transform:translateY(-3px);box-shadow:0 12px 25px rgba(7,59,76,.14);border-color:#01a982}
.topology-card strong,.topology-card small{display:block}.topology-card strong{font-size:15px;margin:6px 0}.topology-card small{color:#526d76;line-height:1.45;overflow-wrap:anywhere}
.topology-card .tag{font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#067865}
.topology-status{display:inline-flex;align-items:center;gap:6px;border-radius:20px;padding:4px 8px;margin-top:9px;font-size:11px;font-weight:700;background:#edf2f3;color:#4c626b}
.topology-status:before{content:"";width:7px;height:7px;border-radius:50%;background:#879ba0}
.topology-status.up{background:#daf7eb;color:#096546}.topology-status.up:before{background:#0c9c68}
.topology-status.down{background:#fde9ed;color:#a32a47}.topology-status.down:before{background:#cf4665}
.topology-caption{font-size:12px;color:#526d76;line-height:1.5}.topology-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}
@media(max-width:900px){.topology{margin:16px}.topology-flow{grid-template-columns:1fr}.topology-arrow{transform:rotate(90deg)}.topology-hero{padding:23px}.topology-body{padding:20px}}


/* Navigation and logical flow; animation is decorative, not telemetry. */
.panel .brand strong{color:#102a43}.panel .brand span{color:#385563}
nav{background:#092d3b;border-bottom:1px solid #205568;gap:4px}
nav button{color:#deebef;border-bottom-color:transparent}
nav button:hover{color:#fff;background:#124857}
nav button.active-tab{color:#fff;background:#104b55;border-bottom-color:#52e7c1}
.topology{background:#071d29;border-color:#1a4b59;color:#e5f5f5}
.topology-hero{background:radial-gradient(circle at 78% 15%,rgba(0,210,188,.25),transparent 37%),linear-gradient(125deg,#061d2b,#0a4853 65%,#07665c)}
.topology-body{background:linear-gradient(155deg,#092632,#0b3440);color:#e5f5f5}
.topology-caption{color:#bfdae0}
.topology-card{background:#0e3541;color:#f4ffff;border-color:#326674;box-shadow:0 8px 22px rgba(0,0,0,.2)}
.topology-card strong{color:#fff}.topology-card small{color:#cae4e7}.topology-card .tag{color:#6df4d3}
.topology-card:hover,.topology-card:focus-visible{border-color:#5ff0ce;background:#124752;box-shadow:0 0 0 1px #48d8bc,0 12px 28px rgba(0,0,0,.25)}
.topology-detail{display:block;margin-top:9px;color:#e5f9f6;font-size:11px;line-height:1.4;opacity:.78}
.topology-card:hover .topology-detail,.topology-card:focus-visible .topology-detail{opacity:1}
.topology-arrow{font-size:0;height:2px;background:#2b807d;position:relative;overflow:visible}
.topology-arrow:after{content:"";position:absolute;width:8px;height:8px;top:-3px;left:0;border-radius:50%;background:#79ffe0;box-shadow:0 0 12px #69ffe0;animation:topology-flow 2.8s linear infinite}
@keyframes topology-flow{from{left:0;opacity:.4}50%{opacity:1}to{left:calc(100% - 8px);opacity:.4}}
[dir="rtl"] .topology-arrow:after{animation-direction:reverse}
@media(max-width:900px){.topology-arrow{width:2px;height:26px;justify-self:center;transform:none}.topology-arrow:after{left:-3px;animation:topology-flow-vertical 2.8s linear infinite}@keyframes topology-flow-vertical{from{top:0}to{top:calc(100% - 8px)}}}
@media(prefers-reduced-motion:reduce){.topology-arrow:after{animation:none}}


/* Shared console styling: preserved semantic controls and per-tool switches. */
body{background:#071d29;color:#e5f5f5}
.panel{background:#0d2c38;border-color:#275462;color:#e5f5f5;box-shadow:0 14px 35px rgba(0,0,0,.18)}
.panel h1,.panel h2,.panel h3{color:#f0fffc}
.panel .help,.panel p{color:#c4dde1}
.panel label{color:#d5eaed}
.panel .group,.panel details.group{background:#103542;border-color:#315e69}
.panel input:not([type="checkbox"]):not([type="radio"]):not([type="color"]),.panel select{background:#071f2b;color:#f1ffff;border-color:#4e7480}
.panel .tool-card{background:#103542;border-color:#315e69;color:#f1ffff}
.panel table.diff td,.panel table.diff th{color:#e5f5f5;border-color:#315e69}
.panel .badge{color:#a4ead8}
.panel .brand strong{color:#f1ffff}.panel .brand span{color:#c4dde1}
.tools-search{display:flex;align-items:end;gap:14px;flex-wrap:wrap;margin:16px 0}
.tools-search label:first-child{flex:1;min-width:220px}.tools-search label:nth-child(2){min-width:180px}
.tool-card{min-width:0}.tool-card strong{overflow-wrap:anywhere}.tools-grid{gap:12px}
.diagnostic-commands{white-space:pre-wrap;background:#071f2b;color:#d6f5ee;padding:14px;border-radius:8px;overflow:auto}
html[data-effect="quiet"] .topology-arrow:after,html[data-effect="quiet"] header.topbar::after{animation:none}
html[data-effect="pulse"] .topology-card{animation:panel-glow 4s ease-in-out infinite}
@keyframes panel-glow{0%,100%{box-shadow:0 6px 18px rgba(0,0,0,.18)}50%{box-shadow:0 0 18px rgba(1,169,130,.28)}}
@media(prefers-reduced-motion:reduce){html[data-effect="pulse"] .topology-card{animation:none}}


.monitor-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.monitor-card{background:#103542;border:1px solid #315e69;border-radius:9px;padding:14px;color:#e7f7f4;min-width:0}
.monitor-card strong,.monitor-card small{display:block}.monitor-card small{color:#c4dde1;margin-top:8px;line-height:1.4}
.monitor-value{font-size:26px;font-weight:800;margin:8px 0;color:#8aefd4}.monitor-card meter{width:100%;height:10px}


/* Shared surfaces: cards and labels use matching contrast in every tab. */
body{background:var(--console-bg,#071d29)}
.panel{background:var(--panel-bg,#0d2c38);color:var(--panel-fg,#f2ffff);border-radius:12px;min-width:0}
.panel h1,.panel h2,.panel h3,.panel label,.panel .help,.panel p,.panel table.diff td,.panel table.diff th{color:var(--panel-fg,#f2ffff)}
.panel .group,.panel details.group,.panel .orch,.panel .tool-card,.panel .monitor-card{background:var(--card-bg,#103542);color:var(--card-fg,#f2ffff);border:1px solid #53727a;border-radius:10px}
.panel .group h3,.panel .group label,.panel .group p,.panel .group .help,.panel .orch .help,.panel .orch strong,.panel .tool-card .help,.panel .monitor-card small,.panel .kv dt{color:var(--card-fg,#f2ffff)}
.panel .orch{overflow-wrap:anywhere;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.16)}
.panel .badge{background:#d9f5ec;color:#075842;border-color:#82bbad}
.panel .orch-actions{display:flex;flex-wrap:wrap;gap:6px;max-width:70%;margin-inline-start:12px}
.panel .tool-card{border-left:4px solid var(--brand)}
.panel .cert-status,.panel .cert-status span{color:#173a47}
.panel .cert-status.active,.panel .cert-status.active span{color:#075842}
.panel .msg,.panel .msg p{color:#075842}.panel .msg.err,.panel .msg.err p{color:#8b2140}.panel .msg.info,.panel .msg.info p{color:#0b4a6b}
.panel input:not([type="checkbox"]):not([type="radio"]):not([type="color"]),.panel select{background:#f7fbfc;color:#102a43;border-color:#688a97}
.panel .secret-note{color:var(--card-fg,#f2ffff)}
.panel .diff{display:block;overflow-x:auto}
.panel .group,.panel .orch,.panel .tool-card{transition:box-shadow .2s ease,transform .2s ease}
.panel .orch:hover,.panel .tool-card:hover{box-shadow:0 10px 28px rgba(0,0,0,.22),0 0 0 1px var(--brand)}
.panel h2{letter-spacing:-.02em}
@media(max-width:700px){
 header.topbar{flex-wrap:wrap;padding:12px 16px}.topbar-actions{flex-wrap:wrap;justify-content:flex-end}
 nav{padding:0 8px;scrollbar-width:thin}nav button{padding:12px}
 .panel{margin:12px 12px 0;padding:16px}.tools-grid,.grid{grid-template-columns:minmax(0,1fr)}
 .panel .orch-actions{float:none;max-width:none;margin:0 0 12px;justify-content:flex-start}
 .kv{grid-template-columns:minmax(90px,auto) minmax(0,1fr)}
 .topology{margin:12px}.color-controls{grid-template-columns:1fr 1fr}
 dialog{max-height:90vh;overflow:auto}.monitor-grid{grid-template-columns:repeat(auto-fit,minmax(130px,1fr))}
}
@media(max-width:380px){.color-controls{grid-template-columns:1fr}.topbar-actions{justify-content:flex-start}}
 .topology-card{display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;gap:4px;min-width:0;height:auto}.topology-card strong,.topology-card small,.topology-detail{width:100%;line-height:1.45;overflow-wrap:anywhere}
.topology-stack{min-width:0}.topology-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:12px}.topology-group{min-width:0;border:1px solid #326674;border-radius:10px;padding:12px;background:#092a36}.topology-group h3{margin:0 0 10px;color:#fff;font-size:14px}.topology-list{display:grid;gap:10px;max-height:410px;overflow-y:auto;padding:2px}.topology-filter{max-width:360px;background:#f7fbfc;color:#102a43;margin:0 0 12px}.topology-card[hidden]{display:none}.diagnostic-commands{max-height:300px;min-height:80px}

/* SASE overview: a compact logical flow above a full-width destination inventory. */
.topology{border-radius:20px;border:1px solid #24515e;background:#071923;box-shadow:0 24px 60px #020c1470}
.topology-hero{isolation:isolate;overflow:hidden;padding:clamp(24px,3.2vw,44px);background:radial-gradient(ellipse at 82% 20%,#1aa99638,transparent 43%),linear-gradient(122deg,#071d2a 4%,#0a3b49 63%,#07524e)}
.topology-hero:before,.topology-hero:after{content:"";position:absolute;pointer-events:none;z-index:-1;border:1px solid #5cf2d823;border-radius:50%;width:380px;height:380px;right:4%;top:-210px}
.topology-hero:after{width:500px;height:500px;right:0;top:-270px;border-color:#5cf2d815}
.topology-hero{background-size:140% 140%;animation:sase-ambient 14s ease-in-out infinite alternate}
@keyframes sase-ambient{from{background-position:0% 20%}to{background-position:100% 70%}}
html[data-effect="quiet"] .topology-hero{animation:none}
@media(prefers-reduced-motion:reduce){.topology-hero{animation:none}}
.topology-hero h1{max-width:18ch;letter-spacing:-.035em;font-weight:750}
.topology-hero p{line-height:1.65}
.sase-hero-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}
.sase-pill{display:inline-flex;align-items:center;gap:8px;border:1px solid #79d8cf46;border-radius:999px;padding:6px 11px;background:#061d2870;color:#d7f7f2;font-size:11px;font-weight:700;letter-spacing:.02em}
.sase-pill:before{content:"";width:6px;height:6px;border-radius:50%;background:#5ce5c8;box-shadow:0 0 10px #5ce5c8}
.topology-body{padding:clamp(20px,3vw,34px);background:radial-gradient(ellipse at 90% 0%,#0c596342,transparent 38%),#081f2b}
.topology-head{align-items:flex-start;margin-bottom:18px}
.topology-head h2{font-size:22px;letter-spacing:-.02em}
.topology-caption{line-height:1.55;margin:6px 0;color:#bdd4d9}
.sase-flow{display:grid;grid-template-columns:minmax(0,1fr) 44px minmax(0,1fr) 44px minmax(0,1fr);align-items:center;gap:0;margin:22px 0 28px}
.sase-node{position:relative;display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;gap:8px;width:100%;min-height:156px;text-align:start;padding:18px;border:1px solid #396773;border-radius:14px;background:linear-gradient(155deg,#103b47,#0a2b38);color:#f2ffff;box-shadow:0 12px 26px #0003}
.sase-node:hover,.sase-node:focus-visible{background:linear-gradient(155deg,#164b56,#0c3440);border-color:#72e8d0;box-shadow:0 0 0 1px #62e5cd70,0 14px 30px #0004;transform:translateY(-2px)}
.sase-node .tag{font-size:10px;letter-spacing:.12em;color:#7cebd4;font-weight:800}
.sase-node strong{font-size:16px;line-height:1.3;overflow-wrap:anywhere}
.sase-node small{font-size:12px;line-height:1.5;color:#c4dde1}
.sase-node .topology-status{margin-top:auto}
.sase-link{height:2px;position:relative;background:linear-gradient(90deg,#386f72,#57ddc3,#386f72)}
.sase-link:after{content:"";position:absolute;left:0;top:-3px;width:8px;height:8px;border-radius:50%;background:#b2ffec;box-shadow:0 0 14px #62f3d1;animation:sase-travel 3s linear infinite}
@keyframes sase-travel{from{left:0;opacity:.45}50%{opacity:1}to{left:calc(100% - 8px);opacity:.45}}
.sase-inventory{border:1px solid #285460;border-radius:16px;background:#0a2935;padding:clamp(16px,2.5vw,24px)}
.sase-inventory-head{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:18px}
.sase-inventory-head h3{margin:0;color:#f2ffff;font-size:18px}
.sase-search{display:block;flex:1 1 240px;max-width:340px;margin:0;color:#c6dfe2;font-size:12px}
.sase-search input{margin-top:7px;background:#071d29;color:#f2ffff;border:1px solid #5b8390;border-radius:9px;min-height:42px}
.sase-search input::placeholder{color:#9ebbc1}
.sase-filterbar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
.sase-filterbar button{min-height:34px;padding:6px 12px;border:1px solid #3d6874;background:#103642;color:#d9f1f0;border-radius:999px;font-size:12px}
.sase-filterbar button[aria-pressed="true"]{background:#c9fff1;color:#07352f;border-color:#c9fff1}
.topology-groups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:14px}
.topology-group{background:#0b303b;border:1px solid #285762;border-radius:13px;padding:16px;min-width:0}
.topology-group[hidden],.topology-card[hidden]{display:none}
.sase-group-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.topology-group h3{display:flex;align-items:center;gap:9px;margin:0;color:#f1ffff;font-size:14px}
.sase-count{border:1px solid #3f7881;border-radius:999px;padding:3px 9px;font-size:11px;color:#bcebe1}
.topology-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:10px;max-height:480px;overflow:auto;padding:2px}
.topology-list .topology-card{min-height:158px;margin:0;display:flex;flex-direction:column;justify-content:flex-start;gap:5px;border-radius:10px;padding:14px;background:#103c48;color:#f2ffff}
.topology-list .topology-card strong{font-size:14px;line-height:1.35;margin:2px 0;overflow-wrap:anywhere}
.topology-list .topology-card small{font-size:12px;line-height:1.45}
.topology-list .topology-card .topology-status{margin-top:auto}
.topology-list .topology-card .topology-detail{margin-top:4px;line-height:1.4}
.topology-list .topology-card[hidden]{display:none}
.topology-groups:has(>.topology-group[hidden]){grid-template-columns:minmax(0,1fr)}
.topology-list{scrollbar-width:thin;scrollbar-color:#4b9296 #0a2935}
.topology-list::-webkit-scrollbar{width:8px;height:8px}.topology-list::-webkit-scrollbar-thumb{background:#4b9296;border-radius:8px}.topology-list::-webkit-scrollbar-track{background:#0a2935}
.sase-empty{display:none;margin:12px 0 0;color:#c3d9dc;font-size:13px}
.sase-footer{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-top:18px}
.sase-footer .topology-actions{margin-top:0}
html[data-effect="quiet"] .sase-link:after{animation:none}
@media(max-width:900px){.sase-flow{grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr) 28px minmax(0,1fr)}.sase-node{padding:14px}}
@media(max-width:700px){.sase-flow{grid-template-columns:1fr;gap:0}.sase-link{width:2px;height:22px;justify-self:center}.sase-link:after{left:-3px;top:0;animation:sase-travel-v 3s linear infinite}@keyframes sase-travel-v{from{top:0}to{top:calc(100% - 8px)}}.sase-node{min-height:0}.topology-groups{grid-template-columns:1fr}.sase-search{max-width:none;flex-basis:100%}}
@media(prefers-reduced-motion:reduce){.sase-link:after{animation:none}.sase-node{transition:none}}


/* Decorative holographic interface; no animated element represents live telemetry. */
.topology-hero{min-height:280px}
.topology-hero>h1,.topology-hero>p,.topology-hero>.topology-eyebrow,.topology-hero>.sase-hero-meta{position:relative;z-index:2}
.topology-hero>p{max-width:min(55%,55ch)}
.sase-holo{position:absolute;right:5%;top:50%;width:250px;aspect-ratio:1;transform:translateY(-50%);pointer-events:none;z-index:0;filter:drop-shadow(0 0 16px #32fbd04a)}
.sase-holo:before,.sase-holo:after,.sase-orbit,.sase-core,.sase-holo-grid{content:"";position:absolute;border-radius:50%;inset:0}
.sase-holo:before{border:1px solid #66ffe477;box-shadow:inset 0 0 30px #00d9c026,0 0 25px #00d8b32b;background:repeating-conic-gradient(from 0deg,#80f8dc 0deg 1deg,transparent 1deg 14deg);mask:radial-gradient(transparent 67%,#000 69% 72%,transparent 74%);animation:sase-rotate 24s linear infinite}
.sase-holo:after{inset:12%;border:1px dashed #5cf5d78a;box-shadow:0 0 14px #45f3d04d,inset 0 0 22px #45f3d024;animation:sase-rotate 16s linear infinite reverse}
.sase-holo-grid{inset:23%;border:1px solid #55f1d999;background:linear-gradient(90deg,transparent 49.6%,#69f7df4f 50%,transparent 50.4%),linear-gradient(transparent 49.6%,#69f7df4f 50%,transparent 50.4%),radial-gradient(circle,#0d6a6870,#052734bb 75%);box-shadow:inset 0 0 28px #58f9d337}
.sase-holo-grid:before{content:"";position:absolute;inset:20%;border:1px solid #6bfce080;border-radius:50%}
.sase-orbit{inset:6%;border:1px solid transparent;border-top-color:#adffef;border-left-color:#3df5d4;animation:sase-rotate 5.5s linear infinite}
.sase-orbit:after{content:"";position:absolute;top:12%;left:15%;width:7px;height:7px;background:#ddfff6;border-radius:50%;box-shadow:0 0 15px 5px #32f4d6}
.sase-orbit.alt{inset:18%;border-color:transparent;border-right-color:#91fff0;border-bottom-color:#6df9df;animation-duration:8s;animation-direction:reverse}
.sase-orbit.alt:after{left:auto;top:auto;right:12%;bottom:13%;width:5px;height:5px}
.sase-core{inset:39%;display:grid;place-items:center;color:#ddfff8;font-weight:900;font-size:12px;letter-spacing:.1em;background:#0b5c5d;border:1px solid #a9fff0;box-shadow:0 0 22px #56f9d680,inset 0 0 15px #c2fff234;animation:sase-breathe 3.2s ease-in-out infinite}
@keyframes sase-rotate{to{transform:rotate(360deg)}}
@keyframes sase-breathe{50%{box-shadow:0 0 35px #61ffe0ba,inset 0 0 20px #d8fff667;transform:scale(1.08)}}
.sase-link{height:3px;background:linear-gradient(90deg,#35a79c,#a8ffec,#35a79c);box-shadow:0 0 12px #54f8d980}
.sase-link:after{width:10px;height:10px;top:-4px;box-shadow:0 0 8px #e6fff9,0 0 20px 5px #48f4d2}
.sase-node,.topology-list .topology-card,.panel .group{transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease,background .25s ease}
.sase-node:hover,.topology-list .topology-card:hover{transform:translateY(-4px);box-shadow:0 0 0 1px #83ffe5,0 0 25px #22ebc03d,0 18px 30px #0005}
.sase-filterbar button:hover,nav button:hover{box-shadow:inset 0 -2px #76ffdf,0 0 16px #41e9cb40}
.panel{position:relative}
.panel:before{content:"";position:absolute;left:0;right:0;top:0;height:2px;background:linear-gradient(90deg,transparent,var(--brand),var(--cyan),transparent);background-size:200% 100%;animation:sase-line 4s linear infinite;pointer-events:none}
@keyframes sase-line{to{background-position:200% 0}}
.panel .group:focus-within{border-color:var(--cyan);box-shadow:0 0 0 1px #52f5dd70,0 0 22px #3eead03a}
.panel input:focus,.panel select:focus,.panel textarea:focus{box-shadow:0 0 0 3px #47e9d75c,0 0 20px #32eacb40}
html[data-effect="quiet"] .sase-holo *,html[data-effect="quiet"] .sase-holo:before,html[data-effect="quiet"] .sase-holo:after,html[data-effect="quiet"] .panel:before{animation:none}
@media(max-width:700px){.topology-hero{min-height:225px}.topology-hero>p{max-width:75%}.sase-holo{width:150px;right:-25px;top:38%;opacity:.38}.sase-link{width:3px;height:24px}.sase-link:after{top:0;left:-4px}}
@media(prefers-reduced-motion:reduce){.sase-holo *, .sase-holo:before,.sase-holo:after,.panel:before{animation:none}.sase-node,.topology-list .topology-card,.panel .group{transition:none}}


/* Shared sci-fi chrome and contextual HUD, including user menus and dialogs. */
.panel .actions>button:not(.secondary):not(.danger),.topology-head>button{background:var(--brand);border-color:var(--brand);color:var(--brand-fg,#000)}
.sase-node,.topology-list .topology-card{background:color-mix(in srgb,var(--brand) 18%,#082630)}
.sase-inventory,.topology-group{background:color-mix(in srgb,var(--brand) 10%,#08232d)}
.panel input:not([type="checkbox"]):not([type="radio"]):not([type="color"]),.panel select,.panel textarea{background:#071f2b;color:#f1ffff;border-color:#648a93;color-scheme:dark}
.panel input::placeholder,.panel textarea::placeholder{color:#a9c7ce}
.chrome button.secondary{background:#103642;color:#edfffb;border-color:#648a93}
.chrome button.secondary:hover{background:#16515a;color:#fff}
nav{background:color-mix(in srgb,var(--brand) 12%,#061721);border-color:color-mix(in srgb,var(--brand) 40%,#264553)}
details.menu .menu-body{background:var(--panel-bg,#0d2c38);color:var(--panel-fg,#fff);border:1px solid color-mix(in srgb,var(--brand) 55%,#4d7882);border-radius:12px;padding:10px;box-shadow:0 16px 40px #0009,0 0 20px color-mix(in srgb,var(--brand) 22%,transparent)}
details.menu .menu-body button.secondary,dialog button.secondary{background:#103642;color:#edfffb;border:1px solid #527783}
details.menu .menu-body button.secondary:hover,dialog button.secondary:hover{background:#16515a;color:#fff;border-color:var(--brand)}
dialog{background:var(--panel-bg,#0d2c38);color:var(--panel-fg,#fff);border:1px solid #527783;border-top:3px solid var(--brand);border-radius:14px;max-height:90vh;overflow:auto}
dialog h3,dialog label,dialog .help{color:var(--panel-fg,#fff)}
dialog input:not([type="checkbox"]):not([type="radio"]):not([type="color"]),dialog select,dialog textarea{background:#071f2b;color:#f1ffff;border-color:#648a93;color-scheme:dark}
#lang-sel{background:#0a2b37!important;color:#efffff!important;border-color:#648a93!important;color-scheme:dark}
.icon-picker button{background:#123743;color:#eafff9}.icon-picker button.selected{background:#d9fff1;color:#075842}
#workspace[data-context]:not([data-section="home"])::before{content:attr(data-context);display:block;margin:18px 32px 0;color:var(--brand);font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
#workspace[data-section]:not([data-section="home"]) .panel:first-child:after{content:"";position:absolute;right:22px;top:18px;width:38px;height:38px;border:1px solid var(--brand);border-right-color:transparent;border-radius:50%;box-shadow:0 0 16px color-mix(in srgb,var(--brand) 35%,transparent);opacity:.55;pointer-events:none;animation:hud-orbit 7s linear infinite}
@keyframes hud-orbit{to{transform:rotate(360deg)}}
#workspace[data-section="wizard"] .panel:first-child:after{border-style:dashed}
#workspace[data-section="orch"] .panel:first-child:after{border-radius:30%;transform:rotate(45deg)}
#workspace[data-section="sse"] .panel:first-child:after{border-style:dotted}
#workspace[data-section="svc"] .panel:first-child:after{border-width:3px}
#workspace[data-section="config"] .panel:first-child:after{border-radius:8px}
#workspace[data-section="tls"] .panel:first-child:after{border-radius:45% 45% 50% 50%}
#workspace[data-section="tools"] .panel:first-child:after{border-style:double;border-width:4px}
#workspace[data-section="debug"] .panel:first-child:after{border-left-color:transparent}
#workspace[data-section="update"] .panel:first-child:after{border-bottom-color:transparent}
#workspace[data-section="users"] .panel:first-child:after{border-radius:50% 50% 30% 30%}
.topology-hero{background:radial-gradient(ellipse at 82% 20%,color-mix(in srgb,var(--brand) 35%,transparent),transparent 43%),linear-gradient(122deg,#071d2a 4%,color-mix(in srgb,var(--brand) 24%,#08252f) 63%,color-mix(in srgb,var(--brand) 34%,#061d28))}
.sase-node,.topology-list .topology-card,.sase-inventory,.topology-group{border-color:color-mix(in srgb,var(--brand) 36%,#31515d)}
.sase-core{background:color-mix(in srgb,var(--brand) 32%,#082b35)}
html[data-effect="quiet"] #workspace .panel:first-child:after{animation:none}
@media(max-width:700px){#workspace[data-context]:not([data-section="home"])::before{margin:14px 12px 0}#workspace[data-section]:not([data-section="home"]) .panel:first-child:after{width:26px;height:26px;right:12px;top:12px;opacity:.35}}
@media(prefers-reduced-motion:reduce){#workspace .panel:first-child:after{animation:none}}

.sase-planet-orbit{position:absolute;inset:28%;border:1px solid #98ffe742;border-radius:50%;animation:sase-rotate 7s linear infinite}.sase-planet-orbit i{position:absolute;top:-5px;left:50%;width:10px;height:10px;border-radius:50%;background:#d0fff3;box-shadow:0 0 12px #63ffe0}.sase-planet-orbit.planet-two{inset:32%;animation-duration:11s;animation-direction:reverse}.sase-planet-orbit.planet-two i{width:7px;height:7px;background:#8dcaff;box-shadow:0 0 10px #81c8ff}.sase-ai-brands{color:#8df7de!important;font-weight:700;letter-spacing:.03em}html[data-effect="quiet"] .sase-planet-orbit{animation:none}@media(prefers-reduced-motion:reduce){.sase-planet-orbit{animation:none}}

/* Readable result notifications and atom motif. */
.panel button.secondary{background:#103642;color:#effffb;border-color:#557d85}.panel button.secondary:hover{background:#17515a;color:#fff;border-color:var(--brand)}
.notice-card{display:flex;align-items:flex-start;gap:12px;padding:14px 16px;border:1px solid #4b887a;border-left:4px solid #58eac0;border-radius:11px;color:#ecfff8;background:#0b3837;box-shadow:0 12px 28px #0004;margin-bottom:10px;white-space:pre-wrap}
.notice-card.err{background:#45232e;border-color:#b87889;border-left-color:#ff88a0;color:#fff1f3}.notice-card.info{background:#103446;border-color:#628a9b;border-left-color:#7bd6f4;color:#effcff}
.notice-icon{display:grid;place-items:center;flex:0 0 28px;height:28px;border:1px solid currentColor;border-radius:50%;font-weight:900}
.notice-body{min-width:0;flex:1;overflow-wrap:anywhere}.notice-body strong{display:block;margin-bottom:3px;font-size:13px}.notice-body span{display:block;line-height:1.5;font-size:13px}
.notice-close{min-height:28px;padding:2px 7px;background:transparent;color:inherit;border:0;font-size:18px}
#workspace[data-section]:not([data-section="home"]) .panel:first-child:after{border:0!important;border-radius:0!important;background:center/contain no-repeat url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'%3E%3Cg fill='none' stroke='%237cf9de' stroke-width='2.4'%3E%3Cellipse cx='40' cy='40' rx='35' ry='13'/%3E%3Cellipse cx='40' cy='40' rx='35' ry='13' transform='rotate(60 40 40)'/%3E%3Cellipse cx='40' cy='40' rx='35' ry='13' transform='rotate(120 40 40)'/%3E%3C/g%3E%3Ccircle cx='40' cy='40' r='5' fill='%23d8fff5'/%3E%3C/svg%3E");box-shadow:none;opacity:.75;animation:hud-orbit 14s linear infinite}
.tools-pager{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:16px}.tools-pager .help{margin:0}
@media(prefers-reduced-motion:reduce){#workspace .panel:first-child:after{animation:none}}

#bak-dlg .orch{background:var(--card-bg,#103542);color:var(--card-fg,#fff);border:1px solid #53727a;border-radius:10px;padding:14px;overflow-wrap:anywhere}
#bak-dlg .orch .help,#bak-dlg .orch strong{color:var(--card-fg,#fff)}#bak-dlg .orch .badge{background:#d9f5ec;color:#075842;border-color:#82bbad}
#bak-dlg .orch-actions{display:flex;flex-wrap:wrap;gap:6px;margin-inline-start:12px}
@media(max-width:700px){#bak-dlg .orch-actions{float:none;max-width:none;margin:0 0 12px}}
</style></head><body><main id="app">Cargando...</main>
<script>
var AUTHED=false, STATE={}, CONFIG=null, UPDATE=null, ME=null, WIZARD=null, WSTEP=-1, WDRAFT={}, WREVIEW=null, CURTAB='home', TOPOLOGY_STATUS=null, TOPOLOGY_BUSY=false;
var LANG=localStorage.getItem('ec-lang')||'es';
document.documentElement.lang=LANG;document.documentElement.dir=LANG==='he'?'rtl':'ltr';
var ACCENTS=[{n:'HPE Green',c:'#01a982'},{n:'Cyan',c:'#00c8ff'},{n:'Blue',c:'#00739d'},{n:'Gold',c:'#f2b900'},{n:'Rose',c:'#d94f70'},{n:'Header teal',c:'#073b4c'}];
var I18N={es:{nav_wizard:'Asistente',nav_orch:'Orquestadores',nav_sse:'Plataformas SSE',nav_svc:'Servicios',nav_config:'Variables',nav_update:'Actualizaciones',nav_users:'Usuarios',nav_out:'Salir',tagline:'MCP para SASE · EdgeConnect SD-WAN',login_title:'Control plane administrativo',login_user:'Usuario',login_pass:'Contraseña',login_enter:'Entrar',h2_orch:'Orquestadores',h2_sse:'Plataformas SSE (multi-tenant)',h2_svc:'Servicios',h2_config:'Variables del servicio',h2_update:'Actualizaciones desde GitHub',h2_users:'Usuarios del panel',h2_wizard:'Asistente de configuración',btn_save:'Guardar',btn_save_vars:'Guardar variables',btn_save_restart:'Guardar y reiniciar servicios',btn_save_restart_short:'Guardar y reiniciar',btn_recheck:'Volver a comprobar',btn_detect:'Detectar GitHub',btn_apply_update:'Aplicar actualización',btn_back:'Atrás',btn_next:'Siguiente',btn_review:'Revisar cambios',btn_probe:'Probar',btn_dup:'Duplicar',btn_ren:'Renombrar',btn_default:'Por defecto',btn_edit:'Editar',btn_delete:'Eliminar',btn_save_orch:'Guardar orquestador',btn_save_sse:'Guardar plataforma SSE',loading:'Cargando...',wiz_loading:'Cargando pasos...',secret_set:'Secreto configurado; no se muestra.',secret_unset:'Sin configurar.'},en:{nav_wizard:'Wizard',nav_orch:'Orchestrators',nav_sse:'SSE platforms',nav_svc:'Services',nav_config:'Settings',nav_update:'Updates',nav_users:'Users',nav_out:'Sign out',tagline:'MCP for SASE · EdgeConnect SD-WAN',login_title:'Administrative control plane',login_user:'User',login_pass:'Password',login_enter:'Sign in',h2_orch:'Orchestrators',h2_sse:'SSE platforms (multi-tenant)',h2_svc:'Services',h2_config:'Service settings',h2_update:'Updates from GitHub',h2_users:'Panel users',h2_wizard:'Setup wizard',btn_save:'Save',btn_save_vars:'Save settings',btn_save_restart:'Save and restart services',btn_save_restart_short:'Save and restart',btn_recheck:'Re-check',btn_detect:'Check GitHub',btn_apply_update:'Apply update',btn_back:'Back',btn_next:'Next',btn_review:'Review changes',btn_probe:'Test',btn_dup:'Duplicate',btn_ren:'Rename',btn_default:'Default',btn_edit:'Edit',btn_delete:'Delete',btn_save_orch:'Save orchestrator',btn_save_sse:'Save SSE platform',loading:'Loading...',wiz_loading:'Loading steps...',secret_set:'Secret configured; never displayed.',secret_unset:'Not configured.'}};
function t(k,v){var d=I18N[LANG]||I18N.es;var s=d[k]||I18N.en[k]||I18N.es[k]||k;if(v){for(var x in v){s=s.split('{'+x+'}').join(v[x])}}return s}
function setLang(l){var previousTab=CURTAB;LANG=l;document.documentElement.lang=l;document.documentElement.dir=l==='he'?'rtl':'ltr';localStorage.setItem('ec-lang',l);if(AUTHED){renderShell();showTab(previousTab)}else{renderLogin()}}
function setAccent(c){document.documentElement.style.setProperty('--brand',c);localStorage.setItem('ec-accent',c);if(AUTHED){renderShell();showTab(CURTAB)}else{renderLogin()}}

function siteName(){return localStorage.getItem('ec-site-name')||'EdgeConnect MCP'}
function siteTagline(){return localStorage.getItem('ec-site-tagline')||t('tagline')}
function siteLogo(){return localStorage.getItem('ec-logo')||''}
function siteIcon(){return localStorage.getItem('ec-icon')||''}
function brandHtml(){var ic=siteIcon();var logo=siteLogo();return '<div class="brand">'+(logo?'<img class="logo" src="'+logo+'" alt="logo">':(ic?'<span class="logo">'+esc(ic)+'</span>':''))+'<div><strong>'+esc(siteName())+'</strong><span>'+esc(siteTagline())+' · by Ryuz-crypto</span></div></div>'}
var ICONS=['⚡','🌐','🛰️','🔒','📡','🧭','🖧','⛓️'];
var SKINS={
 custom:null,
 aurora:{accent:'#01a982',header:'#073b4c',cyan:'#00c8ff',page:'#071d29',panel:'#0d2c38',card:'#103542'},
 arctic:{accent:'#28b4df',header:'#103454',cyan:'#8ceaff',page:'#071522',panel:'#102a40',card:'#163950'},
 ultraviolet:{accent:'#ae83ff',header:'#302350',cyan:'#e3a6ff',page:'#160f28',panel:'#261d3d',card:'#35294c'},
 solar:{accent:'#f3b84f',header:'#49300f',cyan:'#ffdd8a',page:'#201508',panel:'#352617',card:'#493521'},
 ember:{accent:'#ff737a',header:'#4a1f29',cyan:'#ffb7a8',page:'#200f18',panel:'#36202a',card:'#492b33'},
 ocean:{accent:'#5b96ff',header:'#172d59',cyan:'#91caff',page:'#0b142a',panel:'#192743',card:'#243757'},
 graphite:{accent:'#9cccbf',header:'#293d42',cyan:'#d0fff0',page:'#121b1e',panel:'#202d31',card:'#304147'}
};
function chooseSkin(id){
 var p=SKINS[id];if(!p)return;
 [['app-accent',p.accent],['app-header',p.header],['app-cyan',p.cyan],['app-page-bg',p.page],['app-panel-bg',p.panel],['app-card-bg',p.card],['app-panel-fg',contrastText(p.panel)],['app-card-fg',contrastText(p.card)]].forEach(function(v){var el=q('#'+v[0]);if(el)el.value=v[1]});
 previewBrand();
}
function markCustomSkin(){var el=q('#app-skin');if(el)el.value='custom';previewBrand()}
function openCustom(){
 var d=q('#custom-dlg');if(!d){q('#app').innerHTML+=customDialogHtml();d=q('#custom-dlg')}
 if(!d)return;
 q('#custom-name').value=siteName();
 q('#custom-tagline').value=localStorage.getItem('ec-site-tagline')||'';
 q('#app-skin').value=SKINS[localStorage.getItem('ec-skin')]?localStorage.getItem('ec-skin'):'custom';
 q('#app-effect').value=localStorage.getItem('ec-effect')||'sci-fi';
 q('#app-accent').value=localStorage.getItem('ec-accent')||'#01a982';
 q('#app-header').value=localStorage.getItem('ec-header')||'#073b4c';
 q('#app-cyan').value=localStorage.getItem('ec-cyan')||'#00c8ff';
 q('#app-page-bg').value=localStorage.getItem('ec-page-bg')||'#071d29';
 q('#app-panel-bg').value=localStorage.getItem('ec-panel-bg')||'#0d2c38';
 q('#app-card-bg').value=localStorage.getItem('ec-card-bg')||'#103542';
 q('#app-panel-fg').value=localStorage.getItem('ec-panel-fg')||contrastText(q('#app-panel-bg').value);
 q('#app-card-fg').value=localStorage.getItem('ec-card-fg')||contrastText(q('#app-card-bg').value);
 renderIconPicker();
 previewBrand();
 d.showModal?d.showModal():d.setAttribute('open','');
}
function renderIconPicker(){var cur=siteIcon();q('#icon-picker').innerHTML=ICONS.map(function(ic){return '<button type="button" class="'+(ic===cur?'selected':'')+'" onclick="pickIcon(\''+ic+'\')">'+ic+'</button>'}).join('')}
function pickIcon(ic){localStorage.setItem('ec-icon',ic);localStorage.removeItem('ec-logo');renderIconPicker();previewBrand();applySavedTheme();refreshBrand()}
function previewBrand(){var p=q('#brand-preview');if(!p||!p.style||!p.querySelector)return;p.style.setProperty('--preview-primary',(q('#app-accent')||{}).value||'#01a982');p.style.setProperty('--preview-header',(q('#app-header')||{}).value||'#073b4c');var ic=siteIcon();var logo=siteLogo();var pv=p.querySelector('.pv-brand');if(pv)pv.innerHTML=(logo?'<img class="logo" src="'+logo+'">':(ic?'<span class="logo">'+esc(ic)+'</span>':''))+'<div><strong>'+esc(q('#custom-name').value||siteName())+'</strong><span>'+esc((q('#custom-tagline')||{}).value||siteTagline())+' · by Ryuz-crypto</span></div>'}
function refreshBrand(){var previousTab=CURTAB;if(AUTHED){renderShell();showTab(previousTab)}else{renderLogin()}}
function closeCustom(){var d=q('#custom-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
function resetCustom(){['ec-accent','ec-header','ec-cyan','ec-icon','ec-logo','ec-site-name','ec-site-tagline','ec-effect','ec-page-bg','ec-panel-bg','ec-card-bg','ec-panel-fg','ec-card-fg','ec-skin'].forEach(function(k){localStorage.removeItem(k)});applySavedTheme();openCustom();refreshBrand();notice(t('app_reset_done'),'ok')}
function colorLuminance(hex){var c=[1,3,5].map(function(i){var v=parseInt(hex.slice(i,i+2),16)/255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*c[0]+.7152*c[1]+.0722*c[2]}
function saveCustom(){
 var pairs=[['panel-bg','panel-fg'],['card-bg','card-fg']];
 for(var pair of pairs){var bg=colorLuminance(q('#app-'+pair[0]).value),fg=colorLuminance(q('#app-'+pair[1]).value);if((Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)<4.5){alert((LANG==='es'||LANG==='mx')?'El contraste entre fondo y texto debe ser al menos 4.5:1.':'Background and text contrast must be at least 4.5:1.');return}}
 var tagline=q('#custom-tagline').value.trim().slice(0,140);if(tagline)localStorage.setItem('ec-site-tagline',tagline);else localStorage.removeItem('ec-site-tagline');
 var name=q('#custom-name')?q('#custom-name').value.trim():'';if(name)localStorage.setItem('ec-site-name',name);
 var a=q('#app-accent');if(a)localStorage.setItem('ec-accent',a.value);
 var h=q('#app-header');if(h)localStorage.setItem('ec-header',h.value);
 var c=q('#app-cyan');if(c)localStorage.setItem('ec-cyan',c.value);
 ['page-bg','panel-bg','card-bg','panel-fg','card-fg'].forEach(function(k){var el=q('#app-'+k);if(el)localStorage.setItem('ec-'+k,el.value)});
 var skin=q('#app-skin');if(skin)localStorage.setItem('ec-skin',skin.value);
 var effect=q('#app-effect');if(effect)localStorage.setItem('ec-effect',effect.value);
 var f=q('#custom-logo');
 if(f&&f.files&&f.files[0]){var r=new FileReader();r.onload=function(e){try{localStorage.setItem('ec-logo',String(e.target.result));localStorage.removeItem('ec-icon')}catch(err){notice(t('file_too_big'),'err')}applySavedTheme();closeCustom();refreshBrand()};r.readAsDataURL(f.files[0]);return}
 applySavedTheme();closeCustom();refreshBrand();
}
function customDialogHtml(){return '<dialog id="custom-dlg"><h3>'+t('custom_title')+'</h3><label>'+t('custom_name')+'<input id="custom-name" oninput="previewBrand()"></label><label>'+t('custom_tagline')+'<input id="custom-tagline" maxlength="140" oninput="previewBrand()" placeholder="'+esc(t('tagline'))+'"></label><p class="help">by Ryuz-crypto</p><label>'+((LANG==='es'||LANG==='mx')?'Skin visual':'Visual skin')+'<select id="app-skin" onchange="chooseSkin(this.value)"><option value="custom">'+((LANG==='es'||LANG==='mx')?'Personalizado / actual':'Custom / current')+'</option><option value="aurora">Aurora · HPE</option><option value="arctic">Arctic · Cyan</option><option value="ultraviolet">Ultraviolet</option><option value="solar">Solar · Amber</option><option value="ember">Ember · Crimson</option><option value="ocean">Ocean · Cobalt</option><option value="graphite">Graphite · Sage</option></select></label><p class="help">'+((LANG==='es'||LANG==='mx')?'Elige una skin y guarda; puedes ajustar sus colores.':'Choose a skin and save; you can adjust its colors.')+'</p><label>'+t('animation_style')+'<select id="app-effect"><option value="sci-fi">Sci-fi · Holográfico</option><option value="flow">'+t('effect_flow')+'</option><option value="pulse">'+t('effect_pulse')+'</option><option value="quiet">'+t('effect_none')+'</option></select></label><p class="help">'+t('effect_help')+'</p><div class="color-controls"><label>'+t('app_accent')+'<input type="color" id="app-accent" oninput="markCustomSkin()"></label><label>'+t('app_header')+'<input type="color" id="app-header" oninput="markCustomSkin()"></label><label>'+t('app_cyan')+'<input type="color" id="app-cyan" oninput="markCustomSkin()"></label><label>'+((LANG==='es'||LANG==='mx')?'Fondo de página':'Page background')+'<input type="color" id="app-page-bg" oninput="markCustomSkin()"></label><label>'+((LANG==='es'||LANG==='mx')?'Fondo de paneles':'Panel background')+'<input type="color" id="app-panel-bg" oninput="markCustomSkin()"></label><label>'+((LANG==='es'||LANG==='mx')?'Fondo de tarjetas':'Card background')+'<input type="color" id="app-card-bg" oninput="markCustomSkin()"></label><label>'+((LANG==='es'||LANG==='mx')?'Texto de paneles':'Panel text')+'<input type="color" id="app-panel-fg" oninput="markCustomSkin()"></label><label>'+((LANG==='es'||LANG==='mx')?'Texto de tarjetas':'Card text')+'<input type="color" id="app-card-fg" oninput="markCustomSkin()"></label></div><p class="help">'+((LANG==='es'||LANG==='mx')?'Elige colores con suficiente contraste. Guarda para aplicar los cambios.':'Choose colors with sufficient contrast. Save to apply changes.')+'</p><label style="margin-top:12px">'+t('app_icon')+'<span class="icon-picker" id="icon-picker"></span></label><label style="margin-top:10px">'+t('custom_logo')+'<input id="custom-logo" type="file" accept="image/png,image/*"></label><div class="panel brand-preview" id="brand-preview"><div class="pv-brand"></div></div><div class="actions"><button onclick="saveCustom()">'+t('custom_save')+'</button><button class="secondary" onclick="closeCustom()">'+t('custom_cancel')+'</button><button class="danger" onclick="resetCustom()">'+t('app_reset')+'</button></div></dialog>'}

var DONATE_URL='https://github.com/sponsors/Ryuz-crypto';
function footerHtml(){return '<footer class="powered-footer"><span>'+t('credits')+': ec-mcp · Ryuz-crypto</span><a class="donate" href="'+DONATE_URL+'" target="_blank" rel="noopener">☕ '+t('donate')+'</a></footer>'}
function userChip(){return '<details class="menu"><summary class="chip">'+esc(ME&&ME.user?ME.user:'')+(ME&&ME.role&&ME.role!=='admin'?' · '+esc(ME.role):'')+'</summary><div class="menu-body"><button class="secondary" onclick="showTab(\'users\')">'+t('menu_users')+'</button><button class="secondary" onclick="openBackups()">'+t('menu_backups')+'</button><button class="secondary" onclick="openCustom()">'+t('menu_custom')+'</button><button class="danger" onclick="logout()">'+t('nav_out')+'</button></div></details>'}

function chromeHtml(){return '<span class="chrome">'+langSelectHtml()+'<button class="secondary" style="padding:4px 9px;font-size:.75rem" title="'+t('menu_custom')+'" onclick="openCustom()">&#9881;</button></span>'}
function langSelectHtml(){return '<select id="lang-sel" title="Idioma / Language" style="min-height:30px;padding:3px 6px;border-radius:4px;border:1px solid #4f7080;background:#fff;color:#102a43" onchange="setLang(this.value)">'+LANGS.map(function(l){return '<option value="'+l[0]+'"'+(LANG===l[0]?' selected':'')+'>'+l[1]+'</option>'}).join('')+'</select>'}
function contrastText(hex){
 if(!/^#[0-9a-f]{6}$/i.test(hex))return '#ffffff';
 var rgb=[1,3,5].map(function(i){var c=parseInt(hex.slice(i,i+2),16)/255;return c<=.04045?c/12.92:Math.pow((c+.055)/1.055,2.4)});
 var luminance=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
 return luminance>.179?'#000000':'#ffffff';
}
function applySavedTheme(){
 var root=document.documentElement.style;
 if(document.documentElement.dataset)document.documentElement.dataset.effect=localStorage.getItem('ec-effect')||'flow';
 var accent=localStorage.getItem('ec-accent')||'#01a982';
 root.setProperty('--brand',accent);root.setProperty('--brand-fg',contrastText(accent));
 root.setProperty('--brand-header',localStorage.getItem('ec-header')||'#073b4c');
 root.setProperty('--cyan',localStorage.getItem('ec-cyan')||'#00c8ff');
 [['page-bg','#071d29'],['panel-bg','#0d2c38'],['card-bg','#103542']].forEach(function(pair){var c=localStorage.getItem('ec-'+pair[0])||pair[1];if(!/^#[0-9a-f]{6}$/i.test(c))c=pair[1];root.setProperty('--'+(pair[0]==='page-bg'?'console-bg':pair[0]),c);if(pair[0]!=='page-bg'){var fg=localStorage.getItem('ec-'+pair[0].replace('-bg','-fg'));root.setProperty('--'+pair[0].replace('-bg','-fg'),/^#[0-9a-f]{6}$/i.test(fg||'')?fg:contrastText(c))}});
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

var I18N6={es:{nav_debug:'Debug',dbg_title:'Depurador de solicitudes',dbg_desc:'Solicitudes en tiempo real del panel (API) y de las tools MCP (audit log). Se actualiza cada 2 s.',dbg_filter:'Filtrar (texto)…',dbg_pause:'Pausar',dbg_resume:'Reanudar',dbg_refresh:'Actualizar',dbg_export:'Exportar',dbg_clear:'Limpiar logs',dbg_time:'Hora',dbg_source:'Fuente',dbg_action:'Acción',dbg_target:'Target',dbg_result:'Resultado',dbg_lat:'Latencia',dbg_tool:'MCP tool',dbg_api:'API panel',dbg_empty:'Sin eventos todavía.',dbg_exported:'Exportado.',dbg_clear_confirm:'¿Borrar el audit log y vaciar el búfer de eventos? Esta acción libera almacenamiento y no se puede deshacer.'},en:{nav_debug:'Debug',dbg_title:'Request debugger',dbg_desc:'Real-time panel API requests and MCP tool calls (audit log). Refreshes every 2 s.',dbg_filter:'Filter (text)…',dbg_pause:'Pause',dbg_resume:'Resume',dbg_refresh:'Refresh',dbg_export:'Export',dbg_clear:'Clear logs',dbg_time:'Time',dbg_source:'Source',dbg_action:'Action',dbg_target:'Target',dbg_result:'Result',dbg_lat:'Latency',dbg_tool:'MCP tool',dbg_api:'Panel API',dbg_empty:'No events yet.',dbg_exported:'Exported.',dbg_clear_confirm:'Delete the audit log and empty the event buffer? This frees storage and cannot be undone.'}};
for(var k6 in I18N6.es){I18N.es[k6]=I18N6.es[k6]}
for(var k6 in I18N6.en){I18N.en[k6]=I18N6.en[k6]}

var I18N7={es:{app_reset:'Restablecer apariencia',app_reset_done:'Apariencia restablecida a los valores por defecto'},en:{app_reset:'Reset look & feel',app_reset_done:'Appearance reset to defaults'}};
for(var k7 in I18N7.es){I18N.es[k7]=I18N7.es[k7]}
for(var k7 in I18N7.en){I18N.en[k7]=I18N7.en[k7]}

var I18N8={es:{q_add_orch:'+ Agregar otro Orchestrator',q_add_sse:'+ Agregar plataforma SSE',q_main_orch:'Orchestrator principal (.env)',q_sse_env:'SSE en .env',q_panel:'Panel web',targets_add_more:'aquí se agregan #2, #3…'},en:{q_add_orch:'+ Add another Orchestrator',q_add_sse:'+ Add SSE platform',q_main_orch:'Main Orchestrator (.env)',q_sse_env:'SSE in .env',q_panel:'Web panel',targets_add_more:'add more here (#2, #3…)'}};
for(var k8 in I18N8.es){I18N.es[k8]=I18N8.es[k8]}
for(var k8 in I18N8.en){I18N.en[k8]=I18N8.en[k8]}

var I18N9={es:{credits:'Créditos',donate:'Donar al proyecto',wiz_home_title:'¿Qué quieres configurar?',wiz_home_desc:'Plataforma multi-servicio (MSP): SD-WAN, SSE, SSH y variables generales, cada una en el wizard o de forma independiente.',wiz_orchs_saved:'Orquestadores guardados',wiz_sse_saved:'Plataformas SSE guardadas',wiz_no_orch:'Aún no hay Orchestrator guardado.',wiz_no_sse:'Aún no hay plataforma SSE guardada.',wiz_setup_first:'Configurar mi primer Orchestrator',wiz_setup_sse:'Configurar Axis SSE',wiz_general:'Variables generales',wiz_general_desc:'Seguridad, transporte, panel, actualizaciones y dashboard. Si ya funcionan, puedes saltarlas.',wiz_edit_general:'Editar variables generales',wiz_skip_done:'Saltar (ya están configuradas)',wiz_start:'Ir al paso a paso',btn_skip:'Saltar este paso'},en:{credits:'Credits',donate:'Donate to the project',wiz_home_title:'What do you want to set up?',wiz_home_desc:'Multi-service (MSP) platform: SD-WAN, SSE, SSH and general variables, each in the wizard or independently.',wiz_orchs_saved:'saved Orchestrators',wiz_sse_saved:'saved SSE platforms',wiz_no_orch:'No Orchestrator saved yet.',wiz_no_sse:'No SSE platform saved yet.',wiz_setup_first:'Set up my first Orchestrator',wiz_setup_sse:'Set up Axis SSE',wiz_general:'General variables',wiz_general_desc:'Security, transport, panel, updates and dashboard. If they already work, you can skip them.',wiz_edit_general:'Edit general variables',wiz_skip_done:'Skip (already configured)',wiz_start:'Go step by step',btn_skip:'Skip this step'}};
for(var k9 in I18N9.es){I18N.es[k9]=I18N9.es[k9]}
for(var k9 in I18N9.en){I18N.en[k9]=I18N9.en[k9]}

var I18N10={es:{tools_filter:'Filtrar por tecnología:',dom_all:'Todas',dom_sdwan:'SD-WAN · EdgeConnect',dom_sse:'HPE SSE · Axis',dom_panel:'Panel / Admin'},en:{tools_filter:'Filter by technology:',dom_all:'All',dom_sdwan:'SD-WAN · EdgeConnect',dom_sse:'HPE SSE · Axis',dom_panel:'Panel / Admin'}};
for(var k10 in I18N10.es){I18N.es[k10]=I18N10.es[k10]}
for(var k10 in I18N10.en){I18N.en[k10]=I18N10.en[k10]}

var I18N11={es:{pick_existing:'Orquestador guardado:',new_entry:'nuevo',menu_backups:'Backups / Rollback',bak_title:'Backups y rollback',bak_desc:'Cada guardado crea un backup automático de .env y del registro (aquí se listan los cambios). Puedes crear backups manuales y restaurar (rollback) cualquiera; antes de restaurar, el estado actual se respalda solo.',bak_create:'Crear backup ahora',bak_restore:'Restaurar',bak_restore_confirm:'¿Restaurar el estado desde',bak_empty:'Sin backups todavía.'},en:{pick_existing:'Saved Orchestrator:',new_entry:'new',menu_backups:'Backups / Rollback',bak_title:'Backups and rollback',bak_desc:'Every save creates an automatic backup of .env and the registry (changes listed here). You can create manual backups and restore any of them; the current state is backed up automatically before restoring.',bak_create:'Create backup now',bak_restore:'Restore',bak_restore_confirm:'Restore state from',bak_empty:'No backups yet.'}};
for(var k11 in I18N11.es){I18N.es[k11]=I18N11.es[k11]}
for(var k11 in I18N11.en){I18N.en[k11]=I18N11.en[k11]}
var LANGS=[['es','Español'],['en','English'],['pt','Português'],['it','Italiano'],['de','Deutsch'],['mx','Español (MX)'],['fr','Français'],['ja','日本語'],['he','עברית']];
var I18N_L={"pt": {"nav_wizard": "Assistente", "nav_orch": "Orquestradores", "nav_sse": "Plataformas SSE", "nav_svc": "Serviços", "nav_config": "Variáveis", "nav_update": "Atualizações", "nav_users": "Usuários", "nav_out": "Sair", "tagline": "MCP para SASE · EdgeConnect SD-WAN", "login_title": "Plano de controle administrativo", "login_user": "Usuário", "login_pass": "Senha", "login_enter": "Entrar", "h2_orch": "Orquestradores", "h2_sse": "Plataformas SSE (multi-tenant)", "h2_svc": "Serviços", "h2_config": "Variáveis do serviço", "h2_update": "Atualizações do GitHub", "h2_users": "Usuários do painel", "h2_wizard": "Assistente de configuração", "btn_save": "Salvar", "btn_save_vars": "Salvar variáveis", "btn_save_restart": "Salvar e reiniciar serviços", "btn_save_restart_short": "Salvar e reiniciar", "btn_recheck": "Verificar novamente", "btn_detect": "Verificar GitHub", "btn_apply_update": "Aplicar atualização", "btn_back": "Voltar", "btn_next": "Próximo", "btn_review": "Revisar alterações", "btn_probe": "Testar", "btn_dup": "Duplicar", "btn_ren": "Renomear", "btn_default": "Padrão", "btn_edit": "Editar", "btn_delete": "Excluir", "btn_save_orch": "Salvar orquestrador", "btn_save_sse": "Salvar plataforma SSE", "loading": "Carregando...", "wiz_loading": "Carregando etapas...", "secret_set": "Segredo configurado; não exibido.", "secret_unset": "Não configurado.", "wiz_step": "Assistente · etapa {a} de {b}", "badge_active": "ativo", "badge_default": "padrão", "no_orch": "Nenhum orquestrador salvo.", "no_sse": "Nenhuma plataforma SSE salva.", "per_target": "Configuração por target", "view_target": "Mostrar configuração de", "all_targets": "(todas as variáveis globais)", "blob_set": "configurado", "blob_unset": "vazio", "nav_tls": "Certificados", "menu_users": "Usuários e senha", "menu_custom": "Personalizar painel", "f_name": "Nome", "f_url": "URL", "f_apikey": "Chave de API", "f_user": "Usuário", "f_pass": "Senha", "f_tls": "Verificar TLS", "f_ssh_user": "Usuário SSH", "f_ssh_pass": "Senha SSH", "f_enable": "Senha enable", "f_ssh_host": "Host SSH", "f_provider": "Provedor", "f_baseurl": "URL base", "f_token": "Token admin (Bearer JWT)", "f_timeout": "Tempo limite (s)", "add_update": "Adicionar ou atualizar", "apply_env": "Aplicar ao .env", "add_update_sse": "Adicionar ou atualizar plataforma SSE", "saved_in": "Salvas em", "secrets_note": "Segredos nunca retornam ao navegador.", "clear_secret": "Remover segredo salvo", "checking": "Verificando...", "svc_checked": "Status verificado com requisições reais em", "latency": "latência", "orch_label": "Orquestrador", "sse_label": "SSE", "upd_worker": "Worker de atualizações", "mcp_label": "Transporte MCP", "review_title": "Revisar alterações antes de salvar", "review_desc": "Pré-visualização em", "review_nowrite": "; nada é gravado ainda.", "no_changes": "Nenhuma alteração em variáveis.", "targets_h": "Targets (orquestradores / SSE)", "wiz_targets_help": "Salve vários orquestradores e várias plataformas SSE de uma vez; escolha qual fica padrão para tools sem target explícito.", "probing": "testando...", "probe_ok": "OK: ", "probe_fail": "Falha: ", "no_users": "Ainda sem usuários: usa-se a senha única (EC_ADMIN_PASSWORD).", "hashes_note": "Hashes nunca são exibidos nem retornados.", "add_user": "Adicionar ou atualizar usuário", "change_pass": "Alterar senha", "u_name": "Usuário", "u_pass": "Senha", "u_role": "Perfil", "u_old": "Senha atual", "u_new": "Nova senha", "u_empty": "Usuário (vazio = minha sessão)", "users_file": "Arquivo", "tls_title": "Certificados HTTPS", "tls_desc": "Envie o certificado e a chave privada (PEM) do painel. Os arquivos são salvos com 0600 e o painel pode servir HTTPS com EC_ADMIN_TLS_ENABLED=true.", "tls_cert": "Certificado PEM", "tls_key": "Chave privada PEM", "tls_upload": "Enviar certificado", "tls_delete": "Excluir certificado", "tls_enabled": "HTTPS ativo", "tls_disabled": "HTTPS desativado", "tls_fp": "Impressão SHA-256", "tls_present": "presente", "tls_missing": "ausente", "tls_none": "Nenhum certificado enviado.", "custom_title": "Personalizar painel", "custom_name": "Nome do site", "custom_logo": "Ícone PNG", "custom_save": "Salvar", "custom_cancel": "Cancelar", "target_info": "Configurações salvas no registro para", "tls_mode": "Formato", "tls_cert_file": "Certificado (arquivo)", "tls_key_file": "Chave privada (arquivo)", "tls_pfx_file": "Arquivo PFX / P12 / PKCS12", "tls_bundle_file": "Bundle PEM (certificado e chave juntos)", "tls_pw": "Senha da chave ou do contêiner, se houver", "tls_note": "Os arquivos são validados no servidor, normalizados para PEM e instalados apenas se a chave corresponder ao certificado. O certificado anterior é salvo (cert.pem.bak). Limite de 3 MB.", "tls_confirm": "Confirmação", "tls_confirm_code": "INSTALAR CERTIFICADO", "tls_install": "Instalar certificado", "tls_installed": "Certificado instalado", "tls_subject": "Titular", "tls_issuer": "Emissor", "tls_expires": "Vence", "fmt_pem": "PEM: certificado e chave separados", "fmt_bundle": "Bundle PEM: certificado e chave juntos", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER: certificado e chave separados", "file_too_big": "O arquivo excede o limite de 3 MB", "yes": "Sim", "no": "Não", "nav_tools": "Ferramentas", "global_vars": "Global (.env)", "tools_title": "Ferramentas MCP", "tools_desc": "Ative ou desative tools do servidor MCP (salvo em EC_MCP_DISABLED_TOOLS e aplicado ao reiniciar).", "tools_total": "tools no total", "tools_disabled": "desativadas", "tool_on": "Ativada:", "tool_off": "Desativada:", "agent_btn": "Sugestão para AI Agent", "agent_title": "Prompt sugerido para o AI Agent", "agent_desc": "Copie este texto para o contexto do seu agente (skill) para usar o ec-mcp da melhor forma. Inclui os skills de docs/.", "copy": "Copiar", "copied": "Copiado para a área de transferência", "app_accent": "Cor de destaque", "app_header": "Cor do cabeçalho", "app_cyan": "Cor de destaque secundária", "app_icon": "Ícone", "nav_debug": "Depuração", "dbg_title": "Depurador de requisições", "dbg_desc": "Requisições em tempo real do painel (API) e das tools MCP (audit log). Atualiza a cada 2 s.", "dbg_filter": "Filtrar (texto)…", "dbg_pause": "Pausar", "dbg_resume": "Retomar", "dbg_refresh": "Atualizar", "dbg_export": "Exportar", "dbg_clear": "Limpar logs", "dbg_time": "Hora", "dbg_source": "Fonte", "dbg_action": "Ação", "dbg_target": "Alvo", "dbg_result": "Resultado", "dbg_lat": "Latência", "dbg_tool": "Tool MCP", "dbg_api": "API do painel", "dbg_empty": "Ainda não há eventos.", "dbg_exported": "Exportado.", "dbg_clear_confirm": "Apagar o audit log e esvaziar o buffer de eventos? Libera espaço e não pode ser desfeito.", "app_reset": "Restaurar aparência", "app_reset_done": "Aparência restaurada aos padrões", "q_add_orch": "+ Adicionar outro Orquestrador", "q_add_sse": "+ Adicionar plataforma SSE", "q_main_orch": "Orquestrador principal (.env)", "q_sse_env": "SSE em .env", "q_panel": "Painel web", "targets_add_more": "aqui você adiciona #2, #3…", "credits": "Créditos", "donate": "Apoie o projeto", "wiz_home_title": "O que você quer configurar?", "wiz_home_desc": "Plataforma multisserviço (MSP): SD-WAN, SSE, SSH e variáveis gerais, cada um no assistente ou de forma independente.", "wiz_orchs_saved": "Orquestradores salvos", "wiz_sse_saved": "Plataformas SSE salvas", "wiz_no_orch": "Ainda não há Orquestrador salvo.", "wiz_no_sse": "Ainda não há plataforma SSE salva.", "wiz_setup_first": "Configurar meu primeiro Orquestrador", "wiz_setup_sse": "Configurar Axis SSE", "wiz_general": "Variáveis gerais", "wiz_general_desc": "Segurança, transporte, painel, atualizações e dashboard. Se já funcionam, você pode pular.", "wiz_edit_general": "Editar variáveis gerais", "wiz_skip_done": "Pular (já estão configuradas)", "wiz_start": "Ir passo a passo", "btn_skip": "Pular esta etapa", "tools_filter": "Filtrar por tecnologia:", "dom_all": "Todas", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "Painel / Admin", "pick_existing": "Orquestrador salvo:", "new_entry": "novo", "menu_backups": "Backups / Rollback", "bak_title": "Backups e rollback", "bak_desc": "Cada salvamento cria um backup automático de .env e do registro (mudanças listadas aqui). Crie backups manuais e restaure qualquer um; antes de restaurar, o estado atual é salvo sozinho.", "bak_create": "Criar backup agora", "bak_restore": "Restaurar", "bak_restore_confirm": "Restaurar o estado de", "bak_empty": "Ainda não há backups."}, "it": {"nav_wizard": "Assistente", "nav_orch": "Orchestrator", "nav_sse": "Piattaforme SSE", "nav_svc": "Servizi", "nav_config": "Variabili", "nav_update": "Aggiornamenti", "nav_users": "Utenti", "nav_out": "Esci", "tagline": "MCP per SASE · EdgeConnect SD-WAN", "login_title": "Pannello di controllo amministrativo", "login_user": "Utente", "login_pass": "Password", "login_enter": "Accedi", "h2_orch": "Orchestrator", "h2_sse": "Piattaforme SSE (multi-tenant)", "h2_svc": "Servizi", "h2_config": "Variabili del servizio", "h2_update": "Aggiornamenti da GitHub", "h2_users": "Utenti del pannello", "h2_wizard": "Assistente di configurazione", "btn_save": "Salva", "btn_save_vars": "Salva variabili", "btn_save_restart": "Salva e riavvia i servizi", "btn_save_restart_short": "Salva e riavvia", "btn_recheck": "Ricontrolla", "btn_detect": "Controlla GitHub", "btn_apply_update": "Applica aggiornamento", "btn_back": "Indietro", "btn_next": "Avanti", "btn_review": "Rivedi modifiche", "btn_probe": "Prova", "btn_dup": "Duplica", "btn_ren": "Rinomina", "btn_default": "Predefinito", "btn_edit": "Modifica", "btn_delete": "Elimina", "btn_save_orch": "Salva orchestrator", "btn_save_sse": "Salva piattaforma SSE", "loading": "Caricamento...", "wiz_loading": "Caricamento passaggi...", "secret_set": "Secret configurato; non mostrato.", "secret_unset": "Non configurato.", "wiz_step": "Assistente · passo {a} di {b}", "badge_active": "attivo", "badge_default": "predefinito", "no_orch": "Nessun orchestrator salvato.", "no_sse": "Nessuna piattaforma SSE salvata.", "per_target": "Configurazione per target", "view_target": "Mostra configurazione di", "all_targets": "(tutte le variabili globali)", "blob_set": "configurato", "blob_unset": "vuoto", "nav_tls": "Certificati", "menu_users": "Utenti e password", "menu_custom": "Personalizza pannello", "f_name": "Nome", "f_url": "URL", "f_apikey": "Chiave API", "f_user": "Utente", "f_pass": "Password", "f_tls": "Verifica TLS", "f_ssh_user": "Utente SSH", "f_ssh_pass": "Password SSH", "f_enable": "Password enable", "f_ssh_host": "Host SSH", "f_provider": "Provider", "f_baseurl": "URL base", "f_token": "Token admin (Bearer JWT)", "f_timeout": "Timeout (s)", "add_update": "Aggiungi o aggiorna", "apply_env": "Applica a .env", "add_update_sse": "Aggiungi o aggiorna piattaforma SSE", "saved_in": "Salvate in", "secrets_note": "I secret non tornano mai al browser.", "clear_secret": "Rimuovi secret salvato", "checking": "Controllo...", "svc_checked": "Stato verificato con richieste reali alle", "latency": "latenza", "orch_label": "Orchestrator", "sse_label": "SSE", "upd_worker": "Worker degli aggiornamenti", "mcp_label": "Trasporto MCP", "review_title": "Rivedi le modifiche prima di salvare", "review_desc": "Anteprima su", "review_nowrite": "; non viene scritto nulla.", "no_changes": "Nessuna modifica alle variabili.", "targets_h": "Target (orchestrator / SSE)", "wiz_targets_help": "Salva più orchestrator e piattaforme SSE insieme; scegli quale è predefinita per le tool senza target esplicito.", "probing": "prova in corso...", "probe_ok": "OK: ", "probe_fail": "Errore: ", "no_users": "Nessun utente: si usa la password singola (EC_ADMIN_PASSWORD).", "hashes_note": "Gli hash non vengono mai mostrati né restituiti.", "add_user": "Aggiungi o aggiorna utente", "change_pass": "Cambia password", "u_name": "Utente", "u_pass": "Password", "u_role": "Ruolo", "u_old": "Password attuale", "u_new": "Nuova password", "u_empty": "Utente (vuoto = la mia sessione)", "users_file": "File", "tls_title": "Certificati HTTPS", "tls_desc": "Carica certificato e chiave privata (PEM) del pannello. I file sono salvati con 0600 e il pannello può servire HTTPS con EC_ADMIN_TLS_ENABLED=true.", "tls_cert": "Certificato PEM", "tls_key": "Chiave privata PEM", "tls_upload": "Carica certificato", "tls_delete": "Elimina certificato", "tls_enabled": "HTTPS attivo", "tls_disabled": "HTTPS disattivato", "tls_fp": "Impronta SHA-256", "tls_present": "presente", "tls_missing": "assente", "tls_none": "Nessun certificato caricato.", "custom_title": "Personalizza pannello", "custom_name": "Nome del sito", "custom_logo": "Icona PNG", "custom_save": "Salva", "custom_cancel": "Annulla", "target_info": "Configurazioni salvate nel registro per", "tls_mode": "Formato", "tls_cert_file": "Certificato (file)", "tls_key_file": "Chiave privata (file)", "tls_pfx_file": "File PFX / P12 / PKCS12", "tls_bundle_file": "Bundle PEM (certificato e chiave insieme)", "tls_pw": "Password della chiave o del contenitore, se presente", "tls_note": "I file sono validati sul server, normalizzati in PEM e installati solo se la chiave corrisponde al certificato. Il certificato precedente è salvato (cert.pem.bak). Limite 3 MB.", "tls_confirm": "Conferma", "tls_confirm_code": "INSTALLA CERTIFICATO", "tls_install": "Installa certificato", "tls_installed": "Certificato installato", "tls_subject": "Soggetto", "tls_issuer": "Emittente", "tls_expires": "Scade", "fmt_pem": "PEM: certificato e chiave separati", "fmt_bundle": "Bundle PEM: certificato e chiave insieme", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER: certificato e chiave separati", "file_too_big": "Il file supera il limite di 3 MB", "yes": "Sì", "no": "No", "nav_tools": "Strumenti", "global_vars": "Globale (.env)", "tools_title": "Strumenti MCP", "tools_desc": "Attiva o disattiva le tool del server MCP (salvate in EC_MCP_DISABLED_TOOLS, applicate al riavvio).", "tools_total": "tool in totale", "tools_disabled": "disattivate", "tool_on": "Attivata:", "tool_off": "Disattivata:", "agent_btn": "Suggerimento per AI Agent", "agent_title": "Prompt suggerito per l'AI Agent", "agent_desc": "Copia questo testo nel contesto del tuo agente (skill) per usare ec-mcp al meglio. Include le skill di docs/.", "copy": "Copia", "copied": "Copiato negli appunti", "app_accent": "Colore principale", "app_header": "Colore intestazione", "app_cyan": "Colore secondario", "app_icon": "Icona", "nav_debug": "Debug", "dbg_title": "Debugger delle richieste", "dbg_desc": "Richieste in tempo reale del pannello (API) e delle tool MCP (audit log). Si aggiorna ogni 2 s.", "dbg_filter": "Filtra (testo)…", "dbg_pause": "Pausa", "dbg_resume": "Riprendi", "dbg_refresh": "Aggiorna", "dbg_export": "Esporta", "dbg_clear": "Pulisci log", "dbg_time": "Ora", "dbg_source": "Fonte", "dbg_action": "Azione", "dbg_target": "Target", "dbg_result": "Risultato", "dbg_lat": "Latenza", "dbg_tool": "Tool MCP", "dbg_api": "API del pannello", "dbg_empty": "Nessun evento.", "dbg_exported": "Esportato.", "dbg_clear_confirm": "Eliminare l'audit log e svuotare il buffer? Libera spazio e non è reversibile.", "app_reset": "Ripristina aspetto", "app_reset_done": "Aspetto ripristinato ai valori predefiniti", "q_add_orch": "+ Aggiungi altro Orchestrator", "q_add_sse": "+ Aggiungi piattaforma SSE", "q_main_orch": "Orchestrator principale (.env)", "q_sse_env": "SSE in .env", "q_panel": "Pannello web", "targets_add_more": "qui aggiungi #2, #3…", "credits": "Crediti", "donate": "Sostieni il progetto", "wiz_home_title": "Cosa vuoi configurare?", "wiz_home_desc": "Piattaforma multi-servizio (MSP): SD-WAN, SSE, SSH e variabili generali,ognuna nell'assistente o in modo indipendente.", "wiz_orchs_saved": "Orchestrator salvati", "wiz_sse_saved": "Piattaforme SSE salvate", "wiz_no_orch": "Nessun Orchestrator salvato.", "wiz_no_sse": "Nessuna piattaforma SSE salvata.", "wiz_setup_first": "Configura il mio primo Orchestrator", "wiz_setup_sse": "Configura Axis SSE", "wiz_general": "Variabili generali", "wiz_general_desc": "Sicurezza, trasporto, pannello, aggiornamenti e dashboard. Se funzionano già, puoi saltarli.", "wiz_edit_general": "Modifica variabili generali", "wiz_skip_done": "Salta (già configurate)", "wiz_start": "Vai passo dopo passo", "btn_skip": "Salta questo passaggio", "tools_filter": "Filtra per tecnologia:", "dom_all": "Tutte", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "Pannello / Admin", "pick_existing": "Orchestrator salvato:", "new_entry": "nuovo", "menu_backups": "Backup / Ripristino", "bak_title": "Backup e ripristino", "bak_desc": "Ogni salvataggio crea un backup automatico di .env e del registro (modifiche elencate qui). Crea backup manuali e ripristina cualquiera; prima del ripristino lo stato attuale è salvato da solo.", "bak_create": "Crea backup ora", "bak_restore": "Ripristina", "bak_restore_confirm": "Ripristinare lo stato da", "bak_empty": "Nessun backup."}, "de": {"nav_wizard": "Assistent", "nav_orch": "Orchestratoren", "nav_sse": "SSE-Plattformen", "nav_svc": "Dienste", "nav_config": "Einstellungen", "nav_update": "Updates", "nav_users": "Benutzer", "nav_out": "Abmelden", "tagline": "MCP für SASE · EdgeConnect SD-WAN", "login_title": "Administrative Kontrollebene", "login_user": "Benutzer", "login_pass": "Passwort", "login_enter": "Anmelden", "h2_orch": "Orchestratoren", "h2_sse": "SSE-Plattformen (Multi-Mandant)", "h2_svc": "Dienste", "h2_config": "Diensteinstellungen", "h2_update": "Updates von GitHub", "h2_users": "Panel-Benutzer", "h2_wizard": "Einrichtungsassistent", "btn_save": "Speichern", "btn_save_vars": "Einstellungen speichern", "btn_save_restart": "Speichern und Dienste neu starten", "btn_save_restart_short": "Speichern & neu starten", "btn_recheck": "Erneut prüfen", "btn_detect": "GitHub prüfen", "btn_apply_update": "Update anwenden", "btn_back": "Zurück", "btn_next": "Weiter", "btn_review": "Änderungen prüfen", "btn_probe": "Testen", "btn_dup": "Duplizieren", "btn_ren": "Umbenennen", "btn_default": "Standard", "btn_edit": "Bearbeiten", "btn_delete": "Löschen", "btn_save_orch": "Orchestrator speichern", "btn_save_sse": "SSE-Plattform speichern", "loading": "Laden...", "wiz_loading": "Schritte werden geladen...", "secret_set": "Geheimnis konfiguriert; wird nicht angezeigt.", "secret_unset": "Nicht konfiguriert.", "wiz_step": "Assistent · Schritt {a} von {b}", "badge_active": "aktiv", "badge_default": "Standard", "no_orch": "Keine Orchestratoren gespeichert.", "no_sse": "Keine SSE-Plattformen gespeichert.", "per_target": "Konfiguration pro Ziel", "view_target": "Konfiguration anzeigen für", "all_targets": "(alle globalen Variablen)", "blob_set": "konfiguriert", "blob_unset": "leer", "nav_tls": "Zertifikate", "menu_users": "Benutzer & Passwort", "menu_custom": "Panel anpassen", "f_name": "Name", "f_url": "URL", "f_apikey": "API-Schlüssel", "f_user": "Benutzer", "f_pass": "Passwort", "f_tls": "TLS prüfen", "f_ssh_user": "SSH-Benutzer", "f_ssh_pass": "SSH-Passwort", "f_enable": "Enable-Passwort", "f_ssh_host": "SSH-Host", "f_provider": "Anbieter", "f_baseurl": "Basis-URL", "f_token": "Admin-Token (Bearer JWT)", "f_timeout": "Timeout (s)", "add_update": "Hinzufügen oder aktualisieren", "apply_env": "Auf .env anwenden", "add_update_sse": "SSE-Plattform hinzufügen/aktualisieren", "saved_in": "Gespeichert in", "secrets_note": "Geheimnisse gelangen nie an den Browser.", "clear_secret": "Gespeichertes Geheimnis entfernen", "checking": "Prüfung läuft...", "svc_checked": "Status mit echten Anfragen geprüft am", "latency": "Latenz", "orch_label": "Orchestrator", "sse_label": "SSE", "upd_worker": "Update-Worker", "mcp_label": "MCP-Transport", "review_title": "Änderungen vor dem Speichern prüfen", "review_desc": "Vorschau für", "review_nowrite": "; es wird noch nichts geschrieben.", "no_changes": "Keine Variablenänderungen.", "targets_h": "Ziele (Orchestratoren / SSE)", "wiz_targets_help": "Speichert mehrere Orchestratoren und SSE-Plattformen auf einmal; wählen Sie die Standard-Plattform für Tools ohne explizites Ziel.", "probing": "teste...", "probe_ok": "OK: ", "probe_fail": "Fehler: ", "no_users": "Noch keine Benutzer: Einzel-Passwort (EC_ADMIN_PASSWORD) wird verwendet.", "hashes_note": "Hashes werden nie angezeigt oder zurückgegeben.", "add_user": "Benutzer hinzufügen oder aktualisieren", "change_pass": "Passwort ändern", "u_name": "Benutzer", "u_pass": "Passwort", "u_role": "Rolle", "u_old": "Aktuelles Passwort", "u_new": "Neues Passwort", "u_empty": "Benutzer (leer = meine Sitzung)", "users_file": "Datei", "tls_title": "HTTPS-Zertifikate", "tls_desc": "Zertifikat und privaten Schlüssel (PEM) des Panels hochladen. Dateien werden mit 0600 gespeichert; HTTPS mit EC_ADMIN_TLS_ENABLED=true.", "tls_cert": "Zertifikat PEM", "tls_key": "Privater Schlüssel PEM", "tls_upload": "Zertifikat hochladen", "tls_delete": "Zertifikat löschen", "tls_enabled": "HTTPS aktiv", "tls_disabled": "HTTPS deaktiviert", "tls_fp": "SHA-256-Fingerprint", "tls_present": "vorhanden", "tls_missing": "fehlt", "tls_none": "Kein Zertifikat hochgeladen.", "custom_title": "Panel anpassen", "custom_name": "Name der Seite", "custom_logo": "PNG-Symbol", "custom_save": "Speichern", "custom_cancel": "Abbrechen", "target_info": "Im Register gespeicherte Konfiguration für", "tls_mode": "Format", "tls_cert_file": "Zertifikat (Datei)", "tls_key_file": "Privater Schlüssel (Datei)", "tls_pfx_file": "PFX-/P12-/PKCS12-Datei", "tls_bundle_file": "PEM-Bundle (Zertifikat und Schlüssel zusammen)", "tls_pw": "Passwort des Schlüssels/Containers, falls vorhanden", "tls_note": "Dateien werden serverseitig validiert, zu PEM normalisiert und nur installiert, wenn der Schlüssel zum Zertifikat passt. Das alte Zertifikat wird gesichert (cert.pem.bak). Limit 3 MB.", "tls_confirm": "Bestätigung", "tls_confirm_code": "ZERTIFIKAT INSTALLIEREN", "tls_install": "Zertifikat installieren", "tls_installed": "Zertifikat installiert", "tls_subject": "Inhaber", "tls_issuer": "Aussteller", "tls_expires": "Läuft ab", "fmt_pem": "PEM: Zertifikat und Schlüssel getrennt", "fmt_bundle": "PEM-Bundle: Zertifikat und Schlüssel zusammen", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER: Zertifikat und Schlüssel getrennt", "file_too_big": "Datei überschreitet das Limit von 3 MB", "yes": "Ja", "no": "Nein", "nav_tools": "Tools", "global_vars": "Global (.env)", "tools_title": "MCP-Tools", "tools_desc": "MCP-Server-Tools aktivieren/deaktivieren (in EC_MCP_DISABLED_TOOLS gespeichert, nach Neustart aktiv).", "tools_total": "Tools insgesamt", "tools_disabled": "deaktiviert", "tool_on": "Aktiviert:", "tool_off": "Deaktiviert:", "agent_btn": "Vorschlag für KI-Agenten", "agent_title": "Empfohlener Prompt für den KI-Agenten", "agent_desc": "Kopieren Sie diesen Text in den Kontext Ihres Agenten (Skill), um ec-mcp optimal zu nutzen. Enthält die Skills aus docs/.", "copy": "Kopieren", "copied": "In die Zwischenablage kopiert", "app_accent": "Akzentfarbe", "app_header": "Header-Farbe", "app_cyan": "Sekundäre Akzentfarbe", "app_icon": "Symbol", "nav_debug": "Debugging", "dbg_title": "Request-Debugger", "dbg_desc": "Echtzeit-Anfragen des Panels (API) und der MCP-Tools (Audit-Log). Aktualisiert alle 2 s.", "dbg_filter": "Filtern (Text)…", "dbg_pause": "Pausieren", "dbg_resume": "Fortsetzen", "dbg_refresh": "Aktualisieren", "dbg_export": "Exportieren", "dbg_clear": "Logs löschen", "dbg_time": "Zeit", "dbg_source": "Quelle", "dbg_action": "Aktion", "dbg_target": "Ziel", "dbg_result": "Ergebnis", "dbg_lat": "Latenz", "dbg_tool": "MCP-Tool", "dbg_api": "Panel-API", "dbg_empty": "Noch keine Ereignisse.", "dbg_exported": "Exportiert.", "dbg_clear_confirm": "Audit-Log löschen und Puffer leeren? Gibt Speicher frei und ist nicht rückgängig.", "app_reset": "Darstellung zurücksetzen", "app_reset_done": "Darstellung auf Standard zurückgesetzt", "q_add_orch": "+ weiteren Orchestrator hinzufügen", "q_add_sse": "+ SSE-Plattform hinzufügen", "q_main_orch": "Haupt-Orchestrator (.env)", "q_sse_env": "SSE in .env", "q_panel": "Web-Panel", "targets_add_more": "hier #2, #3… hinzufügen", "credits": "Impressum", "donate": "Projekt unterstützen", "wiz_home_title": "Was möchten Sie einrichten?", "wiz_home_desc": "Multi-Service-Plattform (MSP): SD-WAN, SSE, SSH und allgemeine Variablen – jeweils im Assistenten oder unabhängig.", "wiz_orchs_saved": "Gespeicherte Orchestratoren", "wiz_sse_saved": "Gespeicherte SSE-Plattformen", "wiz_no_orch": "Noch kein Orchestrator gespeichert.", "wiz_no_sse": "Noch keine SSE-Plattform gespeichert.", "wiz_setup_first": "Ersten Orchestrator einrichten", "wiz_setup_sse": "Axis SSE einrichten", "wiz_general": "Allgemeine Variablen", "wiz_general_desc": "Sicherheit, Transport, Panel, Updates und Dashboard. Wenn sie bereits funktionieren, können Sie sie überspringen.", "wiz_edit_general": "Allgemeine Variablen bearbeiten", "wiz_skip_done": "Überspringen (bereits konfiguriert)", "wiz_start": "Schritt für Schritt", "btn_skip": "Schritt überspringen", "tools_filter": "Nach Technologie filtern:", "dom_all": "Alle", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "Panel / Admin", "pick_existing": "Gespeicherter Orchestrator:", "new_entry": "neu", "menu_backups": "Backups / Rollback", "bak_title": "Backups und Rollback", "bak_desc": "Jedes Speichern erstellt ein automatisches Backup von .env und Registry (Änderungen hier aufgeführt). Manuelle Backups erstellen und wiederherstellen; vor dem Rollback wird der aktuelle Stand automatisch gesichert.", "bak_create": "Backup jetzt erstellen", "bak_restore": "Wiederherstellen", "bak_restore_confirm": "Zustand wiederherstellen von", "bak_empty": "Noch keine Backups."}, "mx": {"nav_wizard": "Asistente", "nav_orch": "Orquestadores", "nav_sse": "Plataformas SSE", "nav_svc": "Servicios", "nav_config": "Variables", "nav_update": "Actualizaciones", "nav_users": "Usuarios", "nav_out": "Salir", "tagline": "MCP para SASE · EdgeConnect SD-WAN", "login_title": "Control plane administrativo", "login_user": "Usuario", "login_pass": "Contraseña", "login_enter": "Entrar", "h2_orch": "Orquestadores", "h2_sse": "Plataformas SSE (multi-tenant)", "h2_svc": "Servicios", "h2_config": "Variables del servicio", "h2_update": "Actualizaciones desde GitHub", "h2_users": "Usuarios del panel", "h2_wizard": "Asistente de configuración", "btn_save": "Guardar", "btn_save_vars": "Guardar variables", "btn_save_restart": "Guardar y reiniciar servicios", "btn_save_restart_short": "Guardar y reiniciar", "btn_recheck": "Volver a comprobar", "btn_detect": "Detectar GitHub", "btn_apply_update": "Aplicar actualización", "btn_back": "Atrás", "btn_next": "Siguiente", "btn_review": "Revisar cambios", "btn_probe": "Probar", "btn_dup": "Duplicar", "btn_ren": "Renombrar", "btn_default": "Por defecto", "btn_edit": "Editar", "btn_delete": "Eliminar", "btn_save_orch": "Guardar orquestador", "btn_save_sse": "Guardar plataforma SSE", "loading": "Cargando...", "wiz_loading": "Cargando pasos...", "secret_set": "Secreto configurado; no se muestra.", "secret_unset": "Sin configurar.", "wiz_step": "Asistente · paso {a} de {b}", "badge_active": "activo", "badge_default": "por defecto", "no_orch": "No hay orquestadores guardados.", "no_sse": "No hay plataformas SSE guardadas.", "per_target": "Configuración por target", "view_target": "Ver configuración de", "all_targets": "(todas las variables globales)", "blob_set": "configurado", "blob_unset": "vacío", "nav_tls": "Certificados", "menu_users": "Usuarios y contraseña", "menu_custom": "Personalizar panel", "f_name": "Nombre", "f_url": "URL", "f_apikey": "API key", "f_user": "Usuario", "f_pass": "Password", "f_tls": "Verificar TLS", "f_ssh_user": "Usuario SSH", "f_ssh_pass": "Password SSH", "f_enable": "Password enable", "f_ssh_host": "Host SSH", "f_provider": "Proveedor", "f_baseurl": "URL base", "f_token": "Token admin (Bearer JWT)", "f_timeout": "Timeout (s)", "add_update": "Agregar o actualizar", "apply_env": "Aplicar al .env", "add_update_sse": "Agregar o actualizar plataforma SSE", "saved_in": "Se guardan en", "secrets_note": "Los secretos nunca regresan al navegador.", "clear_secret": "Eliminar secreto guardado", "checking": "Verificando...", "svc_checked": "Estado verificado con peticiones reales el", "latency": "latencia", "orch_label": "Orchestrator", "sse_label": "SSE", "upd_worker": "Worker de actualizaciones", "mcp_label": "Transporte MCP", "review_title": "Revisar cambios antes de guardar", "review_desc": "Preview sobre", "review_nowrite": "; todavía no se escribe nada.", "no_changes": "Sin cambios en variables.", "targets_h": "Targets (orquestadores / SSE)", "wiz_targets_help": "Guarda varios orquestadores y varias plataformas SSE a la vez; elige cuál queda por defecto para los tools sin target explícito.", "probing": "probando...", "probe_ok": "OK: ", "probe_fail": "Fallo: ", "no_users": "Sin usuarios todavía: se usa la contraseña única (EC_ADMIN_PASSWORD).", "hashes_note": "Los hashes nunca se muestran ni se devuelven.", "add_user": "Agregar o actualizar usuario", "change_pass": "Cambiar contraseña", "u_name": "Usuario", "u_pass": "Contraseña", "u_role": "Rol", "u_old": "Contraseña actual", "u_new": "Nueva contraseña", "u_empty": "Usuario (vacío = mi sesión)", "users_file": "Archivo", "tls_title": "Certificados HTTPS", "tls_desc": "Sube el certificado y la llave privada (PEM) del panel. Los archivos se guardan con permisos 0600 y el panel puede servirse en HTTPS con EC_ADMIN_TLS_ENABLED=true.", "tls_cert": "Certificado PEM", "tls_key": "Llave privada PEM", "tls_upload": "Subir certificado", "tls_delete": "Eliminar certificado", "tls_enabled": "HTTPS activo", "tls_disabled": "HTTPS desactivado", "tls_fp": "Huella SHA-256", "tls_present": "presente", "tls_missing": "ausente", "tls_none": "Sin certificado subido.", "custom_title": "Personalizar panel", "custom_name": "Nombre del sitio", "custom_logo": "Icono PNG", "custom_save": "Guardar", "custom_cancel": "Cancelar", "target_info": "Configuración guardada en el registro para", "tls_mode": "Formato", "tls_cert_file": "Certificado (archivo)", "tls_key_file": "Llave privada (archivo)", "tls_pfx_file": "Archivo PFX / P12 / PKCS12", "tls_bundle_file": "Bundle PEM (certificado y llave juntos)", "tls_pw": "Contraseña de la llave o contenedor, si aplica", "tls_note": "Los archivos se validan en el servidor, se normalizan a PEM y solo se instala si la llave corresponde al certificado. El certificado anterior se respalda (cert.pem.bak). Límite 3 MB.", "tls_confirm": "Confirmación", "tls_confirm_code": "INSTALAR CERTIFICADO", "tls_install": "Instalar certificado", "tls_installed": "Certificado instalado", "tls_subject": "Sujeto", "tls_issuer": "Emisor", "tls_expires": "Vence", "fmt_pem": "PEM: certificado y llave separados", "fmt_bundle": "PEM bundle: certificado y llave juntos", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER: certificado y llave separados", "file_too_big": "El archivo excede el límite de 3 MB", "yes": "Sí", "no": "No", "nav_tools": "Tools", "global_vars": "Global (.env)", "tools_title": "Tools MCP", "tools_desc": "Activa o desactiva tools del servidor MCP (se guarda en EC_MCP_DISABLED_TOOLS y aplica al reiniciar).", "tools_total": "tools totales", "tools_disabled": "desactivadas", "tool_on": "Activada:", "tool_off": "Desactivada:", "agent_btn": "Sugerencia para AI Agent", "agent_title": "Prompt sugerido para el AI Agent", "agent_desc": "Copia este texto al contexto de tu agente (skill) para que use ec-mcp de la mejor manera. Incluye los skills de docs/.", "copy": "Copiar", "copied": "Copiado al portapapeles", "app_accent": "Color de acento", "app_header": "Color de cabecera", "app_cyan": "Color de acento secundario", "app_icon": "Icono", "nav_debug": "Debug", "dbg_title": "Depurador de solicitudes", "dbg_desc": "Solicitudes en tiempo real del panel (API) y de las tools MCP (audit log). Se actualiza cada 2 s.", "dbg_filter": "Filtrar (texto)…", "dbg_pause": "Pausar", "dbg_resume": "Reanudar", "dbg_refresh": "Actualizar", "dbg_export": "Exportar", "dbg_clear": "Borrar logs", "dbg_time": "Hora", "dbg_source": "Fuente", "dbg_action": "Acción", "dbg_target": "Target", "dbg_result": "Resultado", "dbg_lat": "Latencia", "dbg_tool": "MCP tool", "dbg_api": "API panel", "dbg_empty": "Sin eventos todavía.", "dbg_exported": "Exportado.", "dbg_clear_confirm": "¿Borrar el audit log y vaciar el búfer de eventos? Esta acción libera almacenamiento y no se puede deshacer.", "app_reset": "Restablecer apariencia", "app_reset_done": "Apariencia restablecida a los valores por defecto", "q_add_orch": "+ Agregar otro Orchestrator", "q_add_sse": "+ Agregar plataforma SSE", "q_main_orch": "Orchestrator principal (.env)", "q_sse_env": "SSE en .env", "q_panel": "Panel web", "targets_add_more": "aquí se agregan #2, #3…", "credits": "Créditos", "donate": "Apóyanos con una donación", "wiz_home_title": "¿Qué quieres configurar?", "wiz_home_desc": "Plataforma multi-servicio (MSP): SD-WAN, SSE, SSH y variables generales, cada una en el wizard o de forma independiente.", "wiz_orchs_saved": "Orquestadores guardados", "wiz_sse_saved": "Plataformas SSE guardadas", "wiz_no_orch": "Aún no hay Orchestrator guardado.", "wiz_no_sse": "Aún no hay plataforma SSE guardada.", "wiz_setup_first": "Configurar mi primer Orchestrator", "wiz_setup_sse": "Configurar Axis SSE", "wiz_general": "Variables generales", "wiz_general_desc": "Seguridad, transporte, panel, actualizaciones y dashboard. Si ya funcionan, puedes saltarlas.", "wiz_edit_general": "Editar variables generales", "wiz_skip_done": "Saltar (ya están configuradas)", "wiz_start": "Ir al paso a paso", "btn_skip": "Saltar este paso", "tools_filter": "Filtrar por tecnología:", "dom_all": "Todas", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "Panel / Admin", "pick_existing": "Orquestador guardado:", "new_entry": "nuevo", "menu_backups": "Backups / Rollback", "bak_title": "Backups y rollback", "bak_desc": "Cada guardado crea un backup automático de .env y del registro (aquí se listan los cambios). Puedes crear backups manuales y restaurar (rollback) cualquiera; antes de restaurar, el estado actual se respalda solo.", "bak_create": "Crear backup ahora", "bak_restore": "Regresar a esta versión", "bak_restore_confirm": "¿Restaurar el estado desde", "bak_empty": "Sin backups todavía."}, "fr": {"nav_wizard": "Assistant", "nav_orch": "Orchestrateurs", "nav_sse": "Plateformes SSE", "nav_svc": "Services", "nav_config": "Variables", "nav_update": "Mises à jour", "nav_users": "Utilisateurs", "nav_out": "Déconnexion", "tagline": "MCP pour SASE · EdgeConnect SD-WAN", "login_title": "Plan de contrôle administratif", "login_user": "Utilisateur", "login_pass": "Mot de passe", "login_enter": "Connexion", "h2_orch": "Orchestrateurs", "h2_sse": "Plateformes SSE (multi-tenant)", "h2_svc": "Services", "h2_config": "Variables du service", "h2_update": "Mises à jour depuis GitHub", "h2_users": "Utilisateurs du panneau", "h2_wizard": "Assistant de configuration", "btn_save": "Enregistrer", "btn_save_vars": "Enregistrer les variables", "btn_save_restart": "Enregistrer et redémarrer", "btn_save_restart_short": "Enregistrer et redémarrer", "btn_recheck": "Revérifier", "btn_detect": "Vérifier GitHub", "btn_apply_update": "Appliquer la mise à jour", "btn_back": "Retour", "btn_next": "Suivant", "btn_review": "Vérifier les modifications", "btn_probe": "Tester", "btn_dup": "Dupliquer", "btn_ren": "Renommer", "btn_default": "Par défaut", "btn_edit": "Modifier", "btn_delete": "Supprimer", "btn_save_orch": "Enregistrer l'orchestrateur", "btn_save_sse": "Enregistrer la plateforme SSE", "loading": "Chargement...", "wiz_loading": "Chargement des étapes...", "secret_set": "Secret configuré ; non affiché.", "secret_unset": "Non configuré.", "wiz_step": "Assistant · étape {a} sur {b}", "badge_active": "actif", "badge_default": "par défaut", "no_orch": "Aucun orchestreur enregistré.", "no_sse": "Aucune plateforme SSE enregistrée.", "per_target": "Configuration par cible", "view_target": "Afficher la configuration de", "all_targets": "(toutes les variables globales)", "blob_set": "configuré", "blob_unset": "vide", "nav_tls": "Certificats", "menu_users": "Utilisateurs et mot de passe", "menu_custom": "Personnaliser le panneau", "f_name": "Nom", "f_url": "URL", "f_apikey": "Clé API", "f_user": "Utilisateur", "f_pass": "Mot de passe", "f_tls": "Vérifier TLS", "f_ssh_user": "Utilisateur SSH", "f_ssh_pass": "Mot de passe SSH", "f_enable": "Mot de passe enable", "f_ssh_host": "Hôte SSH", "f_provider": "Fournisseur", "f_baseurl": "URL de base", "f_token": "Jeton admin (Bearer JWT)", "f_timeout": "Délai (s)", "add_update": "Ajouter ou modifier", "apply_env": "Appliquer au .env", "add_update_sse": "Ajouter ou modifier une plateforme SSE", "saved_in": "Enregistrées dans", "secrets_note": "Les secrets ne sont jamais renvoyés au navigateur.", "clear_secret": "Supprimer le secret enregistré", "checking": "Vérification...", "svc_checked": "État vérifié avec de vraies requêtes à", "latency": "latence", "orch_label": "Orchestrateur", "sse_label": "SSE", "upd_worker": "Worker de mises à jour", "mcp_label": "Transport MCP", "review_title": "Vérifier les modifications avant d'enregistrer", "review_desc": "Aperçu sur", "review_nowrite": "; rien n'est encore écrit.", "no_changes": "Aucune modification de variable.", "targets_h": "Cibles (orchestrateurs / SSE)", "wiz_targets_help": "Enregistrez plusieurs orchestrateurs et plateformes SSE ; choisissez celle par défaut pour les outils sans cible explicite.", "probing": "test en cours...", "probe_ok": "OK : ", "probe_fail": "Échec : ", "no_users": "Pas encore d'utilisateurs : mot de passe unique (EC_ADMIN_PASSWORD).", "hashes_note": "Les hachages ne sont jamais affichés ni renvoyés.", "add_user": "Ajouter ou modifier un utilisateur", "change_pass": "Changer le mot de passe", "u_name": "Utilisateur", "u_pass": "Mot de passe", "u_role": "Rôle", "u_old": "Mot de passe actuel", "u_new": "Nouveau mot de passe", "u_empty": "Utilisateur (vide = ma session)", "users_file": "Fichier", "tls_title": "Certificats HTTPS", "tls_desc": "Téléversez le certificat et la clé privée (PEM) du panneau. Fichiers en 0600 ; HTTPS avec EC_ADMIN_TLS_ENABLED=true.", "tls_cert": "Certificat PEM", "tls_key": "Clé privée PEM", "tls_upload": "Téléverser le certificat", "tls_delete": "Supprimer le certificat", "tls_enabled": "HTTPS activé", "tls_disabled": "HTTPS désactivé", "tls_fp": "Empreinte SHA-256", "tls_present": "présent", "tls_missing": "absent", "tls_none": "Aucun certificat téléversé.", "custom_title": "Personnaliser le panneau", "custom_name": "Nom du site", "custom_logo": "Icône PNG", "custom_save": "Enregistrer", "custom_cancel": "Annuler", "target_info": "Configuration enregistrée dans le registre pour", "tls_mode": "Format", "tls_cert_file": "Certificat (fichier)", "tls_key_file": "Clé privée (fichier)", "tls_pfx_file": "Fichier PFX / P12 / PKCS12", "tls_bundle_file": "Bundle PEM (certificat et clé ensemble)", "tls_pw": "Mot de passe de la clé ou du conteneur, le cas échéant", "tls_note": "Fichiers validés côté serveur, normalisés en PEM et installés seulement si la clé correspond au certificat. Certificat précédent sauvegardé (cert.pem.bak). Limite 3 Mo.", "tls_confirm": "Confirmation", "tls_confirm_code": "INSTALLER LE CERTIFICAT", "tls_install": "Installer le certificat", "tls_installed": "Certificat installé", "tls_subject": "Sujet", "tls_issuer": "Émetteur", "tls_expires": "Expire", "fmt_pem": "PEM : certificat et clé séparés", "fmt_bundle": "Bundle PEM : certificat et clé ensemble", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER : certificat et clé séparés", "file_too_big": "Le fichier dépasse la limite de 3 Mo", "yes": "Oui", "no": "Non", "nav_tools": "Outils", "global_vars": "Global (.env)", "tools_title": "Outils MCP", "tools_desc": "Activez ou désactivez les outils du serveur MCP (enregistrés dans EC_MCP_DISABLED_TOOLS, appliqués au redémarrage).", "tools_total": "outils au total", "tools_disabled": "désactivées", "tool_on": "Activée :", "tool_off": "Désactivée :", "agent_btn": "Suggestion pour l'agent IA", "agent_title": "Prompt suggéré pour l'agent IA", "agent_desc": "Copiez ce texte dans le contexte de votre agent (skill) pour utiliser ec-mcp au mieux. Inclut les skills de docs/.", "copy": "Copier", "copied": "Copié dans le presse-papiers", "app_accent": "Couleur d'accent", "app_header": "Couleur d'en-tête", "app_cyan": "Couleur d'accent secondaire", "app_icon": "Icône", "nav_debug": "Débogage", "dbg_title": "Débogueur de requêtes", "dbg_desc": "Requêtes en temps réel du panneau (API) et des outils MCP (journal d'audit). Rafraîchi toutes les 2 s.", "dbg_filter": "Filtrer (texte)…", "dbg_pause": "Pause", "dbg_resume": "Reprendre", "dbg_refresh": "Rafraîchir", "dbg_export": "Exporter", "dbg_clear": "Effacer les logs", "dbg_time": "Heure", "dbg_source": "Source", "dbg_action": "Action", "dbg_target": "Cible", "dbg_result": "Résultat", "dbg_lat": "Latence", "dbg_tool": "Outil MCP", "dbg_api": "API du panneau", "dbg_empty": "Aucun événement.", "dbg_exported": "Exporté.", "dbg_clear_confirm": "Supprimer le journal d'audit et vider le tampon ? Libère de l'espace, irréversible.", "app_reset": "Réinitialiser l'apparence", "app_reset_done": "Apparence réinitialisée", "q_add_orch": "+ Ajouter un autre orchestreur", "q_add_sse": "+ Ajouter une plateforme SSE", "q_main_orch": "Orchestrateur principal (.env)", "q_sse_env": "SSE dans .env", "q_panel": "Panneau web", "targets_add_more": "ajoutez #2, #3… ici", "credits": "Crédits", "donate": "Soutenir le projet", "wiz_home_title": "Que souhaitez-vous configurer ?", "wiz_home_desc": "Plateforme multi-services (MSP) : SD-WAN, SSE, SSH et variables générales, chacun dans l'assistant ou indépendamment.", "wiz_orchs_saved": "Orchestrateurs enregistrés", "wiz_sse_saved": "Plateformes SSE enregistrées", "wiz_no_orch": "Aucun orchestreur enregistré.", "wiz_no_sse": "Aucune plateforme SSE enregistrée.", "wiz_setup_first": "Configurer mon premier orchestreur", "wiz_setup_sse": "Configurer Axis SSE", "wiz_general": "Variables générales", "wiz_general_desc": "Sécurité, transport, panneau, mises à jour et tableau de bord. S'ils fonctionnent déjà, vous pouvez les ignorer.", "wiz_edit_general": "Modifier les variables générales", "wiz_skip_done": "Ignorer (déjà configurées)", "wiz_start": "Étape par étape", "btn_skip": "Ignorer cette étape", "tools_filter": "Filtrer par technologie :", "dom_all": "Toutes", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "Panneau / Admin", "pick_existing": "Orchestrateur enregistré :", "new_entry": "nouveau", "menu_backups": "Sauvegardes / Restauration", "bak_title": "Sauvegardes et restauration", "bak_desc": "Chaque sauvegarde crée une sauvegarde auto de .env et du registre (modifs listées ici). Créez des sauvegardes manuelles et restaurez ; l'état courant est d'abord sauvegardé.", "bak_create": "Créer une sauvegarde maintenant", "bak_restore": "Restaurer", "bak_restore_confirm": "Restaurer l'état depuis", "bak_empty": "Aucune sauvegarde."}, "ja": {"nav_wizard": "ウィザード", "nav_orch": "オーケストレーター", "nav_sse": "SSEプラットフォーム", "nav_svc": "サービス", "nav_config": "設定", "nav_update": "アップデート", "nav_users": "ユーザー", "nav_out": "サインアウト", "tagline": "SASE向けMCP · EdgeConnect SD-WAN", "login_title": "管理コントロールプレーン", "login_user": "ユーザー", "login_pass": "パスワード", "login_enter": "サインイン", "h2_orch": "オーケストレーター", "h2_sse": "SSEプラットフォーム（マルチテナント）", "h2_svc": "サービス", "h2_config": "サービス設定", "h2_update": "GitHubからの更新", "h2_users": "パネルユーザー", "h2_wizard": "セットアップウィザード", "btn_save": "保存", "btn_save_vars": "設定を保存", "btn_save_restart": "保存してサービスを再起動", "btn_save_restart_short": "保存して再起動", "btn_recheck": "再確認", "btn_detect": "GitHubを確認", "btn_apply_update": "更新を適用", "btn_back": "戻る", "btn_next": "次へ", "btn_review": "変更を確認", "btn_probe": "テスト", "btn_dup": "複製", "btn_ren": "名前変更", "btn_default": "デフォルト", "btn_edit": "編集", "btn_delete": "削除", "btn_save_orch": "オーケストレーターを保存", "btn_save_sse": "SSEプラットフォームを保存", "loading": "読み込み中...", "wiz_loading": "ステップを読み込み中...", "secret_set": "シークレット設定済み（表示されません）。", "secret_unset": "未設定。", "wiz_step": "ウィザード · ステップ {a}/{b}", "badge_active": "アクティブ", "badge_default": "デフォルト", "no_orch": "オーケストレーターは保存されていません。", "no_sse": "SSEプラットフォームは保存されていません。", "per_target": "ターゲット別設定", "view_target": "設定を表示:", "all_targets": "（すべてのグローバル変数）", "blob_set": "設定済み", "blob_unset": "空", "nav_tls": "証明書", "menu_users": "ユーザーとパスワード", "menu_custom": "パネルをカスタマイズ", "f_name": "名前", "f_url": "URL", "f_apikey": "APIキー", "f_user": "ユーザー", "f_pass": "パスワード", "f_tls": "TLSを検証", "f_ssh_user": "SSHユーザー", "f_ssh_pass": "SSHパスワード", "f_enable": "イネーブルパスワード", "f_ssh_host": "SSHホスト", "f_provider": "プロバイダー", "f_baseurl": "ベースURL", "f_token": "管理トークン（Bearer JWT）", "f_timeout": "タイムアウト（秒）", "add_update": "追加または更新", "apply_env": ".envに適用", "add_update_sse": "SSEプラットフォームを追加または更新", "saved_in": "保存先:", "secrets_note": "シークレットがブラウザに返されることはありません。", "clear_secret": "保存されたシークレットを削除", "checking": "確認中...", "svc_checked": "実リクエストで確認した時刻:", "latency": "レイテンシ", "orch_label": "オーケストレーター", "sse_label": "SSE", "upd_worker": "更新ワーカー", "mcp_label": "MCPトランスポート", "review_title": "保存前に変更を確認", "review_desc": "プレビュー:", "review_nowrite": "; まだ何も書き込まれません。", "no_changes": "設定の変更はありません。", "targets_h": "ターゲット（オーケストレーター / SSE）", "wiz_targets_help": "複数のオーケストレーターとSSEプラットフォームを一度に保存します。target指定のないツールのデフォルトを選んでください。", "probing": "確認中...", "probe_ok": "OK: ", "probe_fail": "失敗: ", "no_users": "ユーザーなし: 単一パスワード（EC_ADMIN_PASSWORD）を使用。", "hashes_note": "ハッシュは表示・返却されません。", "add_user": "ユーザーを追加または更新", "change_pass": "パスワードを変更", "u_name": "ユーザー", "u_pass": "パスワード", "u_role": "ロール", "u_old": "現在のパスワード", "u_new": "新しいパスワード", "u_empty": "ユーザー（空欄 = 自分のセッション）", "users_file": "ファイル", "tls_title": "HTTPS証明書", "tls_desc": "パネルの証明書と秘密鍵（PEM）をアップロードします。ファイルは0600で保存され、EC_ADMIN_TLS_ENABLED=trueでHTTPSを提供できます。", "tls_cert": "PEM証明書", "tls_key": "PEM秘密鍵", "tls_upload": "証明書をアップロード", "tls_delete": "証明書を削除", "tls_enabled": "HTTPS有効", "tls_disabled": "HTTPS無効", "tls_fp": "SHA-256フィンガープリント", "tls_present": "あり", "tls_missing": "なし", "tls_none": "証明書は未アップロードです。", "custom_title": "パネルをカスタマイズ", "custom_name": "サイト名", "custom_logo": "PNGアイコン", "custom_save": "保存", "custom_cancel": "キャンセル", "target_info": "レジストリに保存された設定:", "tls_mode": "形式", "tls_cert_file": "証明書（ファイル）", "tls_key_file": "秘密鍵（ファイル）", "tls_pfx_file": "PFX / P12 / PKCS12ファイル", "tls_bundle_file": "PEMバンドル（証明書と鍵を一緒に）", "tls_pw": "鍵またはコンテナのパスワード（ある場合）", "tls_note": "ファイルはサーバーで検証・PEMに正規化され、鍵が証明書と一致する場合のみインストールされます。旧証明書は cert.pem.bak に保存。上限3MB。", "tls_confirm": "確認", "tls_confirm_code": "証明書をインストール", "tls_install": "証明書をインストール", "tls_installed": "証明書をインストール済み", "tls_subject": "サブジェクト", "tls_issuer": "発行者", "tls_expires": "有効期限", "fmt_pem": "PEM: 証明書と鍵を別々に", "fmt_bundle": "PEMバンドル: 証明書と鍵を一緒に", "fmt_pfx": "PFX / PKCS12", "fmt_der": "DER: 証明書と鍵を別々に", "file_too_big": "ファイルが3MBの上限を超えています", "yes": "はい", "no": "いいえ", "nav_tools": "ツール", "global_vars": "グローバル（.env）", "tools_title": "MCPツール", "tools_desc": "MCPサーバーのツールを有効/無効化します（EC_MCP_DISABLED_TOOLSに保存、再起動で適用）。", "tools_total": "ツール合計", "tools_disabled": "無効", "tool_on": "有効化:", "tool_off": "無効化:", "agent_btn": "AIエージェント向け提案", "agent_title": "AIエージェント向け推奨プロンプト", "agent_desc": "このテキストをエージェントのコンテキスト（スキル）にコピーしてec-mcpを最適に使えます。docs/のスキルを含みます。", "copy": "コピー", "copied": "クリップボードにコピーしました", "app_accent": "アクセントカラー", "app_header": "ヘッダーの色", "app_cyan": "セカンダリアクセントカラー", "app_icon": "アイコン", "nav_debug": "デバッグ", "dbg_title": "リクエストデバッガー", "dbg_desc": "パネル（API）とMCPツール（監査ログ）のリクエストをリアルタイム表示。2秒ごとに更新。", "dbg_filter": "絞り込み（テキスト）…", "dbg_pause": "一時停止", "dbg_resume": "再開", "dbg_refresh": "更新", "dbg_export": "エクスポート", "dbg_clear": "ログを消去", "dbg_time": "時刻", "dbg_source": "ソース", "dbg_action": "アクション", "dbg_target": "ターゲット", "dbg_result": "結果", "dbg_lat": "レイテンシ", "dbg_tool": "MCPツール", "dbg_api": "パネルAPI", "dbg_empty": "イベントはまだありません。", "dbg_exported": "エクスポートしました。", "dbg_clear_confirm": "監査ログを削除してイベントバッファを空にしますか？容量を解放します（元に戻せません）。", "app_reset": "外観をリセット", "app_reset_done": "外観をデフォルトに戻しました", "q_add_orch": "+ オーケストレーターを追加", "q_add_sse": "+ SSEプラットフォームを追加", "q_main_orch": "メインオーケストレーター（.env）", "q_sse_env": "SSE（.env）", "q_panel": "Webパネル", "targets_add_more": "ここに #2、#3… を追加", "credits": "クレジット", "donate": "プロジェクトを支援", "wiz_home_title": "何を設定しますか？", "wiz_home_desc": "マルチサービスプラットフォーム（MSP）：SD-WAN・SSE・SSH・一般設定を、ウィザードまたは個別に設定できます。", "wiz_orchs_saved": "保存済みオーケストレーター", "wiz_sse_saved": "保存済みSSEプラットフォーム", "wiz_no_orch": "オーケストレーターはまだ保存されていません。", "wiz_no_sse": "SSEプラットフォームはまだ保存されていません。", "wiz_setup_first": "最初のオーケストレーターを設定", "wiz_setup_sse": "Axis SSEを設定", "wiz_general": "一般設定", "wiz_general_desc": "セキュリティ・トランスポート・パネル・更新・ダッシュボード。すでに動作していればスキップできます。", "wiz_edit_general": "一般設定を編集", "wiz_skip_done": "スキップ（設定済み）", "wiz_start": "ステップごとに進む", "btn_skip": "このステップをスキップ", "tools_filter": "技術で絞り込み:", "dom_all": "すべて", "dom_sdwan": "SD-WAN · EdgeConnect", "dom_sse": "HPE SSE · Axis", "dom_panel": "パネル / 管理", "pick_existing": "保存済みオーケストレーター:", "new_entry": "新規", "menu_backups": "バックアップ / ロールバック", "bak_title": "バックアップとロールバック", "bak_desc": "保存ごとに .env とレジストリの自動バックアップが作られます（変更点を表示）。手動バックアップの作成と復元も可能。復元前に現在の状態が自動保存されます。", "bak_create": "今すぐバックアップ", "bak_restore": "復元", "bak_restore_confirm": "この状態から復元しますか:", "bak_empty": "バックアップはまだありません。"}};
for(var kl in I18N_L.pt){I18N.pt=I18N.pt||{};I18N.pt[kl]=I18N_L.pt[kl]}
for(var kl in I18N_L.it){I18N.it=I18N.it||{};I18N.it[kl]=I18N_L.it[kl]}
for(var kl in I18N_L.de){I18N.de=I18N.de||{};I18N.de[kl]=I18N_L.de[kl]}
for(var kl in I18N_L.mx){I18N.mx=I18N.mx||{};I18N.mx[kl]=I18N_L.mx[kl]}
for(var kl in I18N_L.fr){I18N.fr=I18N.fr||{};I18N.fr[kl]=I18N_L.fr[kl]}
for(var kl in I18N_L.ja){I18N.ja=I18N.ja||{};I18N.ja[kl]=I18N_L.ja[kl]}













I18N.he={nav_wizard:'אשף הגדרה',nav_orch:'אורקסטרטורים',nav_sse:'פלטפורמות SSE',nav_svc:'שירותים',nav_config:'הגדרות',nav_update:'עדכונים',nav_users:'משתמשים',nav_tools:'כלים',nav_tls:'תעודות',nav_debug:'אבחון',nav_out:'יציאה',tagline:'ניהול EdgeConnect SD-WAN ו-SSE',login_title:'מרכז ניהול',login_user:'שם משתמש',login_pass:'סיסמה',login_enter:'כניסה',u_name:'שם משתמש',h2_orch:'אורקסטרטורים',h2_sse:'פלטפורמות SSE',h2_svc:'שירותים',h2_config:'הגדרות השירות',h2_update:'עדכונים',h2_wizard:'אשף הגדרה',btn_save:'שמירה',btn_save_vars:'שמירת הגדרות',btn_save_restart:'שמירה והפעלה מחדש',btn_save_restart_short:'שמירה והפעלה מחדש',btn_recheck:'בדיקה חוזרת',btn_probe:'בדיקה',btn_edit:'עריכה',btn_delete:'מחיקה',btn_next:'הבא',btn_back:'הקודם',btn_review:'סקירת שינויים',loading:'טוען...',yes:'כן',no:'לא',menu_custom:'התאמה אישית',top_home:'ראשי',top_heading:'מרכז תפעול SASE',top_caption:'מפת תצורה לוגית; הקווים אינם מציגים תעבורה או חיבורים פעילים.',top_sub:'ניהול חיבורי SD-WAN ו-SSE במקום אחד.',top_map:'מפת חיבורים',top_check:'בדיקת חיבורים',top_checking:'בודק…',top_last:'בדיקה אחרונה: ',top_none:'טרם נבדק',top_connected:'מחובר',top_problem:'קיימת בעיה',top_ai:'עוזרי בינה מלאכותית',top_sessions:'גישה ותקשורת · החיבורים לא נבדקו',top_panel_ver:'גרסת הממשק: ',top_info:'מידע נוסף',top_open:'פתיחת הגדרות',top_missing:'לא נשמרו יעדים',top_first:'הגדרת חיבור ראשון',top_unavailable:'גרסאות היעדים ומספר ההתקנים אינם זמינים בתצוגה זו.',top_default:'יעד ברירת מחדל',top_saved:'יעד שמור',top_platform:'פלטפורמה שמורה',secret_set:'הסוד מוגדר ואינו מוצג',secret_unset:'לא הוגדר סוד'};

var EXTRA_UI={
 es:['Descripción del sitio','Estilo de animación','Flujo','Pulso','Sin animación','Los efectos son decorativos y se aplican a este navegador.','Diagnóstico Linux (solo lectura · administrador)','Comandos predefinidos; salida limitada. Revisa los registros antes de compartirlos.','Memoria','Disco','Estado de servicios','Registro del MCP','Registro del panel','Ejecutando…','Usuario','API del panel: método, ruta, estado y duración. No se garantiza la captura de cada API upstream.'],
 en:['Site description','Animation style','Flow','Pulse','No animation','Effects are decorative and apply in this browser.','Linux diagnostics (read-only · administrator)','Fixed commands with bounded output. Review logs before sharing.','Memory','Disk','Service status','MCP journal','Admin journal','Running…','User','Panel API: method, path, status and duration. Not every upstream API is captured.'],
 pt:['Descrição do site','Estilo de animação','Fluxo','Pulso','Sem animação','Os efeitos são decorativos neste navegador.','Diagnóstico Linux (somente leitura · administrador)','Comandos fixos com saída limitada. Revise os registros antes de compartilhar.','Memória','Disco','Estado dos serviços','Log do MCP','Log do painel','Executando…','Usuário','API do painel: método, rota, estado e duração. Nem todas as APIs upstream são registradas.'],
 it:['Descrizione del sito','Stile animazione','Flusso','Impulso','Nessuna animazione','Gli effetti sono decorativi in questo browser.','Diagnostica Linux (sola lettura · amministratore)','Comandi fissi con output limitato. Controllare i log prima di condividerli.','Memoria','Disco','Stato servizi','Log MCP','Log pannello','Esecuzione…','Utente','API pannello: metodo, percorso, stato e durata. Non tutte le API upstream sono registrate.'],
 de:['Website-Beschreibung','Animationsstil','Fluss','Puls','Keine Animation','Effekte sind in diesem Browser dekorativ.','Linux-Diagnose (nur Lesen · Administrator)','Feste Befehle mit begrenzter Ausgabe. Protokolle vor dem Teilen prüfen.','Speicher','Datenträger','Dienststatus','MCP-Protokoll','Panel-Protokoll','Wird ausgeführt…','Benutzer','Panel-API: Methode, Pfad, Status und Dauer. Nicht alle Upstream-APIs werden erfasst.'],
 fr:['Description du site','Style d’animation','Flux','Impulsion','Sans animation','Les effets sont décoratifs dans ce navigateur.','Diagnostic Linux (lecture seule · administrateur)','Commandes fixes à sortie limitée. Vérifiez les journaux avant partage.','Mémoire','Disque','État des services','Journal MCP','Journal du panneau','Exécution…','Utilisateur','API du panneau : méthode, chemin, état et durée. Toutes les API amont ne sont pas enregistrées.'],
 ja:['サイトの説明','アニメーション','フロー','パルス','アニメーションなし','効果はこのブラウザー内の装飾です。','Linux診断（読み取り専用・管理者）','固定コマンドと制限された出力。共有前にログを確認してください。','メモリ','ディスク','サービス状態','MCPログ','管理画面ログ','実行中…','ユーザー','管理APIのメソッド、パス、状態、所要時間。すべての上流APIは記録されません。'],
 he:['תיאור האתר','סגנון הנפשה','זרימה','פעימה','ללא הנפשה','האפקטים הם קישוט בדפדפן זה.','אבחון Linux (קריאה בלבד · מנהל)','פקודות קבועות עם פלט מוגבל. יש לבדוק יומנים לפני שיתוף.','זיכרון','דיסק','מצב שירותים','יומן MCP','יומן ממשק הניהול','מתבצע…','משתמש','API של הממשק: שיטה, נתיב, מצב ומשך. לא כל ממשקי ה־API נרשמים.']
};
var EXTRA_KEYS=['custom_tagline','animation_style','effect_flow','effect_pulse','effect_none','effect_help','diag_title','diag_help','diag_memory','diag_disk','diag_status','diag_mcp_log','diag_admin_log','diag_running','diag_user','diag_api_help'];
Object.keys(EXTRA_UI).forEach(function(lang){if(!I18N[lang])I18N[lang]={};EXTRA_KEYS.forEach(function(key,i){I18N[lang][key]=EXTRA_UI[lang][i]})});if(I18N.mx)EXTRA_KEYS.forEach(function(key,i){I18N.mx[key]=EXTRA_UI.es[i]});
var EXTRA_TOOLS={
 es:['Resultado correcto','No se pudo completar','Información','Buscar herramienta','Nombre o descripción','Estado','Habilitadas','Deshabilitadas','Monitoreo recomendado','Todas las herramientas','Habilitar todas','¿Habilitar todas las tools? Se aplicará después de reiniciar; las políticas de escritura siguen vigentes.','Anterior','Siguiente','Página','No hay herramientas para este filtro.','Cambios guardados; reinicia el MCP para aplicarlos.'],
 en:['Completed','Could not complete','Information','Search tools','Name or description','Status','Enabled','Disabled','Recommended monitoring','All tools','Enable all','Enable all tools? Applied after restart; write policies still apply.','Previous','Next','Page','No tools match this filter.','Changes saved; restart the MCP to apply them.'],
 pt:['Concluído','Não foi possível concluir','Informação','Buscar ferramentas','Nome ou descrição','Estado','Ativadas','Desativadas','Monitoramento recomendado','Todas as ferramentas','Ativar todas','Ativar todas as ferramentas? Aplicado após reiniciar; políticas de escrita permanecem.','Anterior','Próxima','Página','Nenhuma ferramenta neste filtro.','Alterações salvas; reinicie o MCP para aplicar.'],
 it:['Completato','Impossibile completare','Informazione','Cerca strumenti','Nome o descrizione','Stato','Abilitati','Disabilitati','Monitoraggio consigliato','Tutti gli strumenti','Abilita tutti','Abilitare tutti gli strumenti? Dopo il riavvio restano valide le regole di scrittura.','Precedente','Successiva','Pagina','Nessuno strumento corrisponde.','Modifiche salvate; riavviare MCP.'],
 de:['Abgeschlossen','Nicht abgeschlossen','Information','Tools suchen','Name oder Beschreibung','Status','Aktiviert','Deaktiviert','Empfohlenes Monitoring','Alle Tools','Alle aktivieren','Alle Tools aktivieren? Nach Neustart wirksam; Schreibregeln gelten weiterhin.','Zurück','Weiter','Seite','Keine Tools für diesen Filter.','Änderungen gespeichert; MCP neu starten.'],
 fr:['Terminé','Échec','Information','Rechercher des outils','Nom ou description','État','Activés','Désactivés','Surveillance recommandée','Tous les outils','Tout activer','Activer tous les outils ? Après redémarrage ; les règles d’écriture restent applicables.','Précédent','Suivant','Page','Aucun outil pour ce filtre.','Modifications enregistrées ; redémarrez MCP.'],
 ja:['完了','完了できません','情報','ツール検索','名前または説明','状態','有効','無効','推奨監視','すべてのツール','すべて有効化','すべてのツールを有効にしますか？再起動後に適用され、書き込み規則は維持されます。','前へ','次へ','ページ','該当するツールはありません。','保存しました。MCPを再起動してください。'],
 he:['הושלם','לא ניתן להשלים','מידע','חיפוש כלים','שם או תיאור','מצב','פעילים','מושבתים','ניטור מומלץ','כל הכלים','הפעלת הכל','להפעיל את כל הכלים? יוחל לאחר הפעלה מחדש; מדיניות כתיבה תישאר בתוקף.','הקודם','הבא','עמוד','אין כלים מתאימים.','השינויים נשמרו; יש להפעיל את MCP מחדש.']
};
var EXTRA_TOOL_KEYS=['notice_ok','notice_err','notice_info','tools_search','tools_search_hint','tools_state','tools_enabled','tools_disabled_label','tools_recommended','tools_all','tools_enable_all','tools_enable_all_confirm','tools_prev','tools_next','tools_page','tools_empty','tools_restart'];
Object.keys(EXTRA_TOOLS).forEach(function(lang){EXTRA_TOOL_KEYS.forEach(function(key,i){I18N[lang][key]=EXTRA_TOOLS[lang][i]})});if(I18N.mx)EXTRA_TOOL_KEYS.forEach(function(key,i){I18N.mx[key]=EXTRA_TOOLS.es[i]});
var AUDIT_CLEAR_I18N={es:['Limpiar búfer','¿Limpiar solo el búfer temporal del panel? La auditoría persistente se conserva.'],en:['Clear buffer','Clear only the temporary panel buffer? Persistent audit logs are retained.'],mx:['Limpiar búfer','¿Limpiar solo el búfer temporal del panel? La auditoría persistente se conserva.'],pt:['Limpar buffer','Limpar apenas o buffer temporário? O registro de auditoria será preservado.'],it:['Svuota buffer','Svuotare solo il buffer temporaneo? Il registro di audit sarà conservato.'],de:['Puffer leeren','Nur den temporären Puffer leeren? Das Auditprotokoll bleibt erhalten.'],fr:['Vider le tampon','Vider uniquement le tampon temporaire ? Le journal d’audit sera conservé.'],ja:['バッファを消去','一時バッファのみを消去しますか？監査ログは保持されます。'],he:['ניקוי מאגר','לנקות רק את המאגר הזמני? יומן הביקורת יישמר.']};
Object.keys(AUDIT_CLEAR_I18N).forEach(function(lang){if(I18N[lang]){I18N[lang].dbg_clear=AUDIT_CLEAR_I18N[lang][0];I18N[lang].dbg_clear_confirm=AUDIT_CLEAR_I18N[lang][1]}});
function q(s){return document.querySelector(s)}
function esc(v){return String(v==null?'':v).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
async function api(path,body){
 var options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
 var response=await fetch(path,options);
 var data;
 try{data=await response.json()}catch(e){data={ok:false,error:(await response.text()).slice(0,300)||('HTTP '+response.status)}}
 if(response.status===401){AUTHED=false;renderLogin();throw new Error('Sesión expirada');}
 return data;
}
function notice(message,type){
 var node=q('#notice');if(!node)return;var kind=type==='err'?'err':type==='ok'?'ok':'info';
 var title=t(kind==='err'?'notice_err':kind==='ok'?'notice_ok':'notice_info'),icon=kind==='err'?'!':kind==='ok'?'✓':'i';
 node.innerHTML='<div class="notice-card '+kind+'" role="'+(kind==='err'?'alert':'status')+'"><span class="notice-icon" aria-hidden="true">'+icon+'</span><div class="notice-body"><strong>'+esc(title)+'</strong><span>'+esc(message)+'</span></div><button type="button" class="notice-close" aria-label="Close" onclick="q(\'#notice\').innerHTML=\'\'">×</button></div>';
}
function renderLogin(){
 q('#app').innerHTML='<section class="panel" style="max-width:440px;margin:12vh auto">'+brandHtml()+chromeHtml()+'<form onsubmit="login();return false"><label style="margin-top:22px">'+t('u_name')+'<input id="login-user" autocomplete="username"></label><label style="margin-top:12px">'+t('login_pass')+'<input id="login-password" type="password" autocomplete="current-password"></label><div class="actions"><button type="submit">'+t('login_enter')+'</button></div></form><div id="notice"></div></section>';
 if(!q('#custom-dlg'))q('#app').innerHTML+=customDialogHtml();
}
async function login(){
 try{var r=await api('/login',{username:q('#login-user').value,password:q('#login-password').value});if(!r.ok){notice(r.error||'Contraseña incorrecta','err');return}ME=r;AUTHED=true;renderShell();await loadAll();}
 catch(e){notice(e.message,'err')}
}
async function logout(){await api('/logout',{});AUTHED=false;renderLogin()}
function closeMenusOnOutsideClick(){document.addEventListener('click',function(e){if(!e.target.closest||!e.target.closest('details.menu')){document.querySelectorAll('details.menu').forEach(function(d){d.removeAttribute('open')})}})}
if(document.addEventListener)closeMenusOnOutsideClick();
function renderShell(){
 q('#app').innerHTML='<header class="topbar">'+brandHtml()+'<div class="topbar-actions"><span class="version">__EC_MCP_VERSION__</span>'+userChip()+chromeHtml()+'</div></header>'+
 '<nav aria-label="Navegación principal"><button id="tab-home" onclick="showTab(\'home\')">'+(LANG==='he'?t('top_home'):((LANG==='es'||LANG==='mx')?'Inicio':'Home'))+'</button><button id="tab-wizard" onclick="showTab(\'wizard\')">'+t('nav_wizard')+'</button><button id="tab-orch" onclick="showTab(\'orch\')">'+t('nav_orch')+'</button><button id="tab-sse" onclick="showTab(\'sse\')">'+t('nav_sse')+'</button><button id="tab-svc" onclick="showTab(\'svc\')">'+t('nav_svc')+'</button><button id="tab-config" onclick="showTab(\'config\')">'+t('nav_config')+'</button><button id="tab-tls" onclick="showTab(\'tls\')">'+t('nav_tls')+'</button><button id="tab-tools" onclick="showTab(\'tools\')">'+t('nav_tools')+'</button><button id="tab-debug" onclick="showTab(\'debug\')">'+t('nav_debug')+'</button><button id="tab-update" onclick="showTab(\'update\')">'+t('nav_update')+'</button><button id="tab-users" onclick="showTab(\'users\')">'+t('nav_users')+'</button></nav>'+
 '<div id="notice"></div><section id="workspace"></section>'+customDialogHtml()+footerHtml();
 if(ME&&ME.role!=='admin'){var ub=q('#tab-users');if(ub)ub.style.display='none'}
 showTab('home');
}
function showTab(name){
 CURTAB=name;
 var ws=q('#workspace');
 if(ws&&ws.dataset){var contexts={wizard:'SETUP / CONFIGURACIÓN',orch:'SD-WAN / ORCHESTRATORS',sse:'SSE / PLATAFORMAS',svc:'OPERATIONS / SERVICIOS',config:'SYSTEM / VARIABLES',tls:'SECURITY / CERTIFICADOS',tools:'MCP / TOOLS',debug:'OBSERVABILITY / DEBUG',update:'SYSTEM / ACTUALIZACIONES',users:'IDENTITY / USUARIOS'};ws.dataset.section=name;ws.dataset.context=contexts[name]||''}
 if(ws&&ws.animate&&localStorage.getItem('ec-effect')!=='quiet'&&!(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches))
  ws.animate([{opacity:.25,transform:'translateY(14px) scale(.99)',filter:'blur(4px)'},{opacity:1,transform:'none',filter:'blur(0)'}],{duration:420,easing:'cubic-bezier(.2,.8,.2,1)'});
 var ntc=q('#notice');if(ntc)ntc.innerHTML='';
 document.querySelectorAll('nav button').forEach(function(b){b.classList.remove('active-tab')});
 var tab=q('#tab-'+name);if(tab)tab.classList.add('active-tab');
 if(name==='home')renderTopology();
 if(name==='wizard')renderWizard();
 if(name==='orch')renderOrchestrators();
 if(name==='sse')renderSse();
 if(name==='svc')renderServices();
 if(name==='config')renderConfig();
 if(name==='update')renderUpdate();
 if(name==='users')renderUsers();
 if(name==='tls')renderTls();
 if(name==='tools')renderTools();
 if(name==='debug')renderDebug();
 if(name!=='debug'&&typeof dbgStop==='function')dbgStop();
}

function topologyState(entry){
 if(!entry)return {label:LANG==='he'?t('top_none'):((LANG==='es'||LANG==='mx')?'Sin comprobar':'Not checked'),cls:'unknown'};
 if(entry.state==='up')return {label:LANG==='he'?t('top_connected'):((LANG==='es'||LANG==='mx')?'Conectado':'Connected'),cls:'up'};
 if(entry.state==='down')return {label:LANG==='he'?t('top_problem'):((LANG==='es'||LANG==='mx')?'Con problemas':'Problem detected'),cls:'down'};
 return {label:LANG==='he'?t('top_none'):((LANG==='es'||LANG==='mx')?'Sin comprobar':'Not checked'),cls:'unknown'};
}
function topologyBadge(entry){var st=topologyState(entry);return '<span class="topology-status '+st.cls+'">'+esc(st.label)+'</span>'}
function topologyEntry(kind,name){var items=TOPOLOGY_STATUS&&(kind==='orch'?TOPOLOGY_STATUS.orchestrators:TOPOLOGY_STATUS.sse_platforms)||[];return items.find(function(x){return x.name===name})}
function topologyCard(kind,item){
 var isOrch=kind==='orch',entry=topologyEntry(kind,item.name),sub=isOrch?'Orchestrator':'Axis / SSE';
 var detail=entry&&entry.error?entry.error:(isOrch?(item.default?((LANG==='es'||LANG==='mx')?'Destino predeterminado':'Default target'):((LANG==='es'||LANG==='mx')?'Destino guardado':'Saved target')):((LANG==='es'||LANG==='mx')?'Plataforma guardada':'Saved platform'));
 var when=entry&&entry.checked_at?entry.checked_at:((LANG==='es'||LANG==='mx')?'Sin comprobación':'Not checked');
 var hint=(LANG==='he'?t('top_last'):((LANG==='es'||LANG==='mx')?'Última comprobación: ':'Last check: '))+when;
 return '<button type="button" class="topology-card" data-kind="'+kind+'" data-name="'+esc(item.name)+'" onclick="openTopologyTarget(this)" title="'+esc(hint)+'" aria-label="'+esc(sub+': '+item.name+'. '+hint)+'"><span class="tag">'+esc(sub)+'</span><strong>'+esc(item.name)+'</strong><small>'+esc(detail)+'</small>'+topologyBadge(entry)+'<span class="topology-detail">'+esc(hint)+' · '+(LANG==='he'?t('top_open'):((LANG==='es'||LANG==='mx')?'Abrir configuración':'Open settings'))+'</span></button>';
}
function openTopologyTarget(button){
 var kind=button.dataset.kind,name=button.dataset.name;
 if(kind==='orch'){showTab('orch');editOrch(name)}else{showTab('sse');editSse(name)}
}
async function refreshTopology(){
 if(TOPOLOGY_BUSY)return;TOPOLOGY_BUSY=true;renderTopology();
 try{var r=await api('/api/services/status');if(r.error||r.ok===false)throw Error(r.error||'Status unavailable');TOPOLOGY_STATUS=r}
 catch(e){TOPOLOGY_STATUS=null;notice(e.message,'err')}
 finally{TOPOLOGY_BUSY=false;if(CURTAB==='home')renderTopology()}
}
var SASE_KIND='all',SASE_SEARCH='';
function renderTopology(){
 var orchs=STATE.orchestrators||[],sses=STATE.sse_platforms||[],mcp=TOPOLOGY_STATUS&&TOPOLOGY_STATUS.mcp_transport;
 var es=(LANG==='es'||LANG==='mx'),check=TOPOLOGY_STATUS&&TOPOLOGY_STATUS.checked_at?TOPOLOGY_STATUS.checked_at:(es?'Sin comprobar':'Not checked');
 var missing=es?'Aún no hay conexiones configuradas.':'No connections configured yet.';
 var oc=orchs.map(function(o){return topologyCard('orch',o)}).join(''),sc=sses.map(function(o){return topologyCard('sse',o)}).join('');
 var empty='<p class="topology-caption">'+esc(missing)+'</p>';
 var heading=LANG==='he'?t('top_heading'):(es?'Centro de operaciones de SASE':'SASE operations center');
 var caption=LANG==='he'?t('top_caption'):(es?'Vista lógica de la configuración. La animación no representa tráfico ni sesiones activas.':'Logical configuration view. Animation does not represent live traffic or sessions.');
 var statusCaption=es?'Última comprobación: ':'Last checked: ';
 var group=function(kind,title,count,items){return '<section class="topology-group" data-group="'+kind+'"><div class="sase-group-head"><h3>'+title+'</h3><span class="sase-count">'+count+'</span></div><div class="topology-list">'+(items||empty)+'</div></section>'};
 var filter=function(kind,label,count){return '<button type="button" data-filter="'+kind+'" aria-pressed="'+(SASE_KIND===kind)+'" onclick="setSaseKind(this.dataset.filter)">'+label+' <span>'+count+'</span></button>'};
 q('#workspace').innerHTML='<section class="topology"><div class="topology-hero"><div class="sase-holo" aria-hidden="true"><span class="sase-holo-grid"></span><span class="sase-orbit"></span><span class="sase-orbit alt"></span><span class="sase-planet-orbit planet-one"><i></i></span><span class="sase-planet-orbit planet-two"><i></i></span><span class="sase-core">SASE</span></div><div class="topology-eyebrow">SASE · CONTROL CENTER</div><h1>'+heading+'</h1><p>'+(LANG==='he'?t('top_sub'):(es?'Una vista clara de tus conexiones SD-WAN y SSE.':'A clear view of your SD-WAN and SSE connections.'))+'</p><div class="sase-hero-meta"><span class="sase-pill">MCP · __EC_MCP_VERSION__</span><span class="sase-pill">'+orchs.length+' Orchestrators</span><span class="sase-pill">'+sses.length+' SSE</span></div></div>'+
 '<div class="topology-body"><div class="topology-head"><div><h2>'+(LANG==='he'?t('top_map'):(es?'Mapa de conexiones':'Connection map'))+'</h2><p class="topology-caption">'+caption+'</p></div><button type="button" onclick="refreshTopology()" '+(TOPOLOGY_BUSY?'disabled':'')+'>'+(TOPOLOGY_BUSY?(es?'Comprobando…':'Checking…'):(LANG==='he'?t('top_check'):(es?'Comprobar conexiones':'Check connections')))+'</button></div>'+
 '<div class="sase-flow"><button type="button" class="sase-node" onclick="showTab(\'config\')"><span class="tag">01 · CLIENT</span><strong>'+(LANG==='he'?t('top_ai'):(es?'Asistentes de IA':'AI assistants'))+'</strong><small class="sase-ai-brands">Vibe · ChatGPT · Claude</small><small>'+(LANG==='he'?t('top_sessions'):(es?'Acceso y transporte · sesiones no verificadas':'Access and transport · sessions not verified'))+'</small></button><div class="sase-link" aria-hidden="true"></div>'+
 '<button type="button" class="sase-node" onclick="showTab(\'svc\')" title="'+esc(statusCaption+check)+'"><span class="tag">02 · MCP SERVER</span><strong>EdgeConnect MCP</strong><small>'+(LANG==='he'?t('top_panel_ver'):(es?'Versión del panel: ':'Panel version: '))+'__EC_MCP_VERSION__</small>'+topologyBadge(mcp)+'</button><div class="sase-link" aria-hidden="true"></div>'+
 '<button type="button" class="sase-node" onclick="document.getElementById(\'sase-inventory\').scrollIntoView({behavior: \'auto\', block: \'start\'})"><span class="tag">03 · CONNECTIONS</span><strong>'+(es?'Destinos configurados':'Configured targets')+'</strong><small>'+orchs.length+' Orchestrators · '+sses.length+' SSE</small></button></div>'+
 '<section class="sase-inventory" id="sase-inventory"><div class="sase-inventory-head"><div><h3>'+(es?'Tus conexiones':'Your connections')+'</h3><p class="topology-caption">'+(es?'Busca un destino y ábrelo para administrarlo.':'Find a destination and open it to manage it.')+'</p></div><label class="sase-search" for="topology-filter">'+(es?'Buscar por nombre':'Search by name')+'<input id="topology-filter" type="search" value="'+esc(SASE_SEARCH)+'" oninput="filterTopology(this.value)" placeholder="'+(es?'Buscar conexión…':'Search connections…')+'"></label></div>'+
 '<div class="sase-filterbar" aria-label="'+(es?'Filtrar conexiones':'Filter connections')+'">'+filter('all',es?'Todas':'All',orchs.length+sses.length)+filter('orch','SD-WAN',orchs.length)+filter('sse','SSE',sses.length)+'</div><div class="topology-groups">'+group('orch','SD-WAN · Orchestrators',orchs.length,oc)+group('sse','SSE · '+(es?'Plataformas':'Platforms'),sses.length,sc)+'</div><p class="sase-empty" id="sase-empty" role="status">'+(es?'No encontramos conexiones con ese nombre.':'No connections match that name.')+'</p></section>'+
 '<div class="sase-footer"><p class="topology-caption">'+esc(statusCaption+check)+'. '+(es?'Las plataformas SSE no indican tenants descubiertos.':'SSE platforms do not indicate discovered tenants.')+'</p><div class="topology-actions"><button type="button" class="secondary" onclick="showTab(\'wizard\')">'+t('nav_wizard')+'</button><button type="button" class="secondary" onclick="showTab(\'svc\')">'+t('nav_svc')+'</button></div></div></div></section>';
 applySaseFilter();
}
function setSaseKind(kind){SASE_KIND=kind;applySaseFilter()}
function filterTopology(value){SASE_SEARCH=String(value||'');applySaseFilter()}
function applySaseFilter(){
 var term=SASE_SEARCH.trim().toLocaleLowerCase(),visible=0;
 document.querySelectorAll('.topology-card[data-kind]').forEach(function(card){var show=(SASE_KIND==='all'||card.dataset.kind===SASE_KIND)&&String(card.dataset.name||'').toLocaleLowerCase().includes(term);card.hidden=!show;if(show)visible++});
 document.querySelectorAll('.topology-group[data-group]').forEach(function(group){var kind=group.dataset.group,has=!!group.querySelector('.topology-card[data-kind]:not([hidden])');group.hidden=(SASE_KIND!=='all'&&SASE_KIND!==kind)||(!!term&&!has)});
 document.querySelectorAll('.sase-filterbar button[data-filter]').forEach(function(button){button.setAttribute('aria-pressed',String(button.dataset.filter===SASE_KIND))});
 var empty=q('#sase-empty');if(empty)empty.style.display=term&&visible===0?'block':'none';
}

async function renderServices(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_svc')+'</h2><p class="help">'+t('checking')+'</p></section>';
 try{var r=await api('/api/services/status');var h='<section class="panel"><h2>'+t('h2_svc')+'</h2><p class="help">'+t('svc_checked')+' '+esc((r.checked_at||'').replace('T',' ').split('.')[0])+' UTC. Ningún servicio se muestra como activo sin comprobación.</p>';
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
 var list=(STATE.orchestrators||[]).map(function(o){return '<div class=\"orch\"><span class=\"orch-actions\"><button class=\"secondary\" onclick=\"probeTarget(\'orchestrator\',\''+esc(o.name)+'\')\">'+t('btn_probe')+'</button><button class=\"secondary\" onclick=\"dupTarget(\'orchestrator\',\''+esc(o.name)+'\')\">'+t('btn_dup')+'</button><button class=\"secondary\" onclick=\"renTarget(\'orchestrator\',\''+esc(o.name)+'\')\">'+t('btn_ren')+'</button><button class=\"secondary\" onclick=\"setDefaultTarget(\'orchestrator\',\''+esc(o.name)+'\')\">'+t('btn_default')+'</button><button class=\"secondary\" onclick=\"editOrch(\''+esc(o.name)+'\')\">'+t('btn_edit')+'</button><button class=\"danger\" onclick=\"deleteOrch(\''+esc(o.name)+'\')\">'+t('btn_delete')+'</button></span><strong>'+esc(o.name)+'</strong> '+(o.active?'<span class=\"badge\">'+t('badge_active')+'</span>':'')+(o.default?'<span class=\"badge\">'+t('badge_default')+'</span>':'')+'<br><span class=\"help\">'+esc(o.url)+'</span> <span id=\"probe-orchestrator-'+esc(o.name)+'\"></span></div>'}).join('')||'<p class=\"help\">'+t('no_orch')+'</p>';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_orch')+'</h2>'+list+
 '<div class="group"><h3>'+t('add_update')+'</h3>'+orchPickerHtml()+'<div class="grid"><label>'+t('f_name')+'<input id="o-name"></label><label>'+t('f_url')+'<input id="o-url" placeholder="https://orchestrator.example.com"></label><label>'+t('f_apikey')+'<input id="o-key" type="password"></label><label>'+t('f_user')+'<input id="o-user"></label><label>'+t('f_pass')+'<input id="o-password" type="password"></label><label>'+t('f_tls')+'<select id="o-tls"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select></label><label>'+t('f_ssh_user')+'<input id="o-ssh-user"></label><label>'+t('f_ssh_pass')+'<input id="o-ssh-password" type="password"></label><label>'+t('f_enable')+'<input id="o-enable" type="password"></label><label>'+t('f_ssh_host')+'<input id="o-ssh-host"></label></div><div class="actions"><button onclick="saveOrch(true)">'+((LANG==='es'||LANG==='mx')?'Guardar y activar':'Save and activate')+'</button><button class="secondary" onclick="saveOrch(false)">'+t('btn_save')+'</button><button class="secondary" onclick="applyOrch()">'+t('apply_env')+'</button></div></div></section>';
}

function orchPickerHtml(){var l=STATE.orchestrators||[];if(!l.length)return '';return '<label style="margin:0 0 10px;display:flex;gap:8px;align-items:center">'+t('pick_existing')+'<select id="o-pick" style="width:auto;min-height:34px" onchange="if(this.value)editOrch(this.value)"><option value="">— '+t('new_entry')+' —</option>'+l.map(function(o){return '<option value="'+esc(o.name)+'">'+esc(o.name)+'</option>'}).join('')+'</select></label>'}
function ssePickerHtml(){var l=STATE.sse_platforms||[];if(!l.length)return '';return '<label style="margin:0 0 10px;display:flex;gap:8px;align-items:center">'+t('pick_existing')+'<select id="s-pick" style="width:auto;min-height:34px" onchange="if(this.value)editSse(this.value)"><option value="">— '+t('new_entry')+' —</option>'+l.map(function(o){return '<option value="'+esc(o.name)+'">'+esc(o.name)+'</option>'}).join('')+'</select></label>'}
function editOrch(name){var o=(STATE.orchestrators||[]).find(function(x){return x.name===name});if(!o)return;q('#o-name').value=o.name;q('#o-url').value=o.url;q('#o-user').value=o.username||'';['#o-key','#o-password','#o-ssh-password','#o-enable'].forEach(function(id){q(id).value='' });q('#o-tls').value=String(o.verify_tls);q('#o-ssh-user').value=o.ssh_user||'';q('#o-ssh-host').value=o.ssh_host||''}
function confirmTargetActivation(){return confirm((LANG==='es'||LANG==='mx')?'Se guardará el destino y se reiniciarán los servicios para cargar todos los cambios pendientes. Si no hay un destino predeterminado explícito, la selección automática puede cambiar. ¿Continuar?':'Save the target and restart services to load all pending changes? If no explicit default is set, automatic target selection may change.')}
async function activateSavedTarget(){
 try{var result=await api('/api/restart',{});if(result.state==='pending'){notice((LANG==='es'||LANG==='mx')?'Destino guardado. Reinicio solicitado; espera la confirmación.':'Target saved. Restart requested; waiting for confirmation.','info');pollRestart(0)}else notice((LANG==='es'||LANG==='mx'?'Destino guardado, pero no se pudo solicitar el reinicio: ':'Target saved, but restart could not be requested: ')+(result.error||result.message||'unknown'),'err')}
 catch(e){notice(((LANG==='es'||LANG==='mx')?'Destino guardado; reinicio no solicitado: ':'Target saved; restart was not requested: ')+e.message,'err')}
}
async function saveOrch(activate){
 if(activate&&!confirmTargetActivation())return;
 try{var r=await api('/api/orchestrators',{name:q('#o-name').value.trim(),url:q('#o-url').value.trim(),api_key:q('#o-key').value,username:q('#o-user').value,password:q('#o-password').value,verify_tls:q('#o-tls').value==='true',ssh_user:q('#o-ssh-user').value,ssh_password:q('#o-ssh-password').value,ssh_enable_password:q('#o-enable').value,ssh_host:q('#o-ssh-host').value});if(!r.ok){notice(r.error||r.message,'err');return}STATE=await api('/api/state');renderOrchestrators();notice(r.message,'ok');if(activate)await activateSavedTarget()}catch(e){notice(e.message,'err')}
}
async function deleteOrch(name){if(!confirm('Eliminar '+name+'?'))return;await api('/api/orchestrators/delete',{name:name});STATE=await api('/api/state');renderOrchestrators()}
async function applyOrch(){try{var r=await api('/api/apply',{name:q('#o-name').value.trim(),kind:'orchestrator'});notice(r.message||r.error,r.ok?'ok':'err');CONFIG=await api('/api/config')}catch(e){notice(e.message,'err')}}
function renderSse(){
 var list=(STATE.sse_platforms||[]).map(function(o){return '<div class=\"orch\"><span class=\"orch-actions\"><button class=\"secondary\" onclick=\"probeTarget(\'sse\',\''+esc(o.name)+'\')\">'+t('btn_probe')+'</button><button class=\"secondary\" onclick=\"dupTarget(\'sse\',\''+esc(o.name)+'\')\">'+t('btn_dup')+'</button><button class=\"secondary\" onclick=\"renTarget(\'sse\',\''+esc(o.name)+'\')\">'+t('btn_ren')+'</button><button class=\"secondary\" onclick=\"setDefaultTarget(\'sse\',\''+esc(o.name)+'\')\">'+t('btn_default')+'</button><button class=\"secondary\" onclick=\"editSse(\''+esc(o.name)+'\')\">'+t('btn_edit')+'</button><button class=\"danger\" onclick=\"deleteSse(\''+esc(o.name)+'\')\">'+t('btn_delete')+'</button></span><strong>'+esc(o.name)+'</strong> '+(o.active?'<span class=\"badge\">'+t('badge_active')+'</span>':'')+(o.default?'<span class=\"badge\">'+t('badge_default')+'</span>':'')+' <span class=\"badge\">'+esc(o.provider)+'</span><br><span class=\"help\">'+esc(o.base_url)+'</span> <span id=\"probe-sse-'+esc(o.name)+'\"></span></div>'}).join('')||'<p class=\"help\">'+t('no_sse')+'</p>';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_sse')+'</h2><p>'+((LANG==='es'||LANG==='mx')?'Administra plataformas SSE independientes, cada una con su token y URL.':'Manage independent SSE platforms, each with its own token and URL.')+'</p>'+list+
 '<div class="group"><h3>'+t('add_update_sse')+'</h3>'+ssePickerHtml()+'<div class="grid"><label>'+t('f_name')+'<input id="s-name" placeholder="axis-prod"></label><label>'+t('f_provider')+'<select id="s-provider"><option>axis</option></select></label><label>'+t('f_baseurl')+'<input id="s-url" placeholder="https://admin-api.axissecurity.com"></label><label>'+t('f_token')+'<input id="s-token" type="password" autocomplete="new-password"><span class="help" id="s-token-status"></span></label><label>'+t('f_tls')+'<select id="s-tls"><option value="true">'+t('yes')+'</option><option value="false">'+t('no')+'</option></select></label><label>'+t('f_timeout')+'<input id="s-timeout" type="number" value="30"></label></div><div class="actions"><button onclick="saveSse(true)">'+((LANG==='es'||LANG==='mx')?'Guardar y activar':'Save and activate')+'</button><button class="secondary" onclick="saveSse(false)">'+t('btn_save')+'</button><button class="secondary" onclick="applySse()">'+t('apply_env')+'</button></div></div></section>';
}
function editSse(name){var o=(STATE.sse_platforms||[]).find(function(x){return x.name===name});if(!o)return;q('#s-name').value=o.name;q('#s-provider').value=o.provider;q('#s-url').value=o.base_url;q('#s-token').value='';q('#s-token-status').textContent=o.has_admin_token?t('secret_set'):t('secret_unset');var picker=q('#s-pick');if(picker)picker.value=o.name;q('#s-tls').value=String(o.verify_tls);q('#s-timeout').value=o.timeout}
async function saveSse(activate){
 if(activate&&!confirmTargetActivation())return;
 try{var savedName=q('#s-name').value.trim();var r=await api('/api/sse',{name:savedName,provider:q('#s-provider').value,base_url:q('#s-url').value.trim(),admin_token:q('#s-token').value,verify_tls:q('#s-tls').value==='true',timeout:q('#s-timeout').value});if(!r.ok){notice(r.error||r.message,'err');return}STATE=await api('/api/state');renderSse();editSse(savedName);notice(r.message,'ok');if(activate)await activateSavedTarget()}catch(e){notice(e.message,'err')}
}
async function deleteSse(name){if(!confirm('Eliminar plataforma '+name+'?'))return;await api('/api/sse/delete',{name:name});STATE=await api('/api/state');renderSse()}
async function applySse(){var name=q('#s-name').value.trim();if(!name){notice((LANG==='es'||LANG==='mx')?'Selecciona una plataforma SSE guardada antes de aplicar.':'Select a saved SSE platform before applying.','err');return}try{var r=await api('/api/apply',{name:name,kind:'sse'});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)CONFIG=await api('/api/config')}catch(e){notice(e.message,'err')}}
async function renderWizard(){
 if(!WIZARD){
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_wizard')+'</h2><p class="help">'+t('wiz_loading')+'</p></section>';
  try{WIZARD=await api('/api/wizard')}catch(e){notice(e.message,'err');return}
  WSTEP=-1;WDRAFT={};WREVIEW=null;
  WIZARD.fields.forEach(function(f){WDRAFT[f.key]=f.secret?'':f.value});
 }
 if(WSTEP<0){q('#workspace').innerHTML=wizHomeHtml();return}
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

function quickChipsHtml(steps){
 var map=[['targets','q_add_orch'],['targets','q_add_sse'],['orchestrator','q_main_orch'],['sse','q_sse_env'],['panel','q_panel']];
 var h='<div class="wizbar">';
 map.forEach(function(m){var st=steps.find(function(x){return x.id===m[0]});if(st)h+='<button class="secondary" style="padding:4px 9px;font-size:.75rem" onclick="wizGoto(\''+m[0]+'\')">'+t(m[1])+'</button>'});
 return h+'</div>';
}
function wizGoto(id){var i=WIZARD.steps.findIndex(function(x){return x.id===id});if(i>=0){WSTEP=i;wizRenderStep()}}
function wizRenderStep(){
 var steps=WIZARD.steps,s=steps[WSTEP],fields=wizFields(s.id);
 var bar=steps.map(function(st,i){return '<span class="badge" style="'+(i===WSTEP?'border-color:#00739d;color:#07516a':'')+'">'+(i+1)+' '+esc(st['title_'+LANG]||st.title)+'</span>'}).join(' ');
 var targets=s.id==='targets'?wizTargetsHtml():'';
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('wiz_step',{a:WSTEP+1,b:steps.length})+' '+esc(s['title_'+LANG]||s.title)+'</h2><div class="wizbar">'+bar+'</div>'+'<p class="help">'+esc(s['desc_'+LANG]||s.desc||'')+'</p>'+quickChipsHtml(steps)+
  (s.id==='targets'?'<p class="help">'+t('wiz_targets_help')+'</p>':'')+
  '<div class="group"><div class="grid">'+fields.map(wizFieldHtml).join('')+'</div></div>'+targets+
  '<div class="actions">'+(WSTEP>=0?'<button class="secondary" onclick="wizHome()" title="'+t('wiz_home_title')+'">&#8962;</button>':'')+(WSTEP>=0&&stepSkippable(s)?'<button class="secondary" onclick="wizSkip()">'+t('btn_skip')+'</button>':'')+'<button class="secondary" onclick="wizBack()" '+(WSTEP===0?'disabled':'')+'>'+t('btn_back')+'</button><button onclick="wizNext()">'+(WSTEP===steps.length-1?t('btn_review'):t('btn_next'))+'</button></div></section>';
 fields.forEach(function(f){var el=q('#wiz-'+f.key);if(el){el.value=(WDRAFT[f.key]!==undefined?WDRAFT[f.key]:(f.secret?'':f.value));el.addEventListener('input',function(){WDRAFT[f.key]=el.value;WREVIEW=null;wizRefreshDepends()});el.addEventListener('change',function(){WDRAFT[f.key]=el.value;WREVIEW=null;wizRefreshDepends()})}});
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
function wizCollect(){var values={};WIZARD.fields.forEach(function(f){if(!wizDependsOk(f))return;var v=WDRAFT[f.key];if(v===undefined||v===null)return;if(f.secret){if(v!=='')values[f.key]=v}else if(String(v)!==String(f.value==null?'':f.value))values[f.key]=v});return values}
async function wizNext(){
 var errs=wizValidateStep();
 wizFields(WIZARD.steps[WSTEP].id).forEach(function(f){var el=q('#wiz-'+f.key);if(el)WDRAFT[f.key]=el.value});
 if(errs.length){notice(errs.join('\n'),'err');return}
 if(WSTEP<WIZARD.steps.length-1){WSTEP++;wizRenderStep();return}
 await wizReview();
}
function wizBack(){WREVIEW=null;if(WSTEP>0){WSTEP--;wizRenderStep()}else if(WSTEP===0){wizHome()}}
function wizHome(){WSTEP=-1;q('#workspace').innerHTML=wizHomeHtml()}
function wizHomeHtml(){
 var orchs=STATE.orchestrators||[], sses=STATE.sse_platforms||[];
 var sdwan, sse;
 if(orchs.length){sdwan='<p><strong>'+orchs.length+'</strong> '+t('wiz_orchs_saved')+': '+orchs.map(function(o){return '<span class="badge">'+esc(o.name)+(o.default?' ('+t('badge_default')+')':'')+'</span>'}).join(' ')+'</p><div class="actions"><button onclick="wizGoto(\'targets\')">'+t('q_add_orch')+'</button><button class="secondary" onclick="showTab(\'orch\')">'+t('btn_edit')+'</button></div>'}
 else{sdwan='<p class="help">'+t('wiz_no_orch')+'</p><div class="actions"><button onclick="wizGoto(\'orchestrator\')">'+t('wiz_setup_first')+'</button></div>'}
 if(sses.length){sse='<p><strong>'+sses.length+'</strong> '+t('wiz_sse_saved')+': '+sses.map(function(o){return '<span class="badge">'+esc(o.name)+'</span>'}).join(' ')+'</p><div class="actions"><button onclick="wizGoto(\'targets\')">'+t('q_add_sse')+'</button><button class="secondary" onclick="showTab(\'sse\')">'+t('btn_edit')+'</button></div>'}
 else{sse='<p class="help">'+t('wiz_no_sse')+'</p><div class="actions"><button onclick="wizGoto(\'sse\')">'+t('wiz_setup_sse')+'</button></div>'}
 return '<section class="panel"><h2>'+t('wiz_home_title')+'</h2><p class="help">'+t('wiz_home_desc')+'</p>'+
 '<div class="grid"><div class="group"><h3>SD-WAN · Orchestrator</h3>'+sdwan+'</div><div class="group"><h3>SSE · Axis Security</h3>'+sse+'</div></div>'+
 '<div class="group"><h3>'+t('nav_svc')+'</h3><p class="help">'+((LANG==='es'||LANG==='mx')?'Comprueba el estado real del MCP y de las conexiones guardadas.':'Check the actual status of MCP and saved connections.')+'</p><div class="actions"><button class="secondary" onclick="showTab(\'svc\')">'+t('nav_svc')+'</button></div></div>'+
 '<div class="group"><h3>'+t('wiz_general')+'</h3><p class="help">'+t('wiz_general_desc')+'</p><div class="actions"><button class="secondary" onclick="wizGoto(\'security\')">'+t('wiz_edit_general')+'</button><button class="secondary" onclick="wizSkipAll()">'+t('wiz_skip_done')+'</button></div></div>'+
 '<div class="actions"><button onclick="WSTEP=0;wizRenderStep()">'+t('wiz_start')+'</button></div></section>';
}
function wizSkipAll(){WSTEP=WIZARD.steps.length-1;wizReview()}
function stepSkippable(s){var fs=wizFields(s.id);if(!fs.length)return false;return fs.every(function(f){return f.secret?f.configured:!!f.value})}
function wizSkip(){if(WSTEP<WIZARD.steps.length-1){WSTEP++;wizRenderStep()}else{wizReview()}}

async function wizReview(){
 WREVIEW=null;var proposed=wizCollect();
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('review_title')+'</h2><p class="help">'+t('review_desc')+'<span class="mono">'+esc(WIZARD.env_file)+'</span>'+t('review_nowrite')+'</p><div id="wiz-diff">Comprobando...</div><div class="actions"><button class="secondary" onclick="wizBack()">'+t('btn_back')+'</button><button onclick="wizSave(false)">'+t('btn_save_vars')+'</button><button onclick="wizSave(true)">'+t('btn_save_restart_short')+'</button></div></section>';
 try{
  var r=await api('/api/config/diff',{values:proposed});
  if(r.ok!==false&&!(r.errors&&r.errors.length))WREVIEW=Object.assign({},proposed);
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
  if(!WREVIEW){notice((LANG==='es'||LANG==='mx')?'Revisa los cambios antes de guardar.':'Review the changes before saving.','err');return}
  var r=await api('/api/config',{values:WREVIEW});
  if(!r.ok){notice(r.error||'Error al guardar','err');return}
  notice(r.message,'ok');WREVIEW=null;WDRAFT={};CONFIG=await api('/api/config');
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
 return '<div class="group"><h3>'+t('h2_orch')+' · '+t('targets_add_more')+'</h3>'+orch+
  '<div class="grid" style="margin-top:10px"><label>'+t('f_name')+'<input id="wo-name" placeholder="prod"></label><label>'+t('f_url')+'<input id="wo-url" placeholder="https://orchestrator.example.com"></label><label>'+t('f_apikey')+'<input id="wo-key" type="password"></label><label>'+t('f_user')+'<input id="wo-user"></label><label>'+t('f_pass')+'<input id="wo-pass" type="password"></label></div><div class="actions"><button onclick="wizSaveOrch(true)">'+((LANG==='es'||LANG==='mx')?'Guardar y activar':'Save and activate')+'</button><button class="secondary" onclick="wizSaveOrch(false)">'+t('btn_save_orch')+'</button></div></div>'+
  '<div class="group"><h3>'+t('h2_sse')+' · '+t('targets_add_more')+'</h3>'+sse+
  '<div class="grid" style="margin-top:10px"><label>'+t('f_name')+'<input id="ws-name" placeholder="axis-prod"></label><label>'+t('f_baseurl')+'<input id="ws-url" placeholder="https://admin-api.axissecurity.com"></label><label>'+t('f_token')+'<input id="ws-token" type="password"></label><label>'+t('f_timeout')+'<input id="ws-timeout" type="number" value="30"></label></div><div class="actions"><button onclick="wizSaveSse(true)">'+((LANG==='es'||LANG==='mx')?'Guardar y activar':'Save and activate')+'</button><button class="secondary" onclick="wizSaveSse(false)">'+t('btn_save_sse')+'</button></div></div>';
}
async function reloadAfterMutation(){
 STATE=await api('/api/state');
 if(CURTAB==='wizard'){WIZARD=null;WSTEP=0;await renderWizard()}else showTab(CURTAB);
}
async function wizSaveOrch(activate){
 if(activate&&!confirmTargetActivation())return;
 try{var r=await api('/api/orchestrators',{name:q('#wo-name').value.trim(),url:q('#wo-url').value.trim(),api_key:q('#wo-key').value||null,username:q('#wo-user').value||null,password:q('#wo-pass').value||null,verify_tls:true});if(!r.ok){notice(r.error||r.message,'err');return}await reloadAfterMutation();notice(r.message,'ok');if(activate)await activateSavedTarget()}catch(e){notice(e.message,'err')}
}
async function wizSaveSse(activate){
 if(activate&&!confirmTargetActivation())return;
 try{var r=await api('/api/sse',{name:q('#ws-name').value.trim(),provider:'axis',base_url:q('#ws-url').value.trim(),admin_token:q('#ws-token').value||null,verify_tls:true,timeout:q('#ws-timeout').value});if(!r.ok){notice(r.error||r.message,'err');return}await reloadAfterMutation();notice(r.message,'ok');if(activate)await activateSavedTarget()}catch(e){notice(e.message,'err')}
}
async function probeTarget(kind,name){
 var node=document.getElementById('probe-'+kind+'-'+name);if(node)node.textContent=' '+t('probing')+'';
 try{var r=await api('/api/probe',{kind:kind,name:name});if(node)node.innerHTML=' <span class="badge">'+(r.ok?'up':'down')+'</span>';notice((r.ok?t('probe_ok'):t('probe_fail'))+kind+' '+name+(r.error?' — '+r.error:''),r.ok?'ok':'err')}
 catch(e){notice(e.message,'err')}
}
function nameDialogHtml(){return '<dialog id=\"name-dlg\" style=\"max-width:480px;width:calc(100% - 30px)\"><h3 id=\"name-dlg-title\"></h3><label>'+t('f_name')+'<input id=\"name-input\"></label><div class=\"actions\"><button onclick=\"submitName()\">'+t('custom_save')+'</button><button class=\"secondary\" onclick=\"closeName()\">'+t('custom_cancel')+'</button></div></dialog>'}
function askName(kind,name,action,defval){if(!q('#name-dlg'))q('#app').innerHTML+=nameDialogHtml();q('#name-dlg-title').textContent=(action==='rename'?t('btn_ren'):t('btn_dup'))+' '+name;q('#name-input').value=defval;window.__nameAction={kind:kind,name:name,action:action};var d=q('#name-dlg');d.showModal?d.showModal():d.setAttribute('open','')}
function closeName(){var d=q('#name-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
async function submitName(){var a=window.__nameAction;if(!a)return;var nn=(q('#name-input')||{value:''}).value;closeName();if(!nn||!nn.trim())return;if(a.action==='rename')await renTarget(a.kind,a.name,nn.trim());else await dupTarget(a.kind,a.name,nn.trim())}
async function dupTarget(kind,name,nn){
 if(nn===undefined){askName(kind,name,'duplicate',name+'-copia');return}
 var path=kind==='sse'?'/api/sse/duplicate':'/api/orchestrators/duplicate';
 try{var r=await api(path,{name:name,new_name:nn.trim()});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok)await reloadAfterMutation()}catch(e){notice(e.message,'err')}
}
async function renTarget(kind,name,nn){
 if(nn===undefined){askName(kind,name,'rename',name);return}
 if(nn.trim()===name)return;
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
  '<div class="group"><h3>'+t('add_user')+'</h3><div class="grid"><label>'+t('u_name')+'<input id="u-name"></label><label>'+t('u_pass')+'<input id="u-pass" type="password" autocomplete="new-password"></label><label>'+t('u_role')+'<select id="u-role"><option>viewer</option><option>operator</option><option>admin</option></select></label></div><div class="actions"><button onclick="saveUser()">'+t('add_user')+'</button></div></div>'+
  '<div class="group"><h3>'+t('change_pass')+'</h3><div class="grid"><label>'+t('u_empty')+'<input id="p-user"></label><label>'+t('u_old')+'<input id="p-old" type="password" autocomplete="current-password"></label><label>'+t('u_new')+'<input id="p-new" type="password" autocomplete="new-password"></label></div><div class="actions"><button onclick="changePass()">'+t('change_pass')+'</button></div></div></section>';
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
 if(ts.length>6){
  var opts='<option value="global"'+(CFG_TAB==='global'?' selected':'')+'>'+t('global_vars')+'</option>'+ts.map(function(x){return '<option value="'+esc(x.id)+'"'+(CFG_TAB===x.id?' selected':'')+'>'+esc(x.label)+'</option>'}).join('');
  return '<div class="wizbar"><label style="margin:0;display:flex;gap:8px;align-items:center">'+t('view_target')+'<select id="cfg-target-sel" style="width:auto;min-height:32px" onchange="cfgTab(this.value)">'+opts+'</select></label></div>';
 }
 var h='<div class="wizbar"><button class="secondary" style="padding:5px 10px;font-size:.78rem" onclick="cfgTab(\'global\')">'+t('global_vars')+'</button>';
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
var TOOLS_ALL=[],TOOLS_DOM='all',TOOLS_QUERY='',TOOLS_STATE='all',TOOLS_GROUP='recommended',TOOLS_PAGE=0;
var TOOLS_RECOMMENDED=['orchestrator_info','list_appliances','get_wan_health','get_mos','get_tunnel_state','get_active_alarms','get_ha_status','get_availability','get_appliance_health','axis_health','get_sse_status'];
async function renderTools(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('tools_title')+'</h2><p class="help">'+t('tools_desc')+'</p><p class="help">'+t('checking')+'</p></section>';
 try{
  var r=await api('/api/tools');
  TOOLS_ALL=r.tools||[];
  var d=r.domains||{};
  var opts='<option value="all">'+t('dom_all')+' ('+r.total+')</option><option value="sdwan">SD-WAN · EdgeConnect ('+(d.sdwan||0)+')</option><option value="sse">HPE SSE · Axis ('+(d.sse||0)+')</option><option value="panel">'+t('dom_panel')+' ('+(d.panel||0)+')</option>';
  q('#workspace').innerHTML='<section class="panel"><h2>'+t('tools_title')+'</h2><p class="help">'+t('tools_desc')+'</p><p><span class="badge">'+r.total+'</span> '+t('tools_total')+' · <span class="badge">'+r.disabled.length+'</span> '+t('tools_disabled')+'</p><div class="actions" style="align-items:center"><label style="margin:0;display:flex;gap:8px;align-items:center;font-weight:700">'+t('tools_filter')+'<select id="tools-dom" style="width:auto;min-height:34px" onchange="filterTools(this.value)">'+opts+'</select></label><button class="secondary" onclick="showAgentPrompt()">'+t('agent_btn')+'</button></div><div class="tools-search"><label>'+t('tools_search')+'<input id="tools-search" type="search" placeholder="'+t('tools_search_hint')+'" oninput="filterToolsQuery(this.value)"></label><label>'+t('tools_state')+'<select id="tools-state" onchange="filterToolsState(this.value)"><option value="all">'+t('tools_all')+'</option><option value="enabled">'+t('tools_enabled')+'</option><option value="disabled">'+t('tools_disabled_label')+'</option></select></label><label>'+t('tools_filter')+'<select id="tools-group" onchange="filterToolsGroup(this.value)"><option value="recommended">'+t('tools_recommended')+'</option><option value="all">'+t('tools_all')+'</option></select></label><span id="tools-count" class="help" aria-live="polite"></span></div><div class="actions">'+(ME&&ME.role!=='viewer'?'<button class="secondary" onclick="enableAllTools()">'+t('tools_enable_all')+'</button>':'')+'</div><div class="tools-grid" id="tools-list"></div><div class="tools-pager" id="tools-pager"></div></section>';
  q('#tools-dom').value=TOOLS_DOM;q('#tools-state').value=TOOLS_STATE;q('#tools-group').value=TOOLS_GROUP;q('#tools-search').value=TOOLS_QUERY;renderToolsGrid();
 }catch(e){notice(e.message,'err')}
}
function filterTools(v){TOOLS_DOM=v;TOOLS_PAGE=0;renderToolsGrid()}
function filterToolsQuery(v){TOOLS_QUERY=v.toLowerCase().trim();TOOLS_PAGE=0;renderToolsGrid()}
function filterToolsState(v){TOOLS_STATE=v;TOOLS_PAGE=0;renderToolsGrid()}
function filterToolsGroup(v){TOOLS_GROUP=v;TOOLS_PAGE=0;renderToolsGrid()}
function toolsPage(n){TOOLS_PAGE=n;renderToolsGrid()}
function renderToolsGrid(){
 var canWrite=ME&&ME.role!=='viewer';
 var list=TOOLS_ALL.filter(function(x){var domain=TOOLS_DOM==='all'||x.domain===TOOLS_DOM;var state=TOOLS_STATE==='all'||(TOOLS_STATE==='enabled'?!x.disabled:x.disabled);var search=!TOOLS_QUERY||(x.name+' '+(x.description||'')+' '+(x.description_es||'')).toLowerCase().includes(TOOLS_QUERY);var group=TOOLS_GROUP==='all'||TOOLS_RECOMMENDED.includes(x.name);return domain&&state&&search&&group});
 var pages=Math.max(1,Math.ceil(list.length/12));TOOLS_PAGE=Math.max(0,Math.min(TOOLS_PAGE,pages-1));
 var rows=list.slice(TOOLS_PAGE*12,TOOLS_PAGE*12+12).map(function(x){return '<div class="tool-card"><div><strong>'+esc(x.name)+'</strong> <span class="badge">'+(x.domain==='sse'?t('dom_sse'):x.domain==='panel'?t('dom_panel'):t('dom_sdwan'))+'</span><span class="help">'+esc(((LANG==='es'||LANG==='mx')&&x.description_es)?x.description_es:x.description)+'</span></div><label class="switch" title="'+(x.disabled?t('tool_off'):t('tool_on'))+'"><input type="checkbox" '+(x.disabled?'':'checked')+' '+(canWrite?'onchange="toggleTool(\''+esc(x.name)+'\',this.checked)"':'disabled')+'><span class="slider"></span></label></div>'}).join('')||'<p class="help">'+t('tools_empty')+'</p>';
 q('#tools-list').innerHTML=rows;var count=q('#tools-count');if(count)count.textContent=list.length+' / '+TOOLS_ALL.length;
 q('#tools-pager').innerHTML='<button class="secondary" onclick="toolsPage('+(TOOLS_PAGE-1)+')" '+(TOOLS_PAGE===0?'disabled':'')+'>'+t('tools_prev')+'</button><span class="help">'+t('tools_page')+' '+(TOOLS_PAGE+1)+' / '+pages+'</span><button class="secondary" onclick="toolsPage('+(TOOLS_PAGE+1)+')" '+(TOOLS_PAGE>=pages-1?'disabled':'')+'>'+t('tools_next')+'</button>';
}
async function enableAllTools(){if(!confirm(t('tools_enable_all_confirm')))return;try{var r=await api('/api/tools/enable-all',{});notice(r.ok?t('tools_restart'):(r.error||'Error'),r.ok?'ok':'err');if(r.ok)await renderTools()}catch(e){notice(e.message,'err')}}
async function toggleTool(name,enabled){
 try{var r=await api('/api/tools/toggle',{name:name,enabled:enabled});notice(r.ok?((enabled?t('tool_on'):t('tool_off'))+' '+name):(r.error||'Error'),r.ok?'ok':'err');if(r.ok)await renderTools()}catch(e){notice(e.message,'err')}
}
async function showAgentPrompt(){
 try{var r=await api('/api/agent-prompt');if(!q('#agent-dlg'))q('#app').innerHTML+=agentDialogHtml();q('#agent-text').textContent=r.prompt;var d=q('#agent-dlg');d.showModal?d.showModal():d.setAttribute('open','')}catch(e){notice(e.message,'err')}
}
function agentDialogHtml(){return '<dialog id="agent-dlg" style="max-width:780px;width:calc(100% - 30px)"><h3>'+t('agent_title')+'</h3><p class="help">'+t('agent_desc')+'</p><pre id="agent-text" style="max-height:52vh;overflow:auto;background:#071f2b;color:#f1ffff;border:1px solid var(--line);border-radius:4px;padding:12px;font-size:11px;white-space:pre-wrap"></pre><div class="actions"><button onclick="copyAgent()">'+t('copy')+'</button><button class="secondary" onclick="closeAgent()">'+t('custom_cancel')+'</button></div></dialog>'}
function copyAgent(){var el=q('#agent-text');if(el&&navigator.clipboard){navigator.clipboard.writeText(el.textContent)}notice(t('copied'),'ok')}
function closeAgent(){var d=q('#agent-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
var DBG_TIMER=null,DBG_PAUSED=false,DBG_Q='';
async function renderDebug(){
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('dbg_title')+'</h2><p class="help">'+t('dbg_desc')+'</p><div class="actions" style="align-items:center"><input id="dbg-q" placeholder="'+t('dbg_filter')+'" oninput="dbgApplyFilter()" style="max-width:300px;min-height:34px;margin-top:0"><button class="secondary" onclick="dbgTogglePause()" id="dbg-pause">'+t('dbg_pause')+'</button><button class="secondary" onclick="dbgRefresh()">'+t('dbg_refresh')+'</button><button class="secondary" onclick="dbgExport()">'+t('dbg_export')+'</button><button class="danger" onclick="dbgClear()">'+t('dbg_clear')+'</button></div><div id="host-monitor" class="monitor-grid" aria-live="polite"></div><details class="group"><summary>'+((LANG==='es'||LANG==='mx')?'Preparación de auditoría':'Audit readiness')+'</summary><p class="help">'+((LANG==='es'||LANG==='mx')?'Captura SHA-256 del archivo activo (hasta 64 MiB). No incluye archivos rotados; no está firmada ni anclada externamente y no demuestra no repudio. Conserva el JSON en un sistema independiente.':'SHA-256 snapshot of the active file (up to 64 MiB). Rotated files are excluded; the snapshot is unsigned, not externally anchored and does not establish non-repudiation. Keep the JSON in an independent system.')+'</p><div class="actions">'+(ME&&ME.role==='admin'?'<button class="secondary" onclick="downloadAuditSnapshot()">'+((LANG==='es'||LANG==='mx')?'Descargar huella JSON':'Download JSON digest')+'</button>':'')+'</div><p class="help">NIST SP 800-92 · NIST SP 800-53 AU-2 / AU-3 / AU-9 / AU-10 / AU-11</p></details><div class="actions"><button class="secondary" onclick="downloadAudit(\'csv\')">CSV</button><button class="secondary" onclick="downloadAudit(\'xlsx\')">Excel</button></div><p class="help">Informes para administradores: hasta 500 eventos disponibles. Los campos no registrados se muestran vacíos; no se infiere el usuario.</p><details class="group"><summary>'+t('diag_title')+'</summary><p class="help">'+t('diag_help')+'</p><div class="actions"><button class="secondary" onclick="runDiagnostic(\'uptime\')">Carga / uptime</button><button class="secondary" onclick="runDiagnostic(\'memory\')">'+t('diag_memory')+'</button><button class="secondary" onclick="runDiagnostic(\'disk\')">'+t('diag_disk')+'</button><button class="secondary" onclick="runDiagnostic(\'status\')">'+t('diag_status')+'</button><button class="secondary" onclick="runDiagnostic(\'journal_mcp\')">'+t('diag_mcp_log')+'</button><button class="secondary" onclick="runDiagnostic(\'journal_admin\')">'+t('diag_admin_log')+'</button></div><pre id="diagnostic-output" class="diagnostic-commands" aria-live="polite"></pre></details><p class="help">'+t('diag_api_help')+'</p><div id="dbg-table"><p class="help">'+t('checking')+'</p></div></section>';
 await dbgRefresh();
 if(!DBG_TIMER)DBG_TIMER=setInterval(function(){if(!DBG_PAUSED)dbgRefresh()},2500);
}
var DIAG_ABORT=null;
function dbgStop(){if(DIAG_ABORT){DIAG_ABORT.abort();DIAG_ABORT=null}if(DBG_TIMER){clearInterval(DBG_TIMER);DBG_TIMER=null}}
function dbgApplyFilter(){DBG_Q=(q('#dbg-q')||{}).value||'';dbgRefresh()}
function dbgTogglePause(){DBG_PAUSED=!DBG_PAUSED;var b=q('#dbg-pause');if(b)b.textContent=DBG_PAUSED?t('dbg_resume'):t('dbg_pause')}
async function dbgRefresh(){
 try{
  var r=await api('/api/debug/events?limit=500&q='+encodeURIComponent(DBG_Q));
  if(ME&&ME.role==='admin')refreshHostMonitor();
  var rows=(r.events||[]).map(function(e){return '<tr><td class="mono" style="white-space:nowrap">'+esc(String(e.ts_iso||'').replace('T',' ').slice(0,19))+'</td><td><span class="badge">'+(e.source==='mcp-tool'?t('dbg_tool'):t('dbg_api'))+'</span></td><td class="mono">'+esc(e.tool?e.tool+' · '+e.action:e.action)+'</td><td class="mono">'+esc(e.target||'')+'</td><td class="mono">'+esc(e.event_id||'—')+'</td><td>'+esc(e.user||'No disponible')+'</td><td>'+esc(e.result||'')+'</td><td style="white-space:nowrap">'+(typeof e.latency==='number'?e.latency.toFixed(2)+'s':'—')+'</td></tr>'}).join('')||'<tr><td colspan="8" class="help">'+t('dbg_empty')+'</td></tr>';
  q('#dbg-table').innerHTML='<table class="diff"><tr><th>'+t('dbg_time')+'</th><th>'+t('dbg_source')+'</th><th>'+t('dbg_action')+'</th><th>'+t('dbg_target')+'</th><th>Event ID</th><th>'+t('diag_user')+'</th><th>'+t('dbg_result')+'</th><th>'+t('dbg_lat')+'</th></tr>'+rows+'</table>';
 }catch(e){notice(e.message,'err')}
}

var HOST_MONITOR_BUSY=false;
function formatBytes(value){if(value===null||value===undefined)return 'No disponible';return (value/1073741824).toFixed(2)+' GiB'}
function meterCard(label,value,detail){
 var known=typeof value==='number'&&Number.isFinite(value),pct=known?Math.max(0,Math.min(100,value)):0;
 return '<div class="monitor-card"><strong>'+esc(label)+'</strong><div class="monitor-value">'+(known?pct.toFixed(1)+'%':'—')+'</div>'+(known?'<meter min="0" max="100" value="'+pct+'">'+pct+'%</meter>':'')+'<small>'+esc(detail)+'</small></div>';
}
async function refreshHostMonitor(){
 if(HOST_MONITOR_BUSY)return;HOST_MONITOR_BUSY=true;
 try{
  var r=await api('/api/monitor/host');if(r.error)throw Error(r.error);
  var cpu=r.cpu||{},mem=r.memory||{},disk=r.disk||{},activity=r.activity||{},os=r.os||{};
  var node=q('#host-monitor');if(!node||CURTAB!=='debug')return;
  node.innerHTML=meterCard('CPU',cpu.used_percent,(cpu.cores||'—')+' núcleos · uso entre muestras')+
   meterCard('RAM',mem.used_percent,formatBytes(mem.used_bytes)+' / '+formatBytes(mem.total_bytes))+
   meterCard('Disco',disk.used_percent,formatBytes(disk.used_bytes)+' / '+formatBytes(disk.total_bytes)+' · sistema de archivos del servicio')+
   '<div class="monitor-card"><strong>Sistema</strong><div>'+esc(os.system||'No disponible')+' '+esc(os.release||'')+'</div><small>'+esc(os.architecture||'')+' · auditoría: '+esc(formatBytes(r.audit_log_bytes))+'</small></div>'+
   '<div class="monitor-card"><strong>Eventos MCP · último minuto</strong><div class="monitor-value">'+esc(activity.observed_audit_events_last_minute==null?'—':activity.observed_audit_events_last_minute)+'</div>'+(typeof activity.observed_audit_events_last_minute==='number'?'<meter min="0" max="500" value="'+Math.max(0,Math.min(500,activity.observed_audit_events_last_minute))+'"></meter>':'')+'<small>Escala: hasta 500 registros observables, no capacidad ni solicitudes simultáneas. Concurrencia: no disponible.</small></div>';
 }catch(e){var node=q('#host-monitor');if(node)node.textContent='Métricas no disponibles: '+e.message}
 finally{HOST_MONITOR_BUSY=false}
}
async function runDiagnostic(command){
 var output=q('#diagnostic-output');if(!output)return;
 if(DIAG_ABORT)DIAG_ABORT.abort();var controller=new AbortController();DIAG_ABORT=controller;output.textContent=t('diag_running')+'\n';
 try{
  var response=await fetch('/api/diagnostics/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:command}),signal:controller.signal});
  if(!response.ok)throw Error('HTTP '+response.status);
  if(!response.body||!response.body.getReader){output.textContent+=await response.text();return}
  var reader=response.body.getReader(),decoder=new TextDecoder();
  while(true){var part=await reader.read();if(part.done)break;output.textContent+=decoder.decode(part.value,{stream:true});output.scrollTop=output.scrollHeight}
  output.textContent+=decoder.decode();
 }catch(e){if(e.name!=='AbortError')output.textContent+='\n'+e.message}
 finally{if(DIAG_ABORT===controller)DIAG_ABORT=null}
}
async function downloadAuditSnapshot(){
 try{var response=await fetch('/api/audit/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});var r=await response.json();if(!response.ok||!r.ok)throw Error(r.error||('HTTP '+response.status));var blob=new Blob([JSON.stringify(r.snapshot,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ec-mcp-audit-snapshot.json';a.click();URL.revokeObjectURL(a.href);notice((LANG==='es'||LANG==='mx')?'Huella creada; guárdala fuera del servidor.':'Digest created; store it outside the server.','ok')}catch(e){notice(e.message,'err')}
}
async function downloadAudit(format){
 try{var response=await fetch('/api/audit/report?format='+encodeURIComponent(format));if(!response.ok)throw Error('HTTP '+response.status);var blob=await response.blob();var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ec-mcp-auditoria.'+format;a.click();URL.revokeObjectURL(a.href)}
 catch(e){notice(e.message,'err')}
}

async function dbgExport(){
 try{
  var r=await fetch('/api/debug/export');
  var blob=await r.blob();
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ec-mcp-debug.jsonl';a.click();URL.revokeObjectURL(a.href);
  notice(t('dbg_exported'),'ok');
 }catch(e){notice(e.message,'err')}
}
async function dbgClear(){
 if(!confirm(t('dbg_clear_confirm')))return;
 try{var r=await api('/api/debug/clear',{});notice(r.message||r.error,r.ok?'ok':'err');await dbgRefresh()}catch(e){notice(e.message,'err')}
}

async function openBackups(){if(!q('#bak-dlg'))q('#app').innerHTML+=backupsDialogHtml();var d=q('#bak-dlg');await loadBackups();d.showModal?d.showModal():d.setAttribute('open','')}
function closeBackups(){var d=q('#bak-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
function backupsDialogHtml(){return '<dialog id="bak-dlg" style="max-width:760px;width:calc(100% - 30px)"><h3>'+t('bak_title')+'</h3><p class="help">'+t('bak_desc')+'</p><div class="actions"><button onclick="createBackup()">'+t('bak_create')+'</button><button class="secondary" onclick="closeBackups()">'+t('custom_cancel')+'</button></div><div id="bak-list"><p class="help">'+t('checking')+'</p></div></dialog>'}
async function loadBackups(){
 try{
  var r=await api('/api/backups');
  var rows=(r.backups||[]).map(function(b){return '<div class="orch"><span class="orch-actions"><button class="danger" onclick="restoreBackup(\''+esc(b.name)+'\')">'+t('bak_restore')+'</button>'+(ME&&ME.role==='admin'?'<button class="danger" data-name="'+esc(b.name)+'" onclick="deleteBackup(this.dataset.name)">'+((LANG==='es'||LANG==='mx')?'Eliminar':'Delete')+'</button>':'')+'</span><strong>'+esc(b.name)+'</strong> <span class="badge">'+esc(b.label||'')+'</span><br><span class="help">env: '+(b.env_changed&&b.env_changed.length?b.env_changed.slice(0,10).map(esc).join(', '):'—')+' · registro: '+(b.registry_changed&&b.registry_changed.length?b.registry_changed.map(esc).join(', '):'—')+'</span></div>'}).join('')||'<p class="help">'+t('bak_empty')+'</p>';
  q('#bak-list').innerHTML=rows;
 }catch(e){notice(e.message,'err')}
}
async function deleteBackup(name){if(!confirm(((LANG==='es'||LANG==='mx')?'¿Eliminar definitivamente el backup ':'Permanently delete backup ')+name+'?'))return;try{var r=await api('/api/backups/delete',{name:name});notice(r.message||r.error,r.ok?'ok':'err');await loadBackups()}catch(e){notice(e.message,'err')}}
async function createBackup(){try{var r=await api('/api/backups/create',{});notice(r.message||r.error,r.ok?'ok':'err');await loadBackups()}catch(e){notice(e.message,'err')}}
async function restoreBackup(name){
 if(!confirm(t('bak_restore_confirm')+' '+name+'?'))return;
 try{var r=await api('/api/backups/restore',{name:name});notice(r.message||r.error,r.ok?'ok':'err');if(r.ok){STATE=await api('/api/state');CONFIG=await api('/api/config');await loadBackups();showTab(CURTAB)}}catch(e){notice(e.message,'err')}
}
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
 var stepOrder={};(CONFIG.steps||[]).forEach(function(s,i){stepOrder[s.id]=i});var gnames=Object.keys(groups).sort(function(a,b){var fa=groups[a][0],fb=groups[b][0];return (stepOrder[fa.step]??99)-(stepOrder[fb.step]??99)||a.localeCompare(b)});var html=gnames.map(function(name){return '<details class="group"><summary><h3>'+esc(name)+'<span class="count">'+groups[name].length+'</span></h3></summary><div class="grid">'+groups[name].map(fieldHtml).join('')+'</div></details>'}).join('');
 q('#workspace').innerHTML='<section class="panel"><h2>'+t('h2_config')+'</h2><p>'+t('saved_in')+'<span class="mono">'+esc(CONFIG.env_file)+'</span>. '+t('secrets_note')+'</p>'+targetsNavHtml()+html+blobsInfoHtml()+'<div class="actions"><button onclick="saveConfig()">'+t('btn_save_vars')+'</button><button class="secondary" onclick="restartServices()">'+t('btn_save_restart')+'</button></div></section>';
 CONFIG.fields.forEach(function(f){var el=q('#cfg-'+f.key);if(el&&!f.secret)el.value=f.value});
}
function collectConfig(){var values={},clear=[];CONFIG.fields.forEach(function(f){var el=q('#cfg-'+f.key);if(!el)return;if(!f.secret||el.value!=='')values[f.key]=el.value;var c=document.querySelector('[data-clear=\"'+f.key+'\"]');if(c&&c.checked)clear.push(f.key)});return {values:values,clear_secrets:clear}}
async function saveConfig(restart){
 try{var r=await api('/api/config',collectConfig());notice(r.message||r.error,r.ok?'ok':'err');if(!r.ok)return;CONFIG=await api('/api/config');if(restart)await doRestart();else renderConfig()}catch(e){notice(e.message,'err')}
}
function restartDialogHtml(){
 var orchs=(STATE&&STATE.orchestrators)||[],sses=(STATE&&STATE.sse_platforms)||[];
 var defO=((orchs.find(function(o){return o.default})||orchs.find(function(o){return o.active})||{}).name)||'';
 var defS=((sses.find(function(o){return o.default})||sses.find(function(o){return o.active})||{}).name)||'';
 var oradio='<label class=\"clear\"><input type=\"radio\" name=\"rst-orch\" value=\"\"'+(defO?'':' checked')+'> —</label>'+orchs.map(function(o){return '<label class=\"clear\"><input type=\"radio\" name=\"rst-orch\" value=\"'+esc(o.name)+'\"'+(o.name===defO?' checked':'')+'> '+esc(o.name)+'</label>'}).join('');
 var sradio='<label class=\"clear\"><input type=\"radio\" name=\"rst-sse\" value=\"\"'+(defS?'':' checked')+'> —</label>'+sses.map(function(o){return '<label class=\"clear\"><input type=\"radio\" name=\"rst-sse\" value=\"'+esc(o.name)+'\"'+(o.name===defS?' checked':'')+'> '+esc(o.name)+'</label>'}).join('');
 return '<dialog id=\"restart-dlg\" style=\"max-width:560px;width:calc(100% - 30px)\"><h3>'+t('btn_save_restart')+'</h3><p class=\"help\">'+t('targets_h')+'</p><div class=\"group\"><h3>'+t('h2_orch')+'</h3>'+oradio+'</div><div class=\"group\"><h3>'+t('h2_sse')+'</h3>'+sradio+'</div><div class=\"actions\"><button onclick=\"submitRestart()\">'+t('btn_save_restart_short')+'</button><button class=\"secondary\" onclick=\"closeRestart()\">'+t('custom_cancel')+'</button></div></dialog>';
}
function openRestart(){if(!q('#restart-dlg'))q('#app').innerHTML+=restartDialogHtml();var d=q('#restart-dlg');d.showModal?d.showModal():d.setAttribute('open','')}
function closeRestart(){var d=q('#restart-dlg');if(d){d.close?d.close():d.removeAttribute('open')}}
async function restartServices(){openRestart()}
async function submitRestart(){
 var orch=(document.querySelector('input[name=\"rst-orch\"]:checked')||{value:''}).value||'';
 var sse=(document.querySelector('input[name=\"rst-sse\"]:checked')||{value:''}).value||'';
 closeRestart();
 try{
  var r=await api('/api/config',collectConfig());notice(r.message||r.error,r.ok?'ok':'err');if(!r.ok)return;
  if(orch){var a=await api('/api/apply',{name:orch,kind:'orchestrator'});notice(a.message||a.error,a.ok?'ok':'err');if(!a.ok)return}
  if(sse){var b=await api('/api/apply',{name:sse,kind:'sse'});notice(b.message||b.error,b.ok?'ok':'err');if(!b.ok)return}
  CONFIG=await api('/api/config');STATE=await api('/api/state');renderConfig();
  await doRestart();
 }catch(e){notice(e.message,'err')}
}
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
async function boot(){
 applySavedTheme();
 try{var s=await api('/api/state');if(s&&s.session){ME={user:s.session.user,role:s.session.role};AUTHED=true;renderShell();await loadAll();return}}catch(e){}
 renderLogin();
}
boot();
</script></body></html>"""
