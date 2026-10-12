const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ROW_FIELDS = {
  speed: { label: "Speed", value: (it) => (it.downloadSpeed > 0 ? fmtSpeed(it.downloadSpeed) : null) },
  upspeed: { label: "Up", value: (it) => (it.uploadSpeed > 0 ? fmtSpeed(it.uploadSpeed) : null) },
  eta: { label: "ETA", value: (it) => (it.eta != null ? fmtEta(it.eta) : null) },
  seeds: { label: "Seeds", value: (it) => String(it.seeds) },
  peers: { label: "Peers", value: (it) => String(it.connections) },
  size: { label: "Size", value: (it) => (it.totalLength ? fmtBytes(it.totalLength) : null) },
  ratio: { label: "Ratio", value: (it) => (Number(it.ratio) || 0).toFixed(2) },
  category: { label: "Category", value: (it) => (it.category ? esc(it.category) : null) },
  tags: { label: "Tags", value: (it) => ((it.tags || []).length ? esc(it.tags.join(", ")) : null) },
  addedAt: { label: "Added", value: (it) => (it.addedAt ? fmtDate(it.addedAt) : null) },
  savePath: { label: "Path", value: (it) => (it.dir ? esc(it.dir) : null) },
};
const DEFAULT_ROW_FIELDS = ["speed", "eta", "seeds", "peers", "size"];

const STATUS_FILTERS = ["all", "active", "downloading", "metadata", "queued", "paused", "complete", "error"];
const STATUS_CHIP = {
  downloading: ["accent", "downloading"],
  metadata: ["violet", "metadata"],
  queued: ["ink", "queued"],
  paused: ["amber", "paused"],
  complete: ["green", "completed"],
  seeding: ["green", "seeding"],
  error: ["red", "error"],
};
const SORT_KEYS = [
  { id: "addedAt", label: "Added" },
  { id: "name", label: "Name" },
  { id: "progress", label: "Progress" },
  { id: "speed", label: "Speed" },
  { id: "size", label: "Size" },
  { id: "eta", label: "ETA" },
  { id: "seeds", label: "Seeds" },
  { id: "peers", label: "Peers" },
  { id: "status", label: "Status" },
];

const state = {
  items: [],
  global: {},
  settings: null,
  categories: [],
  tags: [],
  views: [],
  presets: {},
  filters: { status: "all", category: "", tag: "", search: "" },
  sort: { key: "addedAt", dir: "desc" },
  rowFields: [...DEFAULT_ROW_FIELDS],
  selection: new Set(),
  detailGid: null,
  detail: null,
  detailTab: "general",
  connected: false,
  _sig: "",
  rowMap: new Map(),
};

async function api(path, method = "GET", body) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || JSON.stringify(j);
    } catch (e) {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function fmtBytes(n) {
  n = Number(n) || 0;
  if (n >= 1e12) return (n / 1e12).toFixed(2) + " TB";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + " GB";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + " MB";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + " KB";
  return n + " B";
}
function fmtSpeed(n) {
  return n > 0 ? fmtBytes(n) + "/s" : "\u2013";
}
function fmtEta(s) {
  if (s == null || s < 0) return "\u2013";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${sec}s`;
  return `${sec}s`;
}
function fmtDate(epoch) {
  if (!epoch) return "";
  return new Date(epoch * 1000).toLocaleString();
}

function toast(message, kind = "") {
  const div = document.createElement("div");
  div.className = "toast " + kind;
  div.textContent = message;
  $("#toasts").appendChild(div);
  setTimeout(() => div.remove(), 5000);
}

function statusChip(stateName) {
  const [cls, label] = STATUS_CHIP[stateName] || ["ink", stateName];
  return `<span class="chip ${cls}">${label}</span>`;
}

function ringHTML(it) {
  if (it.state === "complete") {
    return `<span class="dot-icon done" title="Completed"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg></span>`;
  }
  if (it.state === "error") {
    return `<span class="dot-icon err" title="Error">!</span>`;
  }
  if (it.state === "queued" || it.state === "paused") {
    return `<span class="dot-icon ${it.state}" title="${it.state}"><svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"></rect><rect x="14" y="5" width="4" height="14" rx="1"></rect></svg></span>`;
  }
  const pct = it.percent || 0;
  const C = 2 * Math.PI * 11;
  const off = C * (1 - pct / 100);
  const num = it.state === "metadata" ? "" : Math.round(pct);
  return `<span class="ring"><svg viewBox="0 0 24 24"><circle class="track" cx="12" cy="12" r="11"></circle><circle class="val" cx="12" cy="12" r="11" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"></circle></svg><span class="num">${num}</span></span>`;
}

function chipsHTML(it) {
  return state.rowFields
    .map((k) => {
      const def = ROW_FIELDS[k];
      if (!def) return "";
      const val = def.value(it);
      if (val == null || val === "") return "";
      return `<span class="chip"><span class="k">${def.label}</span><span class="v">${val}</span></span>`;
    })
    .join("");
}

function buildTask(it) {
  const el = document.createElement("article");
  el.className = "task s-" + it.state + (state.selection.has(it.gid) ? " selected" : "");
  el.dataset.gid = it.gid;
  const checked = state.selection.has(it.gid) ? "checked" : "";
  el.innerHTML = `
    <div class="task-row" role="button" tabindex="0" aria-expanded="false">
      <input type="checkbox" class="task-check" ${checked} aria-label="Select torrent">
      ${ringHTML(it)}
      <span class="task-title" title="${esc(it.name)}">${esc(it.name)}</span>
      <span class="task-meta">${it.totalLength ? fmtBytes(it.totalLength) : ""}</span>
      ${statusChip(it.state)}
      <span class="chev"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"></path></svg></span>
    </div>
    <div class="task-body"><div class="inner"><div class="pad">
      <div class="chip-row">${chipsHTML(it)}</div>
      <div class="chip-row">
        <button class="btn sm" data-act="toggle">${it.state === "paused" ? "Resume" : "Pause"}</button>
        <button class="btn sm" data-act="details">Details</button>
        <button class="btn sm" data-act="open">Open</button>
        <button class="btn sm" data-act="reveal">Reveal</button>
        <button class="btn sm btn-danger" data-act="remove">Remove</button>
      </div>
      <div class="substeps"></div>
    </div></div></div>`;
  el._refs = {
    ring: el.querySelector(".ring, .dot-icon"),
    status: el.querySelector(".chip.accent, .chip.violet, .chip.ink, .chip.amber, .chip.green, .chip.red"),
    meta: el.querySelector(".task-meta"),
    chips: el.querySelector(".chip-row"),
    toggle: el.querySelector('[data-act="toggle"]'),
  };
  return el;
}

function updateTask(el, it) {
  el.className = "task s-" + it.state + (state.selection.has(it.gid) ? " selected" : "") + (el.classList.contains("open") ? " open" : "");
  const r = el._refs || {};
  if (r.ring) {
    const fresh = document.createElement("span");
    fresh.innerHTML = ringHTML(it);
    r.ring.replaceWith(fresh.firstElementChild);
    r.ring = el.querySelector(".ring, .dot-icon");
  }
  if (r.status) {
    const fresh = document.createElement("span");
    fresh.innerHTML = statusChip(it.state);
    r.status.replaceWith(fresh.firstElementChild);
    r.status = el.querySelector(".chip.accent, .chip.violet, .chip.ink, .chip.amber, .chip.green, .chip.red");
  }
  if (r.meta) r.meta.textContent = it.totalLength ? fmtBytes(it.totalLength) : "";
  if (r.chips && el.classList.contains("open")) r.chips.innerHTML = chipsHTML(it);
  if (r.toggle) r.toggle.textContent = it.state === "paused" ? "Resume" : "Pause";
}

function visibleItems() {
  const f = state.filters;
  const q = f.search.toLowerCase();
  const items = state.items.filter((it) => {
    if (f.status === "active") {
      if (!["downloading", "metadata", "seeding"].includes(it.state)) return false;
    } else if (f.status !== "all" && it.state !== f.status) return false;
    if (f.category && it.category !== f.category) return false;
    if (f.tag && !(it.tags || []).includes(f.tag)) return false;
    if (q && !it.name.toLowerCase().includes(q)) return false;
    return true;
  });
  const key = state.sort.key, mul = state.sort.dir === "asc" ? 1 : -1;
  const fieldOf = (it) => {
    switch (key) {
      case "name": return it.name;
      case "progress": return it.percent;
      case "speed": return it.downloadSpeed;
      case "size": return it.totalLength;
      case "eta": return it.eta == null ? Infinity : it.eta;
      case "seeds": return it.seeds;
      case "peers": return it.connections;
      case "status": return it.state;
      default: return it.addedAt || 0;
    }
  };
  items.sort((a, b) => {
    const av = fieldOf(a), bv = fieldOf(b);
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * mul;
    return String(av).localeCompare(String(bv)) * mul;
  });
  return items;
}

function renderRows() {
  const items = visibleItems();
  const list = $("#tableBody");
  const sig = items.map((i) => i.gid).join(",") + "|" + JSON.stringify(state.sort) + "|" + JSON.stringify(state.filters) + "|" + state.rowFields.join(",");
  if (sig !== state._sig) {
    state._sig = sig;
    const frag = document.createDocumentFragment();
    state.rowMap.clear();
    for (const it of items) {
      const el = buildTask(it);
      state.rowMap.set(it.gid, el);
      frag.appendChild(el);
    }
    list.replaceChildren(frag);
  } else {
    const present = new Set(items.map((i) => i.gid));
    for (const it of items) {
      const el = state.rowMap.get(it.gid);
      if (el) updateTask(el, it);
    }
    for (const [gid, el] of state.rowMap) {
      if (!present.has(gid)) {
        el.remove();
        state.rowMap.delete(gid);
      }
    }
  }
  const empty = $("#emptyState");
  empty.classList.toggle("show", items.length === 0);
  empty.innerHTML = state.connected
    ? `<div class="loading"><span class="pixel-grid"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span><span class="shimmer" style="animation:none">No torrents — click Add to start</span></div>`
    : `<div class="loading"><span class="pixel-grid"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span><span class="shimmer">Connecting</span></div>`;
}

function renderStats() {
  const g = state.global || {};
  $("#stats").innerHTML =
    `<span class="stat">\u2193 <b>${fmtSpeed(g.downloadSpeed || 0)}</b></span>` +
    `<span class="stat">\u2191 <b>${fmtSpeed(g.uploadSpeed || 0)}</b></span>` +
    `<span class="stat">active <b>${g.numActive || 0}</b></span>` +
    `<span class="stat">queued <b>${g.numWaiting || 0}</b></span>` +
    `<span class="stat">done <b>${g.numStopped || 0}</b></span>`;
}

function renderStatusChips() {
  const items = state.items;
  const counts = {};
  for (const it of items) counts[it.state] = (counts[it.state] || 0) + 1;
  $("#statusChips").innerHTML = STATUS_FILTERS.map((s) => {
    const n = s === "all" ? items.length
      : s === "active" ? (counts.downloading || 0) + (counts.metadata || 0) + (counts.seeding || 0)
      : counts[s] || 0;
    const label = s === "all" ? "All" : s;
    const active = state.filters.status === s ? "active" : "";
    return `<button class="fchip ${active}" data-status="${s}">${label}<span class="n">${n}</span></button>`;
  }).join("");
}

function navItem(attrs, label, count) {
  return `<div class="nav-item" ${attrs}><span>${label}</span>${count != null ? `<span class="count">${count}</span>` : ""}</div>`;
}

function renderSidebar() {
  const items = state.items;
  $("#categoryFilters").innerHTML =
    navItem('data-category=""', "All categories", items.length) +
    state.categories.map((c) => navItem(`data-category="${esc(c.name)}"`, esc(c.name), items.filter((i) => i.category === c.name).length)).join("");
  $("#tagFilters").innerHTML =
    navItem('data-tag=""', "All tags", "") +
    state.tags.map((t) => navItem(`data-tag="${esc(t)}"`, esc(t), items.filter((i) => (i.tags || []).includes(t)).length)).join("");
  $("#viewList").innerHTML = state.views.length
    ? state.views.map((v, i) => navItem(`data-view="${i}"`, esc(v.name), "\u2192")).join("")
    : `<div class="hint" style="padding:4px 8px">No saved views</div>`;

  for (const id of ["categoryFilters", "tagFilters", "viewList"]) {
    const active = id === "categoryFilters" ? state.filters.category : id === "tagFilters" ? state.filters.tag : null;
    $$(".nav-item", $("#" + id)).forEach((el) => {
      const val = el.dataset.category ?? el.dataset.tag;
      if (active !== null && val === active) el.classList.add("active");
    });
  }
  attachGlide($("#categoryFilters"));
  attachGlide($("#tagFilters"));
  attachGlide($("#viewList"));
}

function attachGlide(nav) {
  if (!nav) return;
  let glide = nav.querySelector(":scope > .nav-glide");
  if (!glide) {
    glide = document.createElement("span");
    glide.className = "nav-glide";
    nav.prepend(glide);
  }
  if (nav.dataset.glideWired) return;
  nav.dataset.glideWired = "1";
  const move = (el) => {
    glide.style.top = el.offsetTop + "px";
    glide.style.height = el.offsetHeight + "px";
    glide.style.opacity = "1";
  };
  nav.addEventListener("mouseover", (e) => {
    const item = e.target.closest(".nav-item");
    if (item && !item.classList.contains("active")) move(item);
  });
  nav.addEventListener("mouseleave", () => (glide.style.opacity = "0"));
}

function renderSort() {
  const sel = $("#sortKey");
  sel.innerHTML = SORT_KEYS.map((k) => `<option value="${k.id}" ${state.sort.key === k.id ? "selected" : ""}>${k.label}</option>`).join("");
  $("#sortDir").textContent = state.sort.dir === "asc" ? "\u2191" : "\u2193";
}

function setConn(on) {
  state.connected = on;
  const dot = $("#connDot");
  dot.className = "conn " + (on ? "on" : "off");
  dot.title = on ? "connected" : "disconnected";
  if (!state.items.length) renderRows();
}

function onUpdate(data) {
  state.items = data.items || [];
  state.global = data.global || {};
  for (const ev of data.events || []) {
    if (ev.type === "completed") {
      toast("Completed: " + ev.name, "ok");
      if (state.settings?.notifications && "Notification" in window && Notification.permission === "granted") {
        new Notification("Download complete", { body: ev.name });
      }
    }
  }
  renderStats();
  renderStatusChips();
  renderSidebar();
  renderRows();
  if (state.detailGid) refreshDetail();
}

function connect() {
  const es = new EventSource("/api/events");
  es.onopen = () => setConn(true);
  es.onerror = () => setConn(false);
  es.onmessage = (e) => {
    try {
      onUpdate(JSON.parse(e.data));
    } catch (err) {
      console.error("stream update failed", err);
    }
  };
}

async function togglePause(gid) {
  const it = state.items.find((i) => i.gid === gid);
  const action = it && it.state === "paused" ? "resume" : "pause";
  await api(`/downloads/${gid}/${action}`, "POST");
}

async function removeGid(gid) {
  await api(`/downloads/${gid}/remove`, "POST");
  if (state.detailGid === gid) closeDrawer();
}

async function toggleTask(gid, task) {
  const row = task.querySelector(".task-row");
  const open = task.classList.toggle("open");
  row.setAttribute("aria-expanded", open ? "true" : "false");
  if (open && !task.dataset.loaded) {
    task.dataset.loaded = "1";
    const sub = task.querySelector(".substeps");
    try {
      const d = await api("/downloads/" + gid);
      const files = (d.files || []).slice(0, 10);
      sub.innerHTML = files.length
        ? files.map((f) => `<div class="substep"><span class="fp" title="${esc(f.path)}">${esc(f.name)}</span><div class="bar-mini"><i style="width:${f.percent}%"></i></div><span class="pct">${f.percent}%</span></div>`).join("")
        : `<div class="hint">No file details yet.</div>`;
    } catch (e) {
      sub.innerHTML = `<div class="hint">${esc(e.message)}</div>`;
    }
  }
}

async function taskAction(gid, act, task) {
  try {
    if (act === "toggle") await togglePause(gid);
    else if (act === "details") { openDetail(gid); return; }
    else if (act === "remove") { await removeGid(gid); return; }
    else if (act === "open" || act === "reveal") {
      const r = await api(`/actions/${act}`, "POST", { gid });
      toast(`${act}: ${r.path}`, "ok");
    }
  } catch (e) {
    toast(e.message, "err");
  }
}

function renderBatchBar() {
  let bar = $("#batchbar");
  const n = state.selection.size;
  if (!n) {
    if (bar) bar.remove();
    return;
  }
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "batchbar";
    bar.className = "batchbar";
    document.body.appendChild(bar);
  }
  bar.innerHTML =
    `<span><b>${n}</b> selected</span>` +
    `<button class="btn sm" data-batch="pause">Pause</button>` +
    `<button class="btn sm" data-batch="resume">Resume</button>` +
    `<button class="btn sm btn-danger" data-batch="remove">Remove</button>` +
    `<button class="btn sm" data-batch="clear">Clear</button>`;
}

async function batch(action) {
  const gids = [...state.selection];
  if (!gids.length) return;
  if (action === "clear") {
    state.selection.clear();
    state._sig = "";
    renderRows();
    renderBatchBar();
    return;
  }
  await api("/downloads/batch", "POST", { action, gids });
  if (action === "remove") state.selection.clear();
  renderBatchBar();
}

function openDetail(gid) {
  state.detailGid = gid;
  refreshDetail();
}
function closeDrawer() {
  state.detailGid = null;
  state.detail = null;
  $("#drawer").hidden = true;
}
async function refreshDetail() {
  if (!state.detailGid) return;
  try {
    state.detail = await api(`/downloads/${state.detailGid}`);
  } catch (e) {
    closeDrawer();
    return;
  }
  renderDrawer();
}

function renderDrawer() {
  const d = state.detail;
  if (!d) return;
  const dr = $("#drawer");
  dr.hidden = false;
  const tabs = ["general", "files", "peers", "trackers"];
  let body = "";
  if (state.detailTab === "general") {
    body = `<div class="kv">
      <div class="k">Status</div><div class="v">${statusChip(d.state)}</div>
      <div class="k">Progress</div><div class="v">${d.percent}%  (${fmtBytes(d.completedLength)} / ${fmtBytes(d.totalLength)})</div>
      <div class="k">Download</div><div class="v">${fmtSpeed(d.downloadSpeed)}</div>
      <div class="k">Upload</div><div class="v">${fmtSpeed(d.uploadSpeed)}</div>
      <div class="k">ETA</div><div class="v">${fmtEta(d.eta)}</div>
      <div class="k">Seeds / Peers</div><div class="v">${d.seeds} / ${d.connections}</div>
      <div class="k">Uploaded</div><div class="v">${fmtBytes(d.uploadLength)} (ratio ${(Number(d.ratio) || 0).toFixed(2)})</div>
      <div class="k">Files</div><div class="v">${d.filesCount}</div>
      <div class="k">Info hash</div><div class="v mono">${esc(d.infoHash || "\u2013")}</div>
      <div class="k">Save path</div><div class="v mono">${esc(d.dir || "")}</div>
      <div class="k">Category</div><div class="v">${esc(d.category || "\u2013")}</div>
      <div class="k">Tags</div><div class="v">${(d.tags || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("") || "\u2013"}</div>
      ${d.errorMessage ? `<div class="k">Error</div><div class="v" style="color:var(--red)">${esc(d.errorMessage)}</div>` : ""}
    </div>`;
  } else if (state.detailTab === "files") {
    body = `<div class="toolbar" style="margin-bottom:10px"><button class="btn sm" id="filesApply">Apply selection</button><label class="switch" style="margin:0"><input type="checkbox" id="filesSeq"> sequential</label></div>` +
      (d.files || []).map((f) => `<div class="file-row"><input type="checkbox" class="task-check fcheck" style="opacity:1" data-index="${f.index}" ${f.selected ? "checked" : ""}><span class="mono" title="${esc(f.path)}">${esc(f.name)}</span><div class="bar-mini"><i style="width:${f.percent}%"></i></div><span class="badge">${f.percent}%</span></div>`).join("");
  } else if (state.detailTab === "peers") {
    body = (d.peers || []).length
      ? d.peers.map((p) => `<div class="peer-row"><span class="mono">${esc(p.ipAddress)}:${esc(p.port)}</span><span class="badge">${esc((p.peerId || "").slice(0, 8))}</span><span class="badge">${fmtSpeed(p.downloadSpeed)}</span><span class="badge">${fmtSpeed(p.uploadSpeed)}</span></div>`).join("")
      : `<div class="hint">No connected peers.</div>`;
  } else {
    body = (d.trackers || []).length
      ? d.trackers.map((t) => `<div class="tracker-row"><span class="mono">${esc(t.uri)}</span><span class="badge">${esc(t.status)}</span><span class="badge">${esc(t.lastAnnounceResult || "")}</span></div>`).join("")
      : `<div class="hint">No trackers.</div>`;
  }

  dr.innerHTML = `
    <div class="drawer-head"><h3>${esc(d.name)}</h3><button class="btn sm" id="drawerClose">Close</button></div>
    <div class="toolbar">
      <button class="btn sm" data-dact="toggle">${d.state === "paused" ? "Resume" : "Pause"}</button>
      <button class="btn sm" data-dact="open">Open</button>
      <button class="btn sm" data-dact="reveal">Reveal</button>
      <button class="btn sm" data-dact="magnet">Copy magnet</button>
      <button class="btn sm btn-danger" data-dact="remove">Remove</button>
    </div>
    <div class="tabs">${tabs.map((t) => `<button class="tab ${state.detailTab === t ? "active" : ""}" data-tab="${t}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div>
    <div class="tab-body">${body}</div>`;

  $("#drawerClose").onclick = closeDrawer;
  $$(".tab", dr).forEach((b) => (b.onclick = () => { state.detailTab = b.dataset.tab; renderDrawer(); }));
  $$("[data-dact]", dr).forEach((b) => (b.onclick = () => drawerAction(b.dataset.dact)));
  const apply = $("#filesApply");
  if (apply) apply.onclick = applyFiles;
}

async function drawerAction(action) {
  const gid = state.detailGid;
  if (!gid) return;
  try {
    if (action === "toggle") await togglePause(gid);
    else if (action === "remove") { await removeGid(gid); return; }
    else if (action === "open" || action === "reveal") {
      const r = await api(`/actions/${action}`, "POST", { gid });
      toast(`${action}: ${r.path}`, "ok");
    } else if (action === "magnet") {
      if (state.detail.infoHash) {
        await navigator.clipboard.writeText(`magnet:?xt=urn:btih:${state.detail.infoHash}`);
        toast("Magnet copied", "ok");
      }
    }
    refreshDetail();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function applyFiles() {
  const gid = state.detailGid;
  const files = $$(".fcheck").map((c) => ({ index: Number(c.dataset.index), selected: c.checked }));
  const seq = $("#filesSeq").checked;
  try {
    const r = await api(`/downloads/${gid}/files`, "POST", { files, sequential: seq });
    toast(r.ok === false ? r.error : "Files updated", r.ok === false ? "err" : "ok");
    refreshDetail();
  } catch (e) {
    toast(e.message, "err");
  }
}

function showContextMenu(x, y, gid) {
  const menu = $("#ctxMenu");
  const it = state.items.find((i) => i.gid === gid) || {};
  menu.innerHTML = `
    <button data-cact="toggle">${it.state === "paused" ? "Resume" : "Pause"}</button>
    <button data-cact="details">Details</button>
    <button data-cact="open">Open file</button>
    <button data-cact="reveal">Reveal in folder</button>
    <button data-cact="magnet">Copy magnet</button>
    <hr>
    <button data-cact="category">Set category\u2026</button>
    <button data-cact="tag">Add tag\u2026</button>
    <hr>
    <button data-cact="remove">Remove</button>`;
  menu.hidden = false;
  menu.style.left = Math.min(x, window.innerWidth - 200) + "px";
  menu.style.top = Math.min(y, window.innerHeight - 320) + "px";
  $$("[data-cact]", menu).forEach((b) => (b.onclick = async () => {
    menu.hidden = true;
    const act = b.dataset.cact;
    try {
      if (act === "toggle") await togglePause(gid);
      else if (act === "details") openDetail(gid);
      else if (act === "remove") await removeGid(gid);
      else if (act === "open" || act === "reveal") {
        const r = await api(`/actions/${act}`, "POST", { gid });
        toast(`${act}: ${r.path}`, "ok");
      } else if (act === "magnet") {
        const d = await api(`/downloads/${gid}`);
        if (d.infoHash) {
          await navigator.clipboard.writeText(`magnet:?xt=urn:btih:${d.infoHash}`);
          toast("Magnet copied", "ok");
        }
      } else if (act === "category") {
        const name = prompt("Category name:", it.category || "");
        if (name !== null) await api("/downloads/batch", "POST", { action: "category", gids: [gid], category: name });
      } else if (act === "tag") {
        const tag = prompt("Tag to add:");
        if (tag) {
          const tags = [...new Set([...(it.tags || []), tag])];
          await api("/downloads/batch", "POST", { action: "tags", gids: [gid], tags });
        }
      }
    } catch (e) {
      toast(e.message, "err");
    }
  }));
}

function openModal(html) {
  $("#modalBox").innerHTML = html;
  $("#modalBackdrop").hidden = false;
}
function closeModal() {
  $("#modalBackdrop").hidden = true;
  $("#modalBox").innerHTML = "";
}

function fileToB64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result.split(",")[1]);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}

function openAdd() {
  openModal(`
    <h2>Add torrents</h2>
    <div class="field"><label>Magnet links / URLs (one per line)</label><textarea id="mMagnets" rows="5" placeholder="magnet:?xt=urn:btih:..."></textarea></div>
    <div class="field"><label>Torrent files</label>
      <div class="dropzone" id="dropzone">Drop .torrent files here, or <input type="file" id="mFiles" multiple accept=".torrent"></div>
      <div class="hint" id="fileCount"></div>
    </div>
    <div class="row2">
      <div class="field"><label>Category</label><select id="mCategory"><option value="">(none)</option>${state.categories.map((c) => `<option>${esc(c.name)}</option>`).join("")}</select></div>
      <div class="field"><label>Tags (comma separated)</label><input id="mTags"></div>
    </div>
    <div class="field"><label>Save to</label><input id="mDir" placeholder="${esc(state.settings?.download_dir || "")}"></div>
    <div class="modal-actions"><button class="btn" id="mCancel">Cancel</button><button class="btn btn-accent" id="mAdd">Add</button></div>
  `);
  let files = [];
  const dz = $("#dropzone");
  const setCount = () => ($("#fileCount").textContent = files.length ? files.length + " file(s) ready" : "");
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("over"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("over"));
  dz.addEventListener("drop", async (e) => {
    e.preventDefault();
    dz.classList.remove("over");
    for (const f of e.dataTransfer.files) if (f.name.endsWith(".torrent")) files.push({ name: f.name, data: await fileToB64(f) });
    setCount();
  });
  $("#mFiles").addEventListener("change", async (e) => {
    for (const f of e.target.files) files.push({ name: f.name, data: await fileToB64(f) });
    setCount();
  });
  $("#mCancel").onclick = closeModal;
  $("#mAdd").onclick = async () => {
    const lines = $("#mMagnets").value.split("\n").map((s) => s.trim()).filter(Boolean);
    const magnets = lines.filter((l) => l.startsWith("magnet:"));
    const urls = lines.filter((l) => /^https?:\/\//.test(l));
    const payload = {
      magnets, urls, torrents: files,
      category: $("#mCategory").value,
      tags: $("#mTags").value.split(",").map((s) => s.trim()).filter(Boolean),
      dir: $("#mDir").value.trim(),
    };
    if (!magnets.length && !urls.length && !files.length) { toast("Nothing to add", "err"); return; }
    try {
      const r = await api("/downloads", "POST", payload);
      toast(`Added ${r.count} download(s)`, "ok");
      closeModal();
    } catch (e) {
      toast(e.message, "err");
    }
  };
}

function openSettings() {
  const s = state.settings || {};
  const num = (id, label, val) => `<div class="field"><label>${label}</label><input type="number" id="${id}" value="${val}"></div>`;
  const chk = (id, label, val) => `<label class="switch"><input type="checkbox" id="${id}" ${val ? "checked" : ""}> ${label}</label>`;
  openModal(`
    <h2>Settings</h2>
    <div class="row2">
      <div class="field"><label>Download folder</label><input id="sDownloadDir" value="${esc(s.download_dir || "")}"></div>
      <div class="field"><label>Watch folder (.torrent auto-add)</label><input id="sWatch" value="${esc(s.watch_folder || "")}"></div>
    </div>
    <div class="row2">
      ${num("sMaxConcurrent", "Max concurrent downloads", s.max_concurrent)}
      ${num("sMaxConn", "Max connections per server", s.max_connection_per_server)}
    </div>
    <div class="row2">
      ${num("sDlLimit", "Global download limit (B/s, 0=unlimited)", s.global_download_limit)}
      ${num("sUlLimit", "Global upload limit (B/s, 0=unlimited)", s.global_upload_limit)}
    </div>
    <div class="field"><label>Listen port range</label><input id="sPort" value="${esc(s.listen_port || "")}"></div>
    <div class="hint" style="margin-bottom:10px">Forward this TCP+UDP port range on your router so peers can connect to you — the biggest real-world speed factor.</div>
    <div class="row2">
      <div>${chk("sDht", "DHT", s.dht)}${chk("sPex", "Peer exchange", s.pex)}${chk("sLpd", "Local peer discovery", s.lpd)}</div>
      <div>${chk("sEnc", "Encryption (arc4)", s.encryption)}${chk("sUpload", "Upload while downloading", s.upload_while_downloading)}</div>
    </div>
    <h4 style="margin-top:16px">Privacy</h4>
    <div class="row2">
      <div class="field"><label>Bind interface (VPN, blank=any)</label><input id="sInterface" value="${esc(s.interface || "")}"></div>
      <div>${chk("sKill", "Kill switch (pause all if interface down)", s.kill_switch)}${chk("sNotify", "Desktop notifications", s.notifications)}</div>
    </div>
    <div class="hint">Seeding is permanently disabled (seed-time=0).</div>
    <h4 style="margin-top:16px">Performance</h4>
    <div class="row2">
      <div class="field"><label>Preset</label>
        <select id="sPreset">
          <option value="conservative">Conservative</option>
          <option value="balanced">Balanced</option>
          <option value="aggressive">Aggressive</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div class="field"><label>File allocation</label>
        <select id="sFileAlloc">${["none", "prealloc", "trunc", "falloc"].map((v) => `<option ${s.file_allocation === v ? "selected" : ""}>${v}</option>`).join("")}</select>
      </div>
    </div>
    <div class="row2">${num("sBtMaxPeers", "Max peers per torrent", s.bt_max_peers)}${num("sBtOpenFiles", "Max open files per torrent", s.bt_max_open_files)}</div>
    <div class="row2">
      <div class="field"><label>Peer-seek speed limit</label><input id="sReqSpeed" value="${esc(s.bt_request_peer_speed_limit || "")}"></div>
      <div class="field"><label>Drop peers slower than</label><input id="sLowest" value="${esc(s.lowest_speed_limit || "0")}"></div>
    </div>
    <div class="row2">
      <div class="field"><label>Disk cache</label><input id="sDiskCache" value="${esc(s.disk_cache || "")}"></div>
      ${num("sTrackerTimeout", "Tracker connect timeout (s)", s.bt_tracker_connect_timeout)}
    </div>
    <div class="row2">
      <div>${chk("sOptConcurrent", "Auto-optimize concurrent downloads", s.optimize_concurrent_downloads)}${chk("sMmap", "Memory-map files", s.enable_mmap)}</div>
      <div class="hint">Engine restart needed (button below).</div>
    </div>
    <h4 style="margin-top:16px">Row detail</h4>
    <div class="colgrid">${Object.keys(ROW_FIELDS).map((f) => `<label class="switch" style="margin:0"><input type="checkbox" class="rowfield" data-field="${f}" ${state.rowFields.includes(f) ? "checked" : ""}> ${ROW_FIELDS[f].label}</label>`).join("")}</div>
    <div class="modal-actions">
      <button class="btn" id="sRestart">Restart engine</button>
      <button class="btn" id="sCancel">Cancel</button>
      <button class="btn btn-accent" id="sSave">Save</button>
    </div>
  `);
  $("#sCancel").onclick = closeModal;
  $("#sRestart").onclick = async () => { await api("/engine/restart", "POST"); toast("Engine restarted", "ok"); };
  const perfIds = ["sMaxConcurrent", "sBtMaxPeers", "sBtOpenFiles", "sReqSpeed", "sLowest", "sDiskCache", "sFileAlloc", "sOptConcurrent", "sMmap", "sTrackerTimeout"];
  const applyPreset = (name) => {
    const p = state.presets[name];
    if (!p) return;
    $("#sMaxConcurrent").value = p.max_concurrent;
    $("#sBtMaxPeers").value = p.bt_max_peers;
    $("#sBtOpenFiles").value = p.bt_max_open_files;
    $("#sReqSpeed").value = p.bt_request_peer_speed_limit;
    $("#sLowest").value = p.lowest_speed_limit;
    $("#sDiskCache").value = p.disk_cache;
    $("#sFileAlloc").value = p.file_allocation;
    $("#sOptConcurrent").checked = p.optimize_concurrent_downloads;
    $("#sMmap").checked = p.enable_mmap;
    $("#sTrackerTimeout").value = p.bt_tracker_connect_timeout;
  };
  const presetSel = $("#sPreset");
  presetSel.value = state.presets[s.perf_preset] ? s.perf_preset : "custom";
  presetSel.onchange = () => { if (presetSel.value !== "custom") applyPreset(presetSel.value); };
  perfIds.forEach((id) => { const el = $("#" + id); if (el) el.addEventListener("input", () => (presetSel.value = "custom")); });
  $("#sFileAlloc").addEventListener("change", () => (presetSel.value = "custom"));

  $("#sSave").onclick = async () => {
    const rowFields = Object.keys(ROW_FIELDS).filter((f) => $(`.rowfield[data-field="${f}"]`).checked);
    const patch = {
      download_dir: $("#sDownloadDir").value.trim(),
      watch_folder: $("#sWatch").value.trim(),
      max_concurrent: Number($("#sMaxConcurrent").value) || 1,
      max_connection_per_server: Number($("#sMaxConn").value) || 1,
      global_download_limit: Number($("#sDlLimit").value) || 0,
      global_upload_limit: Number($("#sUlLimit").value) || 0,
      listen_port: $("#sPort").value.trim(),
      dht: $("#sDht").checked,
      pex: $("#sPex").checked,
      lpd: $("#sLpd").checked,
      encryption: $("#sEnc").checked,
      upload_while_downloading: $("#sUpload").checked,
      interface: $("#sInterface").value.trim(),
      kill_switch: $("#sKill").checked,
      notifications: $("#sNotify").checked,
      row_fields: rowFields.length ? rowFields : DEFAULT_ROW_FIELDS,
      perf_preset: $("#sPreset").value,
      bt_max_peers: Number($("#sBtMaxPeers").value) || 128,
      bt_max_open_files: Number($("#sBtOpenFiles").value) || 100,
      bt_request_peer_speed_limit: $("#sReqSpeed").value.trim() || "1M",
      lowest_speed_limit: $("#sLowest").value.trim() || "0",
      disk_cache: $("#sDiskCache").value.trim() || "64M",
      file_allocation: $("#sFileAlloc").value,
      optimize_concurrent_downloads: $("#sOptConcurrent").checked,
      enable_mmap: $("#sMmap").checked,
      bt_tracker_connect_timeout: Number($("#sTrackerTimeout").value) || 5,
      bt_tracker_timeout: Number($("#sTrackerTimeout").value) || 5,
    };
    try {
      state.settings = await api("/settings", "PUT", patch);
      state.rowFields = state.settings.row_fields || DEFAULT_ROW_FIELDS;
      if (patch.notifications && "Notification" in window && Notification.permission === "default") Notification.requestPermission();
      state._sig = "";
      renderRows();
      closeModal();
      toast("Settings saved", "ok");
    } catch (e) {
      toast(e.message, "err");
    }
  };
}

function openManage(kind) {
  const catRow = (c) => `<div class="le-row"><input class="cat-name" value="${esc(c.name)}" placeholder="Name"><input class="cat-path" value="${esc(c.path || "")}" placeholder="Save path (optional)"><button class="mini cdel">\u2715</button></div>`;
  const tagRow = (t) => `<div class="le-row one"><input class="tag-val" value="${esc(t)}" placeholder="Tag"><button class="mini tdel">\u2715</button></div>`;
  const viewRow = (v) => `<div class="le-row" style="grid-template-columns:1fr 1fr 1fr 30px">
      <input class="v-name" value="${esc(v.name)}" placeholder="Name">
      <select class="v-status">${STATUS_FILTERS.map((s) => `<option ${((v.filters || {}).status || "all") === s ? "selected" : ""}>${s}</option>`).join("")}</select>
      <select class="v-sort">${SORT_KEYS.map((k) => `<option ${(v.sort || {}).key === k.id ? "selected" : ""} value="${k.id}">${k.label}</option>`).join("")}</select>
      <button class="mini vdel">\u2715</button></div>`;

  if (kind === "categories") {
    openModal(`<h2>Categories</h2>
      <div class="list-editor" id="catEditor">${state.categories.map(catRow).join("")}</div>
      <div class="modal-actions"><button class="btn" id="addCat">Add</button><button class="btn" id="mCancel">Cancel</button><button class="btn btn-accent" id="mSave">Save</button></div>`);
    const render = () => { $("#catEditor").innerHTML = state.categories.map(catRow).join(""); wireDel(); };
    const wireDel = () => $$(".cdel").forEach((b, i) => (b.onclick = () => { state.categories.splice(i, 1); render(); }));
    $("#addCat").onclick = () => { state.categories.push({ name: "", path: "" }); render(); };
    $("#mCancel").onclick = closeModal;
    $("#mSave").onclick = async () => {
      const names = $$(".cat-name").map((i) => i.value.trim());
      const paths = $$(".cat-path").map((i) => i.value.trim());
      state.categories = await api("/categories", "PUT", names.map((n, i) => ({ name: n, path: paths[i] })).filter((c) => c.name));
      renderSidebar();
      closeModal();
      toast("Categories saved", "ok");
    };
    wireDel();
  } else if (kind === "tags") {
    openModal(`<h2>Tags</h2>
      <div class="list-editor" id="tagEditor">${state.tags.map(tagRow).join("")}</div>
      <div class="modal-actions"><button class="btn" id="addTag">Add</button><button class="btn" id="mCancel">Cancel</button><button class="btn btn-accent" id="mSave">Save</button></div>`);
    const render = () => { $("#tagEditor").innerHTML = state.tags.map(tagRow).join(""); wireDel(); };
    const wireDel = () => $$(".tdel").forEach((b, i) => (b.onclick = () => { state.tags.splice(i, 1); render(); }));
    $("#addTag").onclick = () => { state.tags.push(""); render(); };
    $("#mCancel").onclick = closeModal;
    $("#mSave").onclick = async () => {
      state.tags = await api("/tags", "PUT", $$(".tag-val").map((i) => i.value.trim()).filter(Boolean));
      renderSidebar();
      closeModal();
      toast("Tags saved", "ok");
    };
    wireDel();
  } else {
    openModal(`<h2>Saved views</h2>
      <div class="list-editor" id="viewEditor">${state.views.map(viewRow).join("")}</div>
      <div class="modal-actions"><button class="btn" id="addView">Add</button><button class="btn" id="mCancel">Cancel</button><button class="btn btn-accent" id="mSave">Save</button></div>`);
    const render = () => { $("#viewEditor").innerHTML = state.views.map(viewRow).join(""); wireDel(); };
    const wireDel = () => $$(".vdel").forEach((b, i) => (b.onclick = () => { state.views.splice(i, 1); render(); }));
    $("#addView").onclick = () => { state.views.push({ name: "New view", filters: { status: "all" }, sort: { key: "addedAt", dir: "desc" } }); render(); };
    $("#mCancel").onclick = closeModal;
    $("#mSave").onclick = async () => {
      const names = $$(".v-name").map((i) => i.value.trim());
      const statuses = $$(".v-status").map((i) => i.value);
      const sorts = $$(".v-sort").map((i) => i.value);
      state.views = await api("/views", "PUT", names.map((n, i) => ({ name: n, filters: { status: statuses[i] }, sort: { key: sorts[i], dir: "desc" } })).filter((v) => v.name));
      renderSidebar();
      closeModal();
      toast("Views saved", "ok");
    };
    wireDel();
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $$("#themeToggle button").forEach((b) => b.classList.toggle("active", b.dataset.themeSet === theme));
}

async function init() {
  const [settings, categories, tags, views, statusRes, downloadsRes, presets] = await Promise.all([
    api("/settings"),
    api("/categories"),
    api("/tags"),
    api("/views"),
    api("/status"),
    api("/downloads").catch(() => ({ items: [], global: {} })),
    api("/presets").catch(() => ({})),
  ]);
  state.settings = settings;
  state.categories = categories;
  state.tags = tags;
  state.views = views;
  state.presets = presets;
  state.rowFields = (settings.row_fields || DEFAULT_ROW_FIELDS).filter((f) => ROW_FIELDS[f]);
  if (!state.rowFields.length) state.rowFields = [...DEFAULT_ROW_FIELDS];
  state.sort = settings.sort || state.sort;
  state.filters = Object.assign(state.filters, settings.filters || {});
  applyTheme(settings.theme || "dark");
  setConn(statusRes.aria2Running);
  $("#search").value = state.filters.search || "";

  $("#search").addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    state._sig = "";
    renderRows();
  });
  $("#addBtn").onclick = openAdd;
  $("#settingsBtn").onclick = openSettings;
  $$("#themeToggle button").forEach((b) => (b.onclick = async () => {
    applyTheme(b.dataset.themeSet);
    await api("/settings", "PUT", { theme: b.dataset.themeSet });
  }));

  $("#statusChips").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-status]");
    if (!chip) return;
    state.filters.status = chip.dataset.status;
    state._sig = "";
    renderStatusChips();
    renderRows();
  });
  $("#sortKey").addEventListener("change", (e) => { state.sort.key = e.target.value; state._sig = ""; renderRows(); });
  $("#sortDir").addEventListener("click", () => { state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc"; renderSort(); state._sig = ""; renderRows(); });

  $("#tableBody").addEventListener("click", (e) => {
    const task = e.target.closest(".task");
    if (!task) return;
    const gid = task.dataset.gid;
    if (e.target.classList.contains("task-check")) {
      if (e.target.checked) state.selection.add(gid);
      else state.selection.delete(gid);
      task.classList.toggle("selected", e.target.checked);
      renderBatchBar();
      return;
    }
    const act = e.target.closest("[data-act]");
    if (act) { taskAction(gid, act.dataset.act, task); return; }
    if (e.target.closest(".task-row")) toggleTask(gid, task);
  });
  $("#tableBody").addEventListener("keydown", (e) => {
    const row = e.target.closest(".task-row");
    if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleTask(row.closest(".task").dataset.gid, row.closest(".task")); }
  });
  $("#tableBody").addEventListener("contextmenu", (e) => {
    const task = e.target.closest(".task");
    if (!task) return;
    e.preventDefault();
    showContextMenu(e.clientX, e.clientY, task.dataset.gid);
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#ctxMenu")) $("#ctxMenu").hidden = true;
    const b = e.target.closest("[data-batch]");
    if (b) batch(b.dataset.batch);
  });

  $(".sidebar").addEventListener("click", (e) => {
    const item = e.target.closest(".nav-item");
    if (!item) return;
    if (item.dataset.category !== undefined) state.filters.category = item.dataset.category;
    else if (item.dataset.tag !== undefined) state.filters.tag = item.dataset.tag;
    else if (item.dataset.view !== undefined) {
      const v = state.views[Number(item.dataset.view)];
      state.filters.status = (v.filters || {}).status || "all";
      state.sort = v.sort || state.sort;
      renderSort();
    }
    state._sig = "";
    renderStatusChips();
    renderSidebar();
    renderRows();
  });
  $$("[data-manage]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); openManage(b.dataset.manage); }));

  $("#modalBackdrop").addEventListener("click", (e) => { if (e.target.id === "modalBackdrop") closeModal(); });

  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
    if (e.key === "Escape") {
      if (!$("#modalBackdrop").hidden) closeModal();
      else if (!$("#drawer").hidden) closeDrawer();
      else $("#ctxMenu").hidden = true;
      return;
    }
    if (typing) return;
    if (e.key === "/") { e.preventDefault(); $("#search").focus(); }
    else if (e.key === "p") batch("pause");
    else if (e.key === "r") batch("resume");
    else if (e.key === "Delete") batch("remove");
  });

  renderSort();
  renderStats();
  renderStatusChips();
  renderSidebar();
  renderRows();
  onUpdate({ items: downloadsRes.items || [], global: downloadsRes.global || {}, events: [] });
  connect();
}

init().catch((e) => {
  document.body.innerHTML = `<div style="padding:40px;font:14px/mono;color:var(--ink)">Failed to start: ${esc(e.message)}<br><br>Is the server running? Open http://127.0.0.1:8080</div>`;
});
