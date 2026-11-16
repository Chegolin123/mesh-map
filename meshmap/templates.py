PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>mesh-map — живая карта сети</title>
<style>
  :root{
    --bg:#070a0e; --panel:#0c1218; --panel2:#0a0f14; --line:#1a2531;
    --text:#e6edf3; --muted:#7d8b99; --green:#3ddc97; --amber:#f5a524;
    --violet:#8b7cff; --red:#ff6b6b; --blue:#57a6ff;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; color:var(--text); background:
      radial-gradient(1100px 620px at 18% -12%, #101c27 0%, transparent 60%),
      radial-gradient(900px 520px at 100% 0%, #12151f 0%, transparent 55%),
      var(--bg);
    font:14px/1.45 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .mono{font-family:"JetBrains Mono","Cascadia Mono",Consolas,ui-monospace,monospace}
  header{
    display:flex; align-items:center; justify-content:space-between; gap:16px;
    padding:16px 26px; border-bottom:1px solid var(--line);
    position:sticky; top:0; z-index:10;
    background:rgba(7,10,14,.78); backdrop-filter:blur(10px);
  }
  .brand{display:flex; align-items:center; gap:11px; font-weight:650; letter-spacing:.2px}
  .brand b{font-size:16px}
  .brand span.version{font-size:11px; color:var(--muted); border:1px solid var(--line);
    border-radius:99px; padding:1px 7px; margin-left:2px}
  .pulse{width:9px;height:9px;border-radius:50%;background:var(--green);
    box-shadow:0 0 0 0 rgba(61,220,151,.55); animation:pulse 2s infinite}
  @keyframes pulse{
    0%{box-shadow:0 0 0 0 rgba(61,220,151,.5)}
    70%{box-shadow:0 0 0 9px rgba(61,220,151,0)}
    100%{box-shadow:0 0 0 0 rgba(61,220,151,0)}
  }
  .head-right{display:flex; align-items:center; gap:10px; font-size:12px; color:var(--muted)}
  .pill{border:1px solid var(--line); background:var(--panel); border-radius:99px;
    padding:3px 10px; color:var(--text); font-size:12px}
  .pill.err{border-color:#5a2323; color:#ffb4b4; background:#1a0f12}
  .live{display:flex; align-items:center; gap:6px; color:var(--green); font-size:12px}
  .live.down{color:var(--red)}
  .live i{width:7px;height:7px;border-radius:50%;background:currentColor;display:block}

  main{max-width:1660px; margin:0 auto; padding:20px 26px 28px;
    display:grid; grid-template-columns:minmax(0,1fr) 352px; gap:18px}
  .stage-wrap{display:flex; flex-direction:column; gap:14px; min-width:0}
  .stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:10px}
  .stat{background:linear-gradient(180deg,#0d141c,#0a1015); border:1px solid var(--line);
    border-radius:13px; padding:10px 13px}
  .stat .k{font-size:10.5px; letter-spacing:.9px; text-transform:uppercase; color:var(--muted)}
  .stat .v{font-size:22px; font-weight:700; margin-top:2px}
  .stat .v.green{color:var(--green)} .stat .v.amber{color:var(--amber)}
  .stage{position:relative; border:1px solid var(--line); border-radius:18px; overflow:hidden;
    background:#080c10; box-shadow:0 18px 50px rgba(0,0,0,.45)}
  .stage svg{display:block; width:100%; height:auto; animation:fade .35s ease}
  @keyframes fade{from{opacity:.45}to{opacity:1}}
  .placeholder{position:absolute; inset:0; display:grid; place-items:center; color:var(--muted)}

  aside{display:flex; flex-direction:column; gap:14px; min-width:0}
  .panel{background:linear-gradient(180deg,#0c1218,#0a0f14); border:1px solid var(--line);
    border-radius:16px; overflow:hidden}
  .panel h2{margin:0; padding:12px 15px; font-size:11px; letter-spacing:1px;
    text-transform:uppercase; color:var(--muted); border-bottom:1px solid var(--line);
    display:flex; justify-content:space-between; align-items:center}
  .panel h2 b{color:var(--text); font-size:11px}
  ul{list-style:none; margin:0; padding:6px}
  .node-item{display:flex; align-items:center; gap:10px; padding:8px 9px; border-radius:10px}
  .node-item:hover{background:#101820}
  .node-item .led{width:7px;height:7px;border-radius:50%;background:var(--green); flex:none;
    box-shadow:0 0 8px rgba(61,220,151,.7)}
  .node-item.off .led{background:#4b5764; box-shadow:none}
  .node-item.off .nname{color:#7f8c99}
  .nname{font-size:13px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
  .nos{font-size:11px; color:var(--muted)}
  .tag{margin-left:auto; font-size:9.5px; letter-spacing:.6px; color:#bdb2ff;
    border:1px solid #3b2f7a; background:#191434; border-radius:6px; padding:1px 6px}

  .ev{display:grid; grid-template-columns:52px 1fr; gap:8px; padding:7px 9px;
    border-left:2px solid transparent; border-radius:8px; align-items:baseline}
  .ev:hover{background:#101820}
  .ev .t{font-size:10.5px; color:var(--muted)}
  .ev .m{font-size:12.5px; color:#c9d5e1}
  .ev.info{border-left-color:var(--blue)}
  .ev.node{border-left-color:var(--green)}
  .ev.path{border-left-color:var(--amber)}
  .ev.latency{border-left-color:var(--violet)}
  .ev.warn{border-left-color:var(--red)}
  .ev.warn .m{color:#ffc4c4}
  .empty{padding:14px; color:var(--muted); font-size:12px}

  .node-item{cursor:pointer}

  .drawer-backdrop{position:fixed; inset:0; background:rgba(3,6,9,.55); backdrop-filter:blur(3px);
    opacity:0; pointer-events:none; transition:opacity .2s; z-index:20}
  .drawer-backdrop.open{opacity:1; pointer-events:auto}
  .drawer{position:fixed; top:0; right:0; height:100%; width:min(430px,94vw); z-index:21;
    background:linear-gradient(180deg,#0c1218,#090d12); border-left:1px solid var(--line);
    transform:translateX(102%); transition:transform .24s cubic-bezier(.22,.61,.36,1);
    display:flex; flex-direction:column; box-shadow:-30px 0 70px rgba(0,0,0,.55)}
  .drawer.open{transform:translateX(0)}
  .dr-head{display:flex; align-items:center; justify-content:space-between; gap:10px;
    padding:15px 18px; border-bottom:1px solid var(--line)}
  .dr-title{display:flex; align-items:center; gap:9px; font-size:15px; min-width:0}
  .dr-title b{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
  .dr-close{background:none; border:1px solid var(--line); color:var(--muted); border-radius:8px;
    width:28px; height:28px; cursor:pointer; flex:none; font-size:13px}
  .dr-close:hover{color:var(--text); border-color:#33465a}
  .dr-body{padding:16px 18px; overflow:auto; display:flex; flex-direction:column; gap:16px}
  .kv{display:grid; grid-template-columns:1fr 1fr; gap:9px}
  .kv>div{background:#0a1015; border:1px solid var(--line); border-radius:10px; padding:8px 10px; min-width:0}
  .kv span{display:block; font-size:10px; letter-spacing:.7px; text-transform:uppercase; color:var(--muted)}
  .kv b{font-size:12.5px; font-weight:600; word-break:break-word}
  .actions{display:flex; flex-direction:column; gap:8px}
  .btn{display:flex; align-items:center; justify-content:center; gap:8px; padding:10px 14px;
    border-radius:10px; border:1px solid var(--line); background:#0f1720; color:var(--text);
    font:inherit; font-size:13px; cursor:pointer; text-decoration:none}
  .btn:hover{border-color:#33465a; background:#12202c}
  .btn.primary{background:linear-gradient(180deg,#16352a,#102a21); border-color:#2c6a51; color:#9ff3cf}
  .btn.primary:hover{background:linear-gradient(180deg,#1a4032,#123026)}
  .btn:disabled{opacity:.45; cursor:not-allowed}
  .btn.ghost{background:transparent; color:var(--muted)}
  .hint{font-size:11.5px; color:var(--muted); line-height:1.45}
  .hint code{background:#0a1015; border:1px solid var(--line); border-radius:5px; padding:1px 5px; font-size:11px}
  .links{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:6px}
  .links li{display:flex; justify-content:space-between; gap:8px; font-size:12.5px;
    padding:7px 9px; border-radius:8px; background:#0a1015; border:1px solid var(--line)}
  .links .p{font-size:11px; color:var(--muted)}
  .links .p.direct{color:var(--green)} .links .p.relay{color:var(--amber)}
  h3.sec{margin:0; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--muted)}
  .toast{position:fixed; left:50%; bottom:26px; transform:translate(-50%,20px); z-index:40;
    background:#101a23; border:1px solid #2b4256; color:var(--text); padding:10px 16px;
    border-radius:11px; font-size:13px; opacity:0; pointer-events:none; transition:.2s}
  .toast.show{opacity:1; transform:translate(-50%,0)}

  footer{max-width:1660px; margin:0 auto; padding:0 26px 26px; display:flex; gap:16px;
    align-items:center; justify-content:space-between; color:var(--muted); font-size:12px}
  footer nav{display:flex; gap:14px}
  footer a{color:var(--muted); text-decoration:none; border-bottom:1px dotted transparent}
  footer a:hover{color:var(--text); border-bottom-color:var(--line)}

  @media (max-width:1180px){
    main{grid-template-columns:1fr}
    aside{flex-direction:row; flex-wrap:wrap}
    aside .panel{flex:1 1 320px}
  }
  @media (max-width:640px){
    main,header,footer{padding-left:14px; padding-right:14px}
    .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
    aside{flex-direction:column}
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="pulse" id="pulse"></span>
    <b>mesh-map</b>
    <span class="version">0.1.0</span>
  </div>
  <div class="head-right">
    <span class="pill" id="provider">—</span>
    <span class="mono" id="updated">—</span>
    <span class="live" id="live"><i></i>live</span>
  </div>
</header>

<main>
  <section class="stage-wrap">
    <div class="stats">
      <div class="stat"><div class="k">узлы</div><div class="v" id="sNodes">—</div></div>
      <div class="stat"><div class="k">онлайн</div><div class="v green" id="sOnline">—</div></div>
      <div class="stat"><div class="k">прямых путей</div><div class="v green" id="sDirect">—</div></div>
      <div class="stat"><div class="k">через DERP</div><div class="v amber" id="sRelay">—</div></div>
      <div class="stat"><div class="k">средний RTT</div><div class="v" id="sRtt">—</div></div>
    </div>
    <div class="stage" id="stage"><div class="placeholder">собираю топологию…</div></div>
  </section>

  <aside>
    <div class="panel">
      <h2>Узлы <b id="nodeCount"></b></h2>
      <ul id="nodeList"></ul>
    </div>
    <div class="panel">
      <h2>События <b id="eventCount"></b></h2>
      <ul id="eventList"></ul>
    </div>
  </aside>
</main>

<footer>
  <span>mesh-map · self-hosted tailnet observability</span>
  <nav>
    <a href="/graph.svg">graph.svg</a>
    <a href="/badge.svg">badge.svg</a>
    <a href="/filezilla/sites.xml">FileZilla sites</a>
    <a href="/metrics">metrics</a>
    <a href="/api/history">history</a>
  </nav>
</footer>

<div class="drawer-backdrop" id="backdrop"></div>
<aside class="drawer" id="drawer" aria-hidden="true"></aside>
<div class="toast" id="toast"></div>

<script>
const stage = document.getElementById('stage');
const liveEl = document.getElementById('live');
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (ts) => new Date(ts * 1000).toLocaleTimeString('ru-RU', {hour12: false});

function render(d){
  if(!d.ready){
    stage.innerHTML = '<div class="placeholder">' +
      (d.error ? 'ошибка источника: ' + esc(d.error) : 'собираю топологию…') + '</div>';
    return;
  }
  if(d.svg){ stage.innerHTML = d.svg; }
  document.getElementById('provider').textContent = d.provider;
  document.getElementById('updated').textContent = fmt(d.ts);

  const s = d.summary || {};
  document.getElementById('sNodes').textContent = s.nodes ?? '—';
  document.getElementById('sOnline').textContent = s.online ?? '—';
  document.getElementById('sDirect').textContent = s.direct ?? '—';
  document.getElementById('sRelay').textContent = s.relay ?? '—';
  document.getElementById('sRtt').textContent = s.avg_rtt != null ? s.avg_rtt + ' мс' : '—';

  const nodes = (d.nodes || []).slice().sort((a,b) => (b.online - a.online) || a.hostname.localeCompare(b.hostname));
  document.getElementById('nodeCount').textContent = nodes.length;
  document.getElementById('nodeList').innerHTML = nodes.map(n => `
    <li class="node-item ${n.online ? '' : 'off'}" data-id="${esc(n.id)}">
      <span class="led"></span>
      <div style="min-width:0">
        <div class="nname">${esc(n.hostname)}</div>
        <div class="nos">${esc(n.os_label)}${(n.tags || []).filter(t => t !== 'exit-node').length ? ' · ' + n.tags.filter(t => t !== 'exit-node').map(esc).join(' · ') : ''}</div>
      </div>
      ${n.exit_node ? '<span class="tag">exit</span>' : ''}
    </li>`).join('');

  const events = d.events || [];
  document.getElementById('eventCount').textContent = events.length || '';
  document.getElementById('eventList').innerHTML = events.length
    ? events.map(e => `
      <li class="ev ${esc(e.kind)}">
        <span class="t mono">${fmt(e.ts)}</span>
        <span class="m">${esc(e.message)}</span>
      </li>`).join('')
    : '<li class="empty">пока тихо — сеть стабильна</li>';
}

const es = new EventSource('/api/stream');
es.onmessage = (ev) => {
  liveEl.classList.remove('down');
  render(JSON.parse(ev.data));
};
es.onerror = () => { liveEl.classList.add('down'); };

fetch('/api/state').then(r => r.json()).then(render).catch(() => {});

// ── карточка узла и файловый клиент ─────────────────────────────────────────
const DRAWER = document.getElementById('drawer');
const BACKDROP = document.getElementById('backdrop');
let currentId = null;
let fz = { installed: false, allow_launch: false, path: null, client: null, label: null, key: null };

fetch('/api/filezilla').then(r => r.json()).then(v => { fz = v; }).catch(() => {});

function toast(message){
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 2800);
}

async function copyText(text, okMessage){
  try{
    await navigator.clipboard.writeText(text);
    toast(okMessage || 'скопировано');
  }catch(e){
    toast('не удалось скопировать');
  }
}

function closeDrawer(){
  DRAWER.classList.remove('open');
  BACKDROP.classList.remove('open');
  DRAWER.setAttribute('aria-hidden', 'true');
  currentId = null;
}

function sshLine(ssh){
  if(!ssh) return 'не проверялся';
  if(ssh.open) return (ssh.banner || 'SSH') + ' · порт ' + ssh.port;
  return 'порт ' + ssh.port + ' закрыт';
}

function hint(d, fzReady, sftpReady){
  const name = fz.label || 'файловый клиент';
  if(d.node && d.node.self){
    return fz.key
      ? 'Это этот ПК: ' + name + ' откроет локальные диски по ключу, без пароля.'
      : 'Это этот ПК: локальные файлы — в проводнике. Для SFTP по ключу задай <code>MESHMAP_SSH_KEY</code>.';
  }
  if(d.demo) return 'Демо-узел: адрес синтетический, подключение не установится. Запусти с <code>--provider tailscale</code>, чтобы открывать реальные устройства.';
  if(!d.ssh || !d.ssh.open){
    if(d.node.online) return 'Узел в сети, но SSH-порт закрыт: на нём не запущен sshd. Windows: Параметры → Система → Дополнительные компоненты → OpenSSH Server, затем <code>Start-Service sshd</code> и правило фаервола на порт 22.';
    return 'Узел офлайн — открывать нечего. Включи Tailscale на устройстве и дождись, пока карта покажет его онлайн.';
  }
  if(!fz.installed) return 'FileZilla или WinSCP не найдены. WinSCP ставится одной командой: <code>winget install WinSCP</code>. Или импортируй <code>sites.xml</code> вручную.';
  if(!fz.allow_launch) return 'Запуск приложений выключен (<code>MESHMAP_ALLOW_LAUNCH=0</code>). Скопируй sftp-адрес и открой в ' + name + ' сам.';
  if(!sftpReady) return 'Узел не готов к SFTP.';
  if(fz.key && fz.client === 'winscp') return 'Откроется ' + name + ' по ключу — без пароля.';
  return 'Откроется ' + name + ' с готовым sftp:// — пароль введёшь в диалоге, в URL он не передаётся.';
}

async function openNode(id){
  currentId = id;
  const resp = await fetch('/api/nodes/' + encodeURIComponent(id));
  if(!resp.ok){ toast('узел не найден'); return; }
  const d = await resp.json();
  const n = d.node;
  const fzReady = fz.installed && fz.allow_launch;
  const sftpReady = d.sftp.available;

  DRAWER.innerHTML = `
    <div class="dr-head">
      <div class="dr-title">
        <span style="width:8px;height:8px;border-radius:50%;flex:none;background:${n.online ? 'var(--green)' : '#4b5764'};box-shadow:${n.online ? '0 0 8px var(--green)' : 'none'}"></span>
        <b>${esc(n.hostname)}</b>
        <span class="pill" style="font-size:11px">${esc(n.os_label)}</span>
        ${n.self ? '<span class="pill" style="font-size:11px">этот ПК</span>' : ''}
      </div>
      <button class="dr-close" data-close>✕</button>
    </div>
    <div class="dr-body">
      <div class="kv">
        <div><span>адрес</span><b class="mono">${esc(d.sftp.host)}</b></div>
        <div><span>SSH / SFTP</span><b>${esc(sshLine(d.ssh))}</b></div>
        <div><span>пользователь</span><b class="mono">${esc(d.sftp.user)}</b></div>
        <div><span>состояние</span><b>${n.online ? 'онлайн' : 'офлайн'}</b></div>
      </div>

      <div class="actions">
        <button class="btn primary" data-action="filezilla" ${fzReady && sftpReady && !(n.self && !fz.key) ? '' : 'disabled'}>Открыть в ${esc(fz.label || 'FileZilla')}</button>
        <button class="btn" data-action="copy-sftp" ${sftpReady ? '' : 'disabled'}>Скопировать sftp://</button>
        <button class="btn" data-action="copy-ssh">Скопировать ssh-команду</button>
        <a class="btn ghost" href="/api/nodes/${encodeURIComponent(n.id)}/site.xml">Скачать site entry (.xml)</a>
      </div>

      <div class="hint">${hint(d, fzReady, sftpReady)}</div>

      <h3 class="sec">Связи</h3>
      <ul class="links">${(d.links || []).map(l => `
        <li><span>${esc(l.hostname)}</span>
        <span class="p ${esc(l.path)}">${l.path === 'direct' ? 'прямой' : l.path === 'relay' ? 'DERP ' + esc(l.relay || '') : '—'}${l.rtt_ms != null ? ' · ' + Math.round(l.rtt_ms) + ' мс' : ''}</span></li>`).join('') || '<li><span>нет связей</span></li>'}</ul>

      <a class="btn ghost" href="/filezilla/sites.xml">Все узлы → Site Manager одной пачкой</a>
    </div>`;

  DRAWER.classList.add('open');
  BACKDROP.classList.add('open');
  DRAWER.setAttribute('aria-hidden', 'false');

  DRAWER.querySelector('[data-close]').onclick = closeDrawer;
  DRAWER.querySelector('[data-action="copy-sftp"]').onclick = () => copyText(d.sftp.url, 'sftp-адрес скопирован');
  DRAWER.querySelector('[data-action="copy-ssh"]').onclick = () => copyText(d.ssh_command, 'ssh-команда скопирована');

  const fzBtn = DRAWER.querySelector('[data-action="filezilla"]');
  fzBtn.onclick = async () => {
    fzBtn.disabled = true;
    const r = await fetch('/api/nodes/' + encodeURIComponent(n.id) + '/filezilla', { method: 'POST' });
    const j = await r.json().catch(() => ({}));
    fzBtn.disabled = false;
    if(j.ok){ toast((fz.label || 'Клиент') + ' запущен'); }
    else {
      toast(j.error || 'не удалось открыть');
      if(j.command){ copyText(j.command, 'команда скопирована — вставь в терминал'); }
    }
  };
}

document.getElementById('stage').addEventListener('click', (e) => {
  const nodeEl = e.target.closest ? e.target.closest('g.node') : null;
  if(nodeEl && nodeEl.dataset.id) openNode(nodeEl.dataset.id);
});

document.getElementById('nodeList').addEventListener('click', (e) => {
  const item = e.target.closest('.node-item');
  if(item && item.dataset.id) openNode(item.dataset.id);
});

BACKDROP.addEventListener('click', closeDrawer);
document.addEventListener('keydown', (e) => { if(e.key === 'Escape') closeDrawer(); });
</script>
</body>
</html>
"""
