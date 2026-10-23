const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

const slug = (s) =>
  String(s ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

const ICONS = {
  temperature: "mdi:thermometer",
  humidity: "mdi:water-percent",
  power: "mdi:flash",
  energy: "mdi:lightning-bolt",
  battery: "mdi:battery",
  voltage: "mdi:sine-wave",
  current: "mdi:current-ac",
  pressure: "mdi:gauge",
  illuminance: "mdi:brightness-5",
  timestamp: "mdi:clock-outline",
  duration: "mdi:timer-outline",
  monetary: "mdi:cash",
  door: "mdi:door",
  window: "mdi:window-open-variant",
  motion: "mdi:motion-sensor",
  occupancy: "mdi:account",
  moisture: "mdi:water-alert",
  problem: "mdi:alert-circle",
  connectivity: "mdi:wifi",
  running: "mdi:play-circle",
};

const POWER = [
  {
    icon: "mdi:check-decagram",
    title: "Check configuration",
    desc: "Validate your YAML without changing anything.",
    domain: "homeassistant",
    service: "check_config",
    ok: "Configuration is valid",
    stay: true,
  },
  {
    icon: "mdi:file-refresh",
    title: "Reload template entities",
    desc: "Applies template sensor changes. No downtime.",
    domain: "template",
    service: "reload",
    ok: "Templates reloaded",
  },
  {
    icon: "mdi:reload",
    title: "Reload all YAML",
    desc: "Reloads core, templates, automations, scripts and more.",
    domain: "homeassistant",
    service: "reload_all",
    ok: "YAML reloaded",
  },
  {
    icon: "mdi:restart",
    title: "Restart Home Assistant",
    desc: "Needed for sensor platforms in configuration.yaml. Checks the config first.",
    domain: "homeassistant",
    service: "restart",
    ok: "Restarting... the panel will reconnect",
    danger: true,
    confirm: "Restart Home Assistant now?",
  },
];

const PACKAGES_SNIPPET = `homeassistant:
  packages: !include_dir_named packages`;

const PLACEHOLDER = `# Paste a sensor, a list, or a whole template: block
- name: Example Double
  unique_id: example_double
  unit_of_measurement: "W"
  state: "{{ states('sensor.x') | float(0) * 2 }}"`;

const CSS = `
<style>
  ysm-panel{display:block;
    --ysm-blue:#3b82f6;--ysm-purple:#8b5cf6;--ysm-teal:#14b8a6;
    --ysm-orange:#f59e0b;--ysm-green:#22c55e;--ysm-red:#ef4444;
    --ysm-radius:14px}
  ysm-panel *{box-sizing:border-box}
  .wrap{max-width:960px;margin:0 auto;padding:0 16px 40px;
    color:var(--primary-text-color);
    font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}

  .hero{margin:0 -16px 20px;padding:28px 24px 22px;color:#fff;
    background:linear-gradient(120deg,#2563eb 0%,#7c3aed 55%,#db2777 100%);
    border-radius:0 0 var(--ysm-radius) var(--ysm-radius);
    box-shadow:0 6px 24px #7c3aed44}
  .hero-top{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  .hero h1{margin:0;font-size:26px;font-weight:600;flex:1;min-width:200px;
    display:flex;align-items:center;gap:10px}
  .hero p{margin:6px 0 0;opacity:.85;font-size:14px}
  .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}
  .stat{background:#ffffff22;backdrop-filter:blur(6px);border-radius:12px;
    padding:10px 14px;border:1px solid #ffffff33}
  .stat b{display:block;font-size:24px;line-height:1.1}
  .stat span{font-size:12px;opacity:.85;text-transform:uppercase;letter-spacing:.5px}

  button{font:inherit;font-weight:500;border:none;border-radius:10px;
    padding:9px 16px;cursor:pointer;display:inline-flex;align-items:center;
    gap:6px;transition:transform .1s,box-shadow .15s,opacity .15s;
    background:var(--primary-color);color:var(--text-primary-color,#fff)}
  button:hover{opacity:.92;box-shadow:0 3px 10px #0003}
  button:active{transform:scale(.97)}
  button:disabled{opacity:.5;cursor:default}
  button ha-icon{--mdc-icon-size:18px}
  .btn-white{background:#fff;color:#4c1d95}
  .btn-ghost{background:#ffffff22;color:#fff;border:1px solid #ffffff55}
  button.sec{background:transparent;color:var(--primary-text-color);
    border:1px solid var(--divider-color)}
  button.danger{background:transparent;color:var(--ysm-red);
    border:1px solid var(--ysm-red)}
  button.edit{background:var(--ysm-blue);color:#fff}
  button.copy{background:var(--ysm-teal);color:#fff}
  button.sm{padding:6px 12px;font-size:13px}

  .toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
  .searchbox{flex:1;min-width:200px;position:relative}
  .searchbox ha-icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);
    color:var(--secondary-text-color);--mdc-icon-size:20px}
  input.search{width:100%;padding:11px 14px 11px 40px;font:inherit;
    border-radius:12px;border:1px solid var(--divider-color);outline:none;
    background:var(--card-background-color);color:var(--primary-text-color)}
  input.search:focus{border-color:var(--ysm-purple);
    box-shadow:0 0 0 3px #8b5cf633}
  .tabs{display:inline-flex;padding:4px;border-radius:12px;gap:4px;
    background:var(--secondary-background-color)}
  .tab{padding:7px 16px;border-radius:9px;cursor:pointer;font-size:14px;
    font-weight:500;color:var(--secondary-text-color);transition:all .15s}
  .tab.on{background:linear-gradient(120deg,#2563eb,#7c3aed);color:#fff;
    box-shadow:0 2px 8px #7c3aed55}
  .tab small{opacity:.8;margin-left:4px}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}
  @media(max-width:520px){.grid{grid-template-columns:1fr}
    .stats{gap:6px}.stat{padding:8px 10px}.stat b{font-size:20px}}
  .card{--accent:var(--ysm-blue);position:relative;overflow:hidden;
    background:var(--card-background-color);border-radius:var(--ysm-radius);
    padding:16px 16px 14px 20px;
    box-shadow:var(--ha-card-box-shadow,0 2px 8px #0002);
    transition:transform .15s,box-shadow .15s}
  .card:hover{transform:translateY(-2px);box-shadow:0 8px 20px #0003}
  .card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;
    background:var(--accent)}
  .card.binary{--accent:var(--ysm-purple)}
  .card.platform{--accent:var(--ysm-orange)}
  .top{display:flex;gap:12px;align-items:center}
  .tile{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;
    flex:none;color:var(--accent);
    background:color-mix(in srgb,var(--accent) 16%,transparent)}
  .tile ha-icon{--mdc-icon-size:24px}
  .title{flex:1;min-width:0}
  .name{font-weight:600;font-size:16px;word-break:break-word}
  .sub{font-size:12px;color:var(--secondary-text-color);margin-top:2px;
    word-break:break-all}
  .pill{font-size:13px;font-weight:600;padding:4px 12px;border-radius:20px;
    white-space:nowrap;color:#fff;background:var(--ysm-teal)}
  .pill.on{background:var(--ysm-green)}
  .pill.off{background:#94a3b8}
  .pill.bad{background:var(--ysm-red)}
  .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
  .chip{font-size:11px;font-weight:500;padding:3px 9px;border-radius:20px;
    color:var(--accent);
    background:color-mix(in srgb,var(--accent) 14%,transparent)}
  .chip.neutral{color:var(--secondary-text-color);
    background:var(--secondary-background-color)}
  details{margin-top:12px}
  summary{cursor:pointer;font-size:13px;font-weight:500;color:var(--accent);
    user-select:none}
  pre{margin:8px 0 0;padding:12px;border-radius:10px;overflow:auto;font-size:12px;
    line-height:1.5;max-height:300px;
    background:var(--secondary-background-color);border:1px solid var(--divider-color)}
  .actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}

  .empty{text-align:center;padding:48px 16px;color:var(--secondary-text-color);
    border:2px dashed var(--divider-color);border-radius:var(--ysm-radius)}
  .empty ha-icon{--mdc-icon-size:48px;color:var(--ysm-purple);display:block;
    margin:0 auto 8px}
  .banner{padding:12px 14px;border-radius:12px;margin-bottom:14px;color:#fff;
    background:linear-gradient(120deg,#ef4444,#db2777)}
  .banner.warn{background:linear-gradient(120deg,#f59e0b,#ea580c);
    display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .banner.warn .msg{flex:1;min-width:220px;font-size:14px;line-height:1.5}
  .banner pre{color:var(--primary-text-color);max-height:none}

  .overlay{position:fixed;inset:0;background:#0009;backdrop-filter:blur(3px);
    z-index:20;display:flex;align-items:center;justify-content:center;padding:12px}
  .modal{background:var(--card-background-color);border-radius:18px;width:100%;
    max-width:680px;max-height:95vh;overflow:auto;
    box-shadow:0 20px 60px #0008}
  .mhead{padding:16px 20px;color:#fff;font-size:18px;font-weight:600;
    display:flex;align-items:center;gap:10px;
    background:linear-gradient(120deg,#2563eb,#7c3aed)}
  .mbody{padding:18px 20px 20px}
  textarea{width:100%;height:300px;padding:12px;resize:vertical;
    font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;
    line-height:1.5;border-radius:12px;tab-size:2;outline:none;
    border:1px solid var(--divider-color);
    background:var(--secondary-background-color);color:var(--primary-text-color)}
  textarea:focus{border-color:var(--ysm-purple);box-shadow:0 0 0 3px #8b5cf633}
  select{font:inherit;padding:6px 10px;border-radius:8px;
    background:var(--secondary-background-color);color:var(--primary-text-color);
    border:1px solid var(--divider-color)}
  .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .hint{font-size:12px;color:var(--secondary-text-color);margin:10px 0;line-height:1.5}
  .hint code{background:var(--secondary-background-color);padding:1px 5px;
    border-radius:4px}
  .err{color:var(--ysm-red);font-size:13px;margin:8px 0;white-space:pre-wrap}
  .foot{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}

  .power{display:flex;align-items:center;gap:12px;width:100%;text-align:left;
    margin-bottom:10px;padding:12px 14px;border-radius:12px;
    background:var(--secondary-background-color);
    color:var(--primary-text-color);border:1px solid var(--divider-color)}
  .power ha-icon{--mdc-icon-size:26px;color:var(--ysm-blue);flex:none}
  .power.danger ha-icon{color:var(--ysm-red)}
  .power b{display:block;font-size:15px}
  .power span{font-size:12px;color:var(--secondary-text-color)}

  .toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
    z-index:30;padding:10px 18px;border-radius:24px;color:#fff;font-weight:500;
    background:var(--ysm-green);box-shadow:0 6px 20px #0006;
    animation:pop .25s ease}
  .toast.bad{background:var(--ysm-red)}
  @keyframes pop{from{opacity:0;transform:translate(-50%,12px)}}
</style>`;

const icon = (name) => `<ha-icon icon="${esc(name)}"></ha-icon>`;

class YsmPanel extends HTMLElement {
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
  }

  _init() {
    this._tab = "managed";
    this._q = "";
    this._error = "";
    this._data = { yaml: [], managed: [], restart: [], packages_ok: true };
    this.innerHTML = `${CSS}
      <div class="wrap">
        <div class="hero">
          <div class="hero-top">
            <h1>${icon("mdi:code-braces-box")} Custom Sensor Viewer</h1>
            <button class="btn-ghost" id="power">${icon("mdi:restart")}Reload / Restart</button>
            <button class="btn-ghost" id="refresh">${icon("mdi:refresh")}Refresh</button>
            <button class="btn-white" id="add">${icon("mdi:plus")}Add sensor</button>
          </div>
          <p>View, add, edit and delete your YAML sensors.</p>
          <div class="stats" id="stats"></div>
        </div>
        <div class="toolbar">
          <div class="searchbox">
            ${icon("mdi:magnify")}
            <input class="search" id="q" placeholder="Search name, id, template...">
          </div>
          <div class="tabs" id="tabs"></div>
        </div>
        <div id="banner"></div>
        <div id="list"></div>
      </div>
      <div id="modal"></div>
      <div id="toast"></div>`;
    this.querySelector("#add").onclick = () => this._edit({});
    this.querySelector("#refresh").onclick = () => this._load();
    this.querySelector("#power").onclick = () => this._power();
    this.querySelector("#q").oninput = (e) => {
      this._q = e.target.value.toLowerCase();
      this._render();
    };
    this._load();
  }

  _toast(msg, bad = false) {
    const t = this.querySelector("#toast");
    t.innerHTML = `<div class="toast ${bad ? "bad" : ""}">${esc(msg)}</div>`;
    clearTimeout(this._tt);
    this._tt = setTimeout(() => (t.innerHTML = ""), 2800);
  }

  async _load() {
    this._error = "";
    try {
      this._data = await this._hass.callWS({ type: "ysm/list" });
    } catch (e) {
      this._error = e.message || String(e);
    }
    this._render();
  }

  _banners() {
    const el = this.querySelector("#banner");
    let html = "";
    if (this._error) {
      html += `<div class="banner">Load failed: ${esc(this._error)}</div>`;
    }
    if (this._data.packages_ok === false) {
      html += `<div class="banner warn">
        <div class="msg"><b>Setup needed.</b> Managed sensors are saved to
        <code>packages/ysm.yaml</code>, but packages aren't loaded. Add this to
        <code>configuration.yaml</code>, then restart:
        <pre>${esc(PACKAGES_SNIPPET)}</pre></div>
        <button class="btn-white" data-power>${icon("mdi:restart")}Options</button>
      </div>`;
    }
    const reasons = this._data.restart || [];
    if (reasons.length) {
      html += `<div class="banner warn">
        <div class="msg"><b>Restart needed.</b><br>${reasons
          .map(esc)
          .join("<br>")}</div>
        <button class="btn-white" data-power>${icon("mdi:restart")}Restart options</button>
      </div>`;
    }
    el.innerHTML = html;
    el.querySelectorAll("[data-power]").forEach(
      (b) => (b.onclick = () => this._power()),
    );
  }

  _power() {
    const modal = this.querySelector("#modal");
    modal.innerHTML = `
      <div class="overlay">
        <div class="modal">
          <div class="mhead">${icon("mdi:restart")} Reload / Restart</div>
          <div class="mbody">
            <div id="opts"></div>
            <div class="err" id="err"></div>
            <div class="foot"><button class="sec" id="close">Close</button></div>
          </div>
        </div>
      </div>`;
    const close = () => (modal.innerHTML = "");
    const errEl = modal.querySelector("#err");
    modal.querySelector("#close").onclick = close;
    modal.querySelector(".overlay").onmousedown = (e) => {
      if (e.target.classList.contains("overlay")) close();
    };
    const opts = modal.querySelector("#opts");
    for (const p of POWER) {
      const b = document.createElement("button");
      b.className = `power ${p.danger ? "danger" : ""}`;
      b.innerHTML = `${icon(p.icon)}<div><b>${esc(p.title)}</b><span>${esc(p.desc)}</span></div>`;
      b.onclick = async () => {
        if (p.confirm && !confirm(p.confirm)) return;
        errEl.textContent = "";
        b.disabled = true;
        try {
          await this._hass.callService(p.domain, p.service);
          this._toast(p.ok);
          if (!p.stay) close();
          if (p.service !== "restart") this._load();
        } catch (e) {
          errEl.textContent = e.message || String(e);
        }
        b.disabled = false;
      };
      opts.appendChild(b);
    }
  }

  _live(cfg, type) {
    const states = this._hass.states;
    if (!cfg.name) return null;
    const guess = states[`${type}.${slug(cfg.name)}`];
    if (guess) return guess;
    for (const id in states) {
      if (states[id].attributes.friendly_name === cfg.name) return states[id];
    }
    return null;
  }

  _iconFor(cfg, type) {
    if (typeof cfg.icon === "string" && cfg.icon.startsWith("mdi:")) {
      return cfg.icon;
    }
    return (
      ICONS[cfg.device_class] ||
      (type === "binary_sensor" ? "mdi:toggle-switch" : "mdi:eye")
    );
  }

  _pill(live, cfg) {
    if (!live) return "";
    const st = live.state;
    const unit =
      cfg.unit_of_measurement || live.attributes.unit_of_measurement || "";
    let cls = "";
    if (st === "unavailable" || st === "unknown") cls = "bad";
    else if (st === "on") cls = "on";
    else if (st === "off") cls = "off";
    return `<span class="pill ${cls}">${esc(st)}${unit ? " " + esc(unit) : ""}</span>`;
  }

  _render() {
    this._banners();
    const all = [...this._data.managed, ...this._data.yaml];
    let liveCount = 0;
    for (const s of all) if (this._live(s.config, s.type)) liveCount++;
    this.querySelector("#stats").innerHTML = `
      <div class="stat"><b>${this._data.managed.length}</b><span>Managed</span></div>
      <div class="stat"><b>${this._data.yaml.length}</b><span>In configuration.yaml</span></div>
      <div class="stat"><b>${liveCount}</b><span>Live entities</span></div>`;

    const tabs = this.querySelector("#tabs");
    tabs.innerHTML = `
      <div class="tab ${this._tab === "managed" ? "on" : ""}" data-t="managed">
        Managed<small>${this._data.managed.length}</small></div>
      <div class="tab ${this._tab === "yaml" ? "on" : ""}" data-t="yaml">
        Config<small>${this._data.yaml.length}</small></div>`;
    tabs.querySelectorAll(".tab").forEach((t) => {
      t.onclick = () => {
        this._tab = t.dataset.t;
        this._render();
      };
    });

    const list = this.querySelector("#list");
    list.innerHTML = "";
    const items = (
      this._tab === "managed" ? this._data.managed : this._data.yaml
    ).filter((s) => !this._q || s.yaml.toLowerCase().includes(this._q));

    if (!items.length) {
      list.innerHTML = `<div class="empty">
        ${icon(this._tab === "managed" ? "mdi:playlist-plus" : "mdi:file-search-outline")}
        ${
          this._tab === "managed"
            ? "No managed sensors yet.<br>Click <b>Add sensor</b> and paste some YAML."
            : "Nothing found."
        }</div>`;
      return;
    }

    const grid = document.createElement("div");
    grid.className = "grid";
    list.appendChild(grid);

    for (const s of items) {
      const cfg = s.config;
      const live = this._live(cfg, s.type);
      const platform = (s.kind || "").includes("platform");
      const card = document.createElement("div");
      card.className = `card ${s.type === "binary_sensor" ? "binary" : ""} ${
        platform ? "platform" : ""
      }`;
      const name = cfg.name ?? cfg.platform ?? "(unnamed)";
      const chips = [
        `<span class="chip">${esc(s.kind ?? s.type)}</span>`,
        cfg.device_class &&
          `<span class="chip neutral">${esc(cfg.device_class)}</span>`,
        cfg.state_class &&
          `<span class="chip neutral">${esc(cfg.state_class)}</span>`,
        cfg.unit_of_measurement &&
          `<span class="chip neutral">${esc(cfg.unit_of_measurement)}</span>`,
      ].filter(Boolean);
      card.innerHTML = `
        <div class="top">
          <div class="tile">${icon(this._iconFor(cfg, s.type))}</div>
          <div class="title">
            <div class="name">${esc(name)}</div>
            <div class="sub">${esc(live ? live.entity_id : cfg.unique_id || "not loaded")}</div>
          </div>
          ${this._pill(live, cfg)}
        </div>
        <div class="chips">${chips.join("")}</div>
        <details><summary>Show YAML</summary><pre>${esc(s.yaml)}</pre></details>
        <div class="actions"></div>`;
      const actions = card.querySelector(".actions");
      const btn = (label, ic, cls, fn) => {
        const b = document.createElement("button");
        b.innerHTML = `${icon(ic)}${esc(label)}`;
        b.className = `sm ${cls}`;
        b.onclick = fn;
        actions.appendChild(b);
      };

      if (this._tab === "managed") {
        btn("Edit", "mdi:pencil", "edit", () =>
          this._edit({
            yaml: s.yaml,
            type: s.type,
            replace: { type: s.type, index: s.index },
          }),
        );
        btn("Delete", "mdi:delete-outline", "danger", async () => {
          if (!confirm(`Delete ${cfg.name}?`)) return;
          try {
            await this._hass.callWS({
              type: "ysm/delete",
              sensor_type: s.type,
              index: s.index,
            });
            this._toast("Sensor deleted");
          } catch (e) {
            this._toast("Delete failed: " + e.message, true);
          }
          this._load();
        });
      } else {
        if (s.loc) {
          btn("Edit", "mdi:pencil", "edit", () =>
            this._edit({ yaml: s.yaml, type: s.type, loc: s.loc }),
          );
          btn("Delete", "mdi:delete-outline", "danger", async () => {
            if (
              !confirm(
                `Delete ${name} from configuration.yaml?\n` +
                  "A backup is saved as configuration.yaml.ysm.bak.",
              )
            )
              return;
            try {
              const r = await this._hass.callWS({
                type: "ysm/config_delete",
                loc: s.loc,
              });
              this._toast(
                r.restart ? "Deleted. Restart needed" : "Sensor deleted",
              );
            } catch (e) {
              this._toast("Delete failed: " + e.message, true);
            }
            this._load();
          });
        }
        if (s.copyable) {
          btn("Copy to managed", "mdi:content-copy", "copy", () =>
            this._edit({ yaml: s.yaml, type: s.type }),
          );
        }
      }
      if (!actions.children.length) actions.remove();
      grid.appendChild(card);
    }
  }

  _edit({ yaml = "", type = "sensor", replace, loc }) {
    const modal = this.querySelector("#modal");
    const title = loc
      ? "Edit sensor in configuration.yaml"
      : replace
        ? "Edit sensor"
        : "Add sensors";
    modal.innerHTML = `
      <div class="overlay">
        <div class="modal">
          <div class="mhead">${icon(replace || loc ? "mdi:pencil" : "mdi:plus-circle")}
            ${esc(title)}</div>
          <div class="mbody">
            <textarea id="y" spellcheck="false" placeholder="${esc(PLACEHOLDER)}">${esc(yaml)}</textarea>
            <div class="hint">
              ${
                loc
                  ? `Only this entry is rewritten. A backup is saved as
                     <code>configuration.yaml.ysm.bak</code> and the change is
                     rolled back if Home Assistant rejects it. Comments inside
                     the entry are lost.`
                  : `Accepts a single sensor, a list, <code>sensor:</code> /
                     <code>binary_sensor:</code> blocks, or a full
                     <code>template:</code> block. Quote templates or use a
                     <code>|</code> block. Pasted text is cleaned up
                     automatically.`
              }
            </div>
            <div class="row" id="typerow" ${loc ? 'style="display:none"' : ""}>
              <span class="hint">Entries without a wrapper are:</span>
              <select id="t">
                <option value="sensor">sensor</option>
                <option value="binary_sensor">binary_sensor</option>
              </select>
            </div>
            <div class="err" id="err"></div>
            <div class="foot">
              <button class="sec" id="format">${icon("mdi:auto-fix")}Format</button>
              <button class="sec" id="cancel">Cancel</button>
              <button id="save">${icon("mdi:content-save")}Save</button>
            </div>
          </div>
        </div>
      </div>`;
    const ta = modal.querySelector("#y");
    const errEl = modal.querySelector("#err");
    modal.querySelector("#t").value = type;
    ta.focus();
    ta.onkeydown = (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        document.execCommand("insertText", false, "  ");
      }
    };

    const format = async (quiet) => {
      try {
        const r = await this._hass.callWS({
          type: "ysm/format",
          yaml: ta.value,
        });
        ta.value = r.yaml;
        errEl.textContent =
          !quiet && r.error ? "Cleaned, but: " + r.error : "";
        if (!quiet && !r.error) this._toast("Formatted");
      } catch (e) {
        if (!quiet) errEl.textContent = e.message;
      }
    };
    modal.querySelector("#format").onclick = () => format(false);
    ta.addEventListener("paste", () => setTimeout(() => format(true), 0));

    const close = () => (modal.innerHTML = "");
    modal.querySelector("#cancel").onclick = close;
    modal.querySelector(".overlay").onmousedown = (e) => {
      if (e.target.classList.contains("overlay")) close();
    };

    const saveBtn = modal.querySelector("#save");
    saveBtn.onclick = async () => {
      errEl.textContent = "";
      saveBtn.disabled = true;
      try {
        if (loc) {
          const r = await this._hass.callWS({
            type: "ysm/config_save",
            yaml: ta.value,
            loc,
          });
          close();
          this._toast(r.restart ? "Saved. Restart needed" : "Saved");
        } else {
          const r = await this._hass.callWS({
            type: "ysm/save",
            yaml: ta.value,
            default_type: modal.querySelector("#t").value,
            ...(replace ? { replace } : {}),
          });
          close();
          this._tab = "managed";
          this._toast(`Saved ${r.saved} sensor${r.saved === 1 ? "" : "s"}`);
        }
        this._load();
      } catch (e) {
        errEl.textContent = e.message || String(e);
        saveBtn.disabled = false;
      }
    };
  }
}
customElements.define("ysm-panel", YsmPanel);
