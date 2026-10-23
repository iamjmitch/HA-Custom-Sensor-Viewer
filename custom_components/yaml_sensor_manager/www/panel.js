const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

const PLACEHOLDER = `# Paste a sensor, a list, or a whole template: block
- name: Example Double
  unique_id: example_double
  unit_of_measurement: "W"
  state: "{{ states('sensor.x') | float(0) * 2 }}"`;

const CSS = `
<style>
  :host, ysm-panel { display:block; }
  .wrap{padding:16px;max-width:900px;margin:0 auto;box-sizing:border-box;
    color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,sans-serif)}
  .head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  .head h1{flex:1;margin:0;font-size:24px;font-weight:500}
  button{font:inherit;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;
    background:var(--primary-color);color:var(--text-primary-color,#fff)}
  button.sec{background:transparent;color:var(--primary-text-color);
    border:1px solid var(--divider-color)}
  button.danger{background:var(--error-color,#db4437)}
  button.sm{padding:5px 10px;font-size:13px}
  input.search{width:100%;box-sizing:border-box;padding:10px 12px;font:inherit;
    border-radius:8px;border:1px solid var(--divider-color);
    background:var(--card-background-color);color:var(--primary-text-color)}
  .tabs{display:flex;gap:6px;margin:12px 0}
  .tab{padding:6px 14px;border-radius:16px;cursor:pointer;font-size:14px;
    border:1px solid var(--divider-color)}
  .tab.on{background:var(--primary-color);color:var(--text-primary-color,#fff);
    border-color:var(--primary-color)}
  .card{background:var(--card-background-color);border-radius:12px;padding:14px 16px;
    margin:10px 0;box-shadow:var(--ha-card-box-shadow,0 1px 4px #0003)}
  .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .name{font-weight:500;font-size:16px;flex:1;word-break:break-word}
  .badge{font-size:11px;padding:2px 8px;border-radius:10px;
    background:var(--secondary-background-color);color:var(--secondary-text-color)}
  .state{font-size:13px;padding:2px 8px;border-radius:10px;
    background:var(--primary-color);color:var(--text-primary-color,#fff)}
  .meta{font-size:12px;color:var(--secondary-text-color);margin-top:4px}
  details{margin-top:8px}
  summary{cursor:pointer;font-size:13px;color:var(--secondary-text-color)}
  pre{margin:6px 0 0;padding:10px;border-radius:8px;overflow:auto;font-size:12px;
    background:var(--secondary-background-color)}
  .actions{display:flex;gap:6px;margin-top:10px}
  .empty{text-align:center;padding:32px;color:var(--secondary-text-color)}
  .banner{padding:10px 12px;border-radius:8px;margin:8px 0;
    background:var(--error-color,#db4437);color:#fff}
  .overlay{position:fixed;inset:0;background:#0009;z-index:10;display:flex;
    align-items:center;justify-content:center;padding:12px}
  .modal{background:var(--card-background-color);border-radius:14px;padding:18px;
    width:100%;max-width:640px;max-height:95vh;overflow:auto;box-sizing:border-box}
  .modal h2{margin:0 0 10px}
  textarea{width:100%;box-sizing:border-box;height:300px;padding:10px;resize:vertical;
    font-family:monospace;font-size:13px;border-radius:8px;tab-size:2;
    border:1px solid var(--divider-color);
    background:var(--secondary-background-color);color:var(--primary-text-color)}
  select{font:inherit;padding:6px;border-radius:6px;
    background:var(--secondary-background-color);color:var(--primary-text-color);
    border:1px solid var(--divider-color)}
  .hint{font-size:12px;color:var(--secondary-text-color);margin:8px 0}
  .err{color:var(--error-color,#db4437);font-size:13px;margin:8px 0;white-space:pre-wrap}
  .foot{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
</style>`;

class YsmPanel extends HTMLElement {
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
  }

  _init() {
    this._tab = "managed";
    this._q = "";
    this._data = { yaml: [], managed: [] };
    this.innerHTML = `${CSS}
      <div class="wrap">
        <div class="head">
          <h1>Custom Sensor Viewer</h1>
          <button class="sec" id="refresh">Refresh</button>
          <button id="add">+ Add sensor</button>
        </div>
        <input class="search" id="q" placeholder="Search sensors...">
        <div class="tabs" id="tabs"></div>
        <div id="banner"></div>
        <div id="list"></div>
      </div>
      <div id="modal"></div>`;
    this.querySelector("#add").onclick = () => this._edit({});
    this.querySelector("#refresh").onclick = () => this._load();
    this.querySelector("#q").oninput = (e) => {
      this._q = e.target.value.toLowerCase();
      this._render();
    };
    this._load();
  }

  async _load() {
    const banner = this.querySelector("#banner");
    banner.innerHTML = "";
    try {
      this._data = await this._hass.callWS({ type: "ysm/list" });
    } catch (e) {
      banner.innerHTML = `<div class="banner">Load failed: ${esc(e.message)}</div>`;
    }
    this._render();
  }

  _live(name) {
    const states = this._hass.states;
    for (const id in states) {
      if (states[id].attributes.friendly_name === name) return states[id];
    }
    return null;
  }

  _render() {
    const m = this._data.managed.length;
    const y = this._data.yaml.length;
    const tabs = this.querySelector("#tabs");
    tabs.innerHTML = `
      <div class="tab ${this._tab === "managed" ? "on" : ""}" data-t="managed">
        Managed (${m})</div>
      <div class="tab ${this._tab === "yaml" ? "on" : ""}" data-t="yaml">
        configuration.yaml (${y})</div>`;
    tabs.querySelectorAll(".tab").forEach((t) => {
      t.onclick = () => {
        this._tab = t.dataset.t;
        this._render();
      };
    });

    const list = this.querySelector("#list");
    list.innerHTML = "";
    const items = (this._tab === "managed" ? this._data.managed : this._data.yaml)
      .filter((s) => !this._q || s.yaml.toLowerCase().includes(this._q));

    if (!items.length) {
      list.innerHTML = `<div class="empty">${
        this._tab === "managed"
          ? "No managed sensors yet. Click “+ Add sensor” and paste some YAML."
          : "Nothing found."
      }</div>`;
      return;
    }

    for (const s of items) {
      const cfg = s.config;
      const live = this._live(cfg.name);
      const card = document.createElement("div");
      card.className = "card";
      const unit = cfg.unit_of_measurement || live?.attributes.unit_of_measurement || "";
      card.innerHTML = `
        <div class="row">
          <span class="name">${esc(cfg.name ?? "(unnamed)")}</span>
          <span class="badge">${esc(s.kind ?? s.type)}</span>
          ${live ? `<span class="state">${esc(live.state)} ${esc(unit)}</span>` : ""}
        </div>
        <div class="meta">${[
          cfg.unique_id && `id: ${esc(cfg.unique_id)}`,
          cfg.device_class && `class: ${esc(cfg.device_class)}`,
          live && esc(live.entity_id),
        ].filter(Boolean).join(" · ")}</div>
        <details><summary>YAML</summary><pre>${esc(s.yaml)}</pre></details>
        <div class="actions"></div>`;
      const actions = card.querySelector(".actions");
      const btn = (label, cls, fn) => {
        const b = document.createElement("button");
        b.textContent = label;
        b.className = `sm ${cls}`;
        b.onclick = fn;
        actions.appendChild(b);
      };
      if (this._tab === "managed") {
        btn("Edit", "", () =>
          this._edit({ yaml: s.yaml, type: s.type, replace: { type: s.type, index: s.index } }));
        btn("Delete", "danger", async () => {
          if (!confirm(`Delete ${cfg.name}?`)) return;
          try {
            await this._hass.callWS({
              type: "ysm/delete", sensor_type: s.type, index: s.index,
            });
          } catch (e) {
            alert("Delete failed: " + e.message);
          }
          this._load();
        });
      } else if (s.copyable) {
        btn("Copy to managed", "sec", () => this._edit({ yaml: s.yaml, type: s.type }));
      }
      list.appendChild(card);
    }
  }

  _edit({ yaml = "", type = "sensor", replace }) {
    const modal = this.querySelector("#modal");
    modal.innerHTML = `
      <div class="overlay">
        <div class="modal">
          <h2>${replace ? "Edit sensor" : "Add sensors"}</h2>
          <textarea id="y" spellcheck="false" placeholder="${esc(PLACEHOLDER)}">${esc(yaml)}</textarea>
          <div class="hint">
            Accepts a single sensor, a list, <code>sensor:</code> /
            <code>binary_sensor:</code> blocks, or a full <code>template:</code> block.
            Quote templates or use a <code>|</code> block.
          </div>
          <div class="row">
            <span class="hint">Entries without a wrapper are:</span>
            <select id="t">
              <option value="sensor">sensor</option>
              <option value="binary_sensor">binary_sensor</option>
            </select>
          </div>
          <div class="err" id="err"></div>
          <div class="foot">
            <button class="sec" id="cancel">Cancel</button>
            <button id="save">Save</button>
          </div>
        </div>
      </div>`;
    const ta = modal.querySelector("#y");
    modal.querySelector("#t").value = type;
    ta.focus();
    ta.onkeydown = (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        document.execCommand("insertText", false, "  ");
      }
    };
    const close = () => (modal.innerHTML = "");
    modal.querySelector("#cancel").onclick = close;
    modal.querySelector(".overlay").onmousedown = (e) => {
      if (e.target.classList.contains("overlay")) close();
    };
    modal.querySelector("#save").onclick = async () => {
      const err = modal.querySelector("#err");
      err.textContent = "";
      try {
        await this._hass.callWS({
          type: "ysm/save",
          yaml: ta.value,
          default_type: modal.querySelector("#t").value,
          ...(replace ? { replace } : {}),
        });
        close();
        this._tab = "managed";
        this._load();
      } catch (e) {
        err.textContent = e.message;
      }
    };
  }
}
customElements.define("ysm-panel", YsmPanel);
