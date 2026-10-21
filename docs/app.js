(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  const CATS = ["All", "Engineering", "Analyst", "Business", "Product"];
  const APPLIED_PATH = "docs/data/applied.json";

  // Repo coordinates when hosted on <owner>.github.io/<repo>/
  const gh = (() => {
    const h = location.hostname;
    if (!h.endsWith(".github.io")) return null;
    const owner = h.split(".")[0];
    const repo = location.pathname.split("/").filter(Boolean)[0] || h;
    return { owner, repo, api: `https://api.github.com/repos/${owner}/${repo}/contents/${APPLIED_PATH}` };
  })();

  let jobs = [], today = "", applied = store.get("jr.applied", {}), remoteSha = null;
  const ui = Object.assign({ q: "", cat: "All", type: "", status: "todo", newOnly: false }, store.get("jr.ui", {}));

  // ---------- applied state (local + GitHub sync) ----------
  const b64decode = (b) => new TextDecoder().decode(Uint8Array.from(atob(b.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
  const b64encode = (s) => { const bytes = new TextEncoder().encode(s); let bin = ""; bytes.forEach((x) => (bin += String.fromCharCode(x))); return btoa(bin); };
  const token = () => store.get("jr.token", "");

  async function fetchRemoteApplied() {
    try {
      if (gh) {
        const headers = { Accept: "application/vnd.github+json" };
        if (token()) headers.Authorization = `Bearer ${token()}`;
        const r = await fetch(`${gh.api}?ref=main&t=${Date.now()}`, { headers, cache: "no-store" });
        if (!r.ok) throw new Error(r.status);
        const d = await r.json();
        remoteSha = d.sha;
        return JSON.parse(b64decode(d.content) || "{}");
      }
      const r = await fetch(`data/applied.json?t=${Date.now()}`, { cache: "no-store" });
      return r.ok ? await r.json() : {};
    } catch { return null; }
  }

  async function pushApplied(attempt = 0) {
    if (!gh || !token()) return;
    setSync("Syncing…");
    const remote = await fetchRemoteApplied();
    if (remote === null) { setSync("Couldn't reach GitHub. Ticks are saved on this device."); return; }
    // merge: local edits win, but keep remote entries we don't know about unless we removed them
    const removed = store.get("jr.removed", {});
    const merged = { ...remote, ...applied };
    Object.keys(removed).forEach((id) => { if (!applied[id]) delete merged[id]; });
    const r = await fetch(gh.api, {
      method: "PUT",
      headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token()}` },
      body: JSON.stringify({ message: "Update applied jobs", content: b64encode(JSON.stringify(sortObj(merged), null, 1) + "\n"), sha: remoteSha || undefined, branch: "main" }),
    });
    if (r.status === 409 && attempt < 2) return pushApplied(attempt + 1);
    if (!r.ok) { setSync(r.status === 401 || r.status === 403 ? "Token rejected. Check that it can write to this repo." : `Sync failed (${r.status}).`); return; }
    remoteSha = (await r.json()).content.sha;
    store.set("jr.removed", {});
    setSync("Synced ✓");
  }
  const sortObj = (o) => Object.fromEntries(Object.keys(o).sort().map((k) => [k, o[k]]));

  let syncTimer;
  function queueSync() { clearTimeout(syncTimer); syncTimer = setTimeout(pushApplied, 1200); }
  function setSync(msg) { const el = $("#syncState"); if (el) el.textContent = msg; }

  function toggleApplied(id) {
    if (applied[id]) {
      delete applied[id];
      const removed = store.get("jr.removed", {}); removed[id] = 1; store.set("jr.removed", removed);
    } else {
      applied[id] = { at: today || new Date().toISOString().slice(0, 10), by: "me" };
    }
    store.set("jr.applied", applied);
    queueSync();
  }

  // ---------- rendering ----------
  const ago = (iso) => {
    if (!iso) return "";
    const days = Math.round((Date.parse(today) - Date.parse(iso)) / 864e5);
    return days <= 0 ? "today" : days === 1 ? "1d ago" : days < 31 ? `${days}d ago` : `${Math.round(days / 30)}mo ago`;
  };

  function matches(j) {
    if (ui.cat !== "All" && j.category !== ui.cat) return false;
    if (ui.type && j.type !== ui.type) return false;
    if (ui.status === "todo" && applied[j.id]) return false;
    if (ui.status === "applied" && !applied[j.id]) return false;
    if (ui.newOnly && j.first_seen !== today) return false;
    if (ui.q) {
      const hay = (j._hay ||= `${j.company} ${j.title} ${j.location} ${j.category} ${j.type} ${j.description}`.toLowerCase());
      return ui.q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w));
    }
    return true;
  }

  function card(j) {
    const a = applied[j.id];
    const tags = [
      j.first_seen === today ? '<span class="tag new">New</span>' : "",
      `<span class="tag">${esc(j.type)}</span>`,
      `<span class="tag">${esc(j.category)}</span>`,
      j.salary ? `<span class="tag pay">${esc(j.salary)}</span>` : "",
      `<span class="tag">${esc(j.location)}</span>`,
      j.posted ? `<span class="tag">Posted ${ago(j.posted)}</span>` : "",
      a ? `<span class="tag by">Applied ${esc(a.at)}${a.by === "claude" ? " by Claude" : ""}</span>` : "",
      j.closed ? '<span class="tag">Listing closed</span>' : "",
    ].join("");
    return `<li class="card${a ? " applied" : ""}${j.closed ? " closed" : ""}" data-id="${esc(j.id)}">
      <div><div class="co">${esc(j.company)}</div><h2 class="title">${esc(j.title)}</h2></div>
      <button class="tick" role="checkbox" aria-checked="${a ? "true" : "false"}" aria-label="Mark ${esc(j.title)} at ${esc(j.company)} as applied" data-act="tick">${CHECK}</button>
      <div class="meta">${tags}</div>
      <details class="jd"><summary>Job description</summary><pre data-jd></pre></details>
      <div class="actions">
        <a class="btn" href="${esc(j.apply_url || j.url)}" target="_blank" rel="noopener">Apply</a>
        ${j.url && j.url !== j.apply_url ? `<a class="btn ghost" href="${esc(j.url)}" target="_blank" rel="noopener">View posting</a>` : ""}
        <span class="muted">via ${esc(j.source)}</span>
      </div>
    </li>`;
  }

  function render() {
    const shown = jobs.filter(matches);
    $("#list").innerHTML = shown.map(card).join("");
    $("#empty").hidden = shown.length > 0;
    $("#count").textContent = `${shown.length} of ${jobs.length} jobs`;
    const appliedCount = jobs.filter((j) => applied[j.id]).length;
    const newCount = jobs.filter((j) => j.first_seen === today).length;
    $("#stats").innerHTML = `<span><b>${jobs.length}</b>open</span><span><b>${newCount}</b>new today</span><span><b>${appliedCount}</b>applied</span>`;
    document.querySelectorAll("#catChips .chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.cat === ui.cat)));
  }

  function saveUi() { store.set("jr.ui", ui); render(); }

  // ---------- events ----------
  $("#catChips").innerHTML = CATS.map((c) => `<button class="chip" data-cat="${c}" aria-pressed="false">${c}</button>`).join("");
  $("#catChips").addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) { ui.cat = b.dataset.cat; saveUi(); } });
  $("#q").value = ui.q; $("#typeSel").value = ui.type; $("#statusSel").value = ui.status; $("#newOnly").checked = ui.newOnly;
  let qTimer;
  $("#q").addEventListener("input", (e) => { clearTimeout(qTimer); qTimer = setTimeout(() => { ui.q = e.target.value.trim(); saveUi(); }, 150); });
  $("#typeSel").addEventListener("change", (e) => { ui.type = e.target.value; saveUi(); });
  $("#statusSel").addEventListener("change", (e) => { ui.status = e.target.value; saveUi(); });
  $("#newOnly").addEventListener("change", (e) => { ui.newOnly = e.target.checked; saveUi(); });

  $("#list").addEventListener("click", (e) => {
    const tick = e.target.closest('[data-act="tick"]');
    if (!tick) return;
    const li = tick.closest(".card");
    toggleApplied(li.dataset.id);
    const on = !!applied[li.dataset.id];
    tick.setAttribute("aria-checked", String(on));
    li.classList.toggle("applied", on);
    // let the green tick show before the card leaves the "Not applied" view
    setTimeout(render, ui.status === "" ? 0 : 450);
  });
  $("#list").addEventListener("toggle", (e) => {
    const d = e.target;
    if (d.tagName !== "DETAILS" || !d.open) return;
    const pre = d.querySelector("[data-jd]");
    if (!pre.textContent) pre.textContent = (jobs.find((j) => j.id === d.closest(".card").dataset.id) || {}).description || "No description available.";
  }, true);

  const dlg = $("#settings");
  $("#settingsBtn").addEventListener("click", () => {
    $("#token").value = token();
    setSync(gh ? (token() ? "Sync is on." : "Sync is off. Ticks stay on this device.") : "Sync works once the site is live on GitHub Pages.");
    dlg.showModal();
  });
  dlg.addEventListener("close", () => {
    if (dlg.returnValue === "save") { store.set("jr.token", $("#token").value.trim()); pushApplied(); }
    if (dlg.returnValue === "clear") store.set("jr.token", "");
  });

  // ---------- boot ----------
  (async () => {
    try {
      const r = await fetch(`data/jobs.json?t=${Date.now()}`, { cache: "no-store" });
      const d = await r.json();
      jobs = d.jobs || [];
      today = (d.updated_at || new Date().toISOString()).slice(0, 10);
      $("#updated").textContent = `Updated ${new Date(d.updated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · refreshes daily 8 AM IST`;
    } catch {
      $("#updated").textContent = "Couldn't load jobs. Pull to refresh.";
    }
    render();
    const remote = await fetchRemoteApplied();
    if (remote) {
      const removed = store.get("jr.removed", {});
      Object.entries(remote).forEach(([id, v]) => { if (!removed[id] && !applied[id]) applied[id] = v; });
      store.set("jr.applied", applied);
      render();
    }
  })();
})();
