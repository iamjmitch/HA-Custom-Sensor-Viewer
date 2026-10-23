class YsmPanel extends HTMLElement {
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
  }

  async _init() {
    this.innerHTML = `
      <style>
        .wrap{padding:16px;max-width:1000px;margin:auto;font-family:sans-serif;
          color:var(--primary-text-color)}
        .card{background:var(--card-background-color);border-radius:8px;
          padding:12px 16px;margin:8px 0;box-shadow:var(--ha-card-box-shadow,0 1px 3px #0003)}
        pre{margin:4px 0;overflow:auto;font-size:12px}
        input{width:100%;padding:6px;margin:2px 0 8px;box-sizing:border-box}
        button{padding:6px 12px;margin-right:6px;cursor:pointer}
        .tag{font-size:11px;opacity:.7}
        h2{margin-top:24px}
      </style>
      <div class="wrap">
        <h1>YAML Sensors</h1>
        <input id="filter" placeholder="Filter...">
        <h2>Managed (editable)</h2>
        <button id="add">+ Add sensor</button>
        <div id="form"></div>
        <div id="managed"></div>
        <h2>From configuration.yaml (read-only)</h2>
        <div id="yaml"></div>
      </div>`;
    this.querySelector("#add").onclick = () => this._form();
    this.querySelector("#filter").oninput = () => this._render();
    await this._load();
  }

  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "ysm/list" });
    } catch (e) {
      alert("Load failed: " + e.message);
      this._data = { yaml: [], managed: [] };
    }
    this._render();
  }

  _match(obj) {
    const f = this.querySelector("#filter").value.toLowerCase();
    return !f || JSON.stringify(obj).toLowerCase().includes(f);
  }

  _render() {
    const m = this.querySelector("#managed");
    const y = this.querySelector("#yaml");
    m.innerHTML = "";
    y.innerHTML = "";
    this._data.managed.filter((s) => this._match(s)).forEach((s) => {
      const d = document.createElement("div");
      d.className = "card";
      d.innerHTML = `<b>${s.name}</b><pre>${JSON.stringify(s, null, 2)}</pre>
        <button class="e">Edit</button><button class="d">Delete</button>`;
      d.querySelector(".e").onclick = () => this._form(s);
      d.querySelector(".d").onclick = async () => {
        if (!confirm(`Delete ${s.name}?`)) return;
        await this._hass.callWS({ type: "ysm/delete", name: s.name });
        this._load();
      };
      m.appendChild(d);
    });
    this._data.yaml.filter((s) => this._match(s)).forEach((s) => {
      const d = document.createElement("div");
      d.className = "card";
      d.innerHTML = `<span class="tag">${s.kind}</span>
        <pre>${JSON.stringify(s.config, null, 2)}</pre>
        <button>Copy to managed</button>`;
      d.querySelector("button").onclick = () => {
        if (s.kind.startsWith("template")) this._form(s.config, true);
        else alert("Only template sensors can be copied.");
      };
      y.appendChild(d);
    });
  }

  _form(s = {}, isCopy = false) {
    const fields = ["name", "state", "unit_of_measurement", "device_class",
      "state_class", "icon", "unique_id"];
    const box = this.querySelector("#form");
    box.innerHTML = `<div class="card">${fields
      .map((f) => `<label>${f}</label><input data-f="${f}"
        value="${(s[f] ?? "").toString().replace(/"/g, "&quot;")}">`)
      .join("")}
      <button id="save">Save</button><button id="cancel">Cancel</button></div>`;
    box.querySelector("#cancel").onclick = () => (box.innerHTML = "");
    box.querySelector("#save").onclick = async () => {
      const sensor = {};
      box.querySelectorAll("input").forEach((i) => (sensor[i.dataset.f] = i.value));
      try {
        await this._hass.callWS({
          type: "ysm/save",
          sensor,
          ...(s.name && !isCopy ? { original_name: s.name } : {}),
        });
        box.innerHTML = "";
        this._load();
      } catch (e) {
        alert("Save failed: " + e.message);
      }
    };
  }
}
customElements.define("ysm-panel", YsmPanel);
