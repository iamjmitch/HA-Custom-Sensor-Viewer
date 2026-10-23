"""YAML Sensor Manager."""
from __future__ import annotations

import os
from pathlib import Path

import voluptuous as vol
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import dump, load_yaml

DOMAIN = "yaml_sensor_manager"
FIELDS = ("name", "state", "unit_of_measurement", "device_class",
          "state_class", "icon", "unique_id")


def _managed_path(hass: HomeAssistant) -> str:
    return hass.config.path("packages", "ysm.yaml")


def _read_managed(hass) -> list[dict]:
    path = _managed_path(hass)
    if not os.path.exists(path):
        return []
    data = load_yaml(path) or {}
    out = []
    for block in data.get("template", []) or []:
        out.extend(block.get("sensor", []) or [])
    return out


def _write_managed(hass, sensors: list[dict]) -> None:
    path = _managed_path(hass)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    content = {"template": [{"sensor": sensors}]} if sensors else {}
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Managed by YAML Sensor Manager\n" + dump(content))


def _scan_config(hass) -> list[dict]:
    cfg = load_yaml(hass.config.path("configuration.yaml")) or {}
    items = []

    def add(kind, entry):
        items.append({"kind": kind, "config": entry})

    for domain in ("sensor", "binary_sensor"):
        val = cfg.get(domain) or []
        for e in val if isinstance(val, list) else [val]:
            if isinstance(e, dict):
                add(f"{domain} (platform)", e)
    tpl = cfg.get("template") or []
    for block in tpl if isinstance(tpl, list) else [tpl]:
        if not isinstance(block, dict):
            continue
        for domain in ("sensor", "binary_sensor"):
            for e in block.get(domain, []) or []:
                add(f"template {domain}", e)
    return items


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj if isinstance(obj, (str, int, float, bool, type(None))) else str(obj)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "ysm/list"})
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    try:
        yaml_items = await hass.async_add_executor_job(_scan_config, hass)
    except Exception as err:  # noqa: BLE001
        yaml_items = []
        connection.send_error(msg["id"], "scan_failed", str(err))
        return
    managed = await hass.async_add_executor_job(_read_managed, hass)
    connection.send_result(msg["id"], {
        "yaml": _jsonable(yaml_items),
        "managed": _jsonable(managed),
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/save",
    vol.Optional("original_name"): str,
    vol.Required("sensor"): dict,
})
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    sensor = {k: v for k, v in msg["sensor"].items()
              if k in FIELDS and v not in ("", None)}
    if "name" not in sensor or "state" not in sensor:
        connection.send_error(msg["id"], "invalid", "name and state required")
        return
    sensors = await hass.async_add_executor_job(_read_managed, hass)
    orig = msg.get("original_name", sensor["name"])
    for i, s in enumerate(sensors):
        if s.get("name") == orig:
            sensors[i] = sensor
            break
    else:
        sensors.append(sensor)
    await hass.async_add_executor_job(_write_managed, hass, sensors)
    await hass.services.async_call(DOMAIN_TEMPLATE, "reload", blocking=True)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/delete",
    vol.Required("name"): str,
})
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    sensors = await hass.async_add_executor_job(_read_managed, hass)
    sensors = [s for s in sensors if s.get("name") != msg["name"]]
    await hass.async_add_executor_job(_write_managed, hass, sensors)
    await hass.services.async_call(DOMAIN_TEMPLATE, "reload", blocking=True)
    connection.send_result(msg["id"], {"ok": True})


DOMAIN_TEMPLATE = "template"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)

    www = str(Path(__file__).parent / "www")
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/ysm_static", www, False)]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="ysm-panel",
        frontend_url_path="ysm",
        module_url="/ysm_static/panel.js",
        sidebar_title="YAML Sensors",
        sidebar_icon="mdi:code-braces",
        require_admin=True,
    )
    return True
