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
    display:fl
