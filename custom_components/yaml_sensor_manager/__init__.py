"""Custom Sensor Viewer."""
from __future__ import annotations

import os
import re
import textwrap
from collections.abc import Mapping
from pathlib import Path

import voluptuous as vol
import yaml
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml
from homeassistant.util.yaml.loader import Secrets, parse_yaml

DOMAIN = "yaml_sensor_manager"
DOMAIN_TEMPLATE = "template"
TYPES = ("sensor", "binary_sensor")
VERSION = "0.4.1"


def _jsonable(obj):
    """Convert HA's YAML node types into plain Python types."""
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj)
    return str(obj)


class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", str(data), style=style
    )


_Dumper.add_multi_representer(str, _str_rep)


def _dump(data) -> str:
    return yaml.dump(
        _jsonable(data),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _secrets(hass) -> Secrets:
    return Secrets(Path(hass.config.config_dir))


_REPLACEMENTS = {
    "\u00a0": " ", "\u2007": " ", "\u202f": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
}

_LIST_ITEM = re.compile(r"^-( +)[\w\"'][^:]*:")


def _restore_first_indent(text: str) -> str:
    """Fix pastes where the first line lost its leading whitespace.

    Example: "- name: x" at column 0 followed by "        unique_id: y".
    """
    lines = text.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first is None:
        return text
    head = lines[first]
    match = _LIST_ITEM.match(head)
    if not match:
        return text
    # Column where the first key starts, relative to the dash.
    key_offset = 1 + len(match.group(1))
    # Indent of the sibling keys (ignore other "- " lines).
    rest = [
        len(ln) - len(ln.lstrip(" "))
        for ln in lines[first + 1:]
        if ln.strip() and not ln.lstrip(" ").startswith("-")
    ]
    if not rest:
        return text
    missing = min(rest) - key_offset
    if missing > 0:
        lines[first] = " " * missing + head
    return "\n".join(lines)


def _clean_text(text: str) -> str:
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "  ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _restore_first_indent(text)
    return textwrap.dedent(text).strip("\n") + "\n"


def _format(hass, text: str) -> dict:
    cleaned = _clean_text(text)
    try:
        data = parse_yaml(cleaned, _secrets(hass))
        if data is None:
            return {"yaml": cleaned}
        return {"yaml": _dump(data)}
    except Exception as err:  # noqa: BLE001
        # Not valid YAML yet (e.g. unquoted template): return cleaned text
        return {"yaml": cleaned, "error": str(err)}


def _managed_path(hass: HomeAssistant) -> str:
    return hass.config.path("packages", "ysm.yaml")


def _read_managed(hass) -> dict[str, list]:
    out = {t: [] for t in TYPES}
    path = _managed_path(hass)
    if not os.path.exists(path):
        return out
    data = load_yaml(path, _secrets(hass)) or {}
    for block in data.get("template", []) or []:
        for t in TYPES:
            out[t].extend(_jsonable(block.get(t, []) or []))
    return out


def _write_managed(hass, managed: dict[str, list]) -> None:
    path = Path(_managed_path(hass))
    path.parent.mkdir(parents=True, exist_ok=True)
    block = {t: managed[t] for t in TYPES if managed[t]}
    content = {"template": [block]} if block else {}
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Managed by Custom Sensor Viewer\n")
        if content:
            f.write(_dump(content))


def _load_config_yaml(hass) -> dict:
    path = Path(hass.config.path("configuration.yaml"))
    with open(path, encoding="utf-8") as f:
        return parse_yaml(f, _secrets(hass)) or {}


def _scan_config(hass) -> list[dict]:
    cfg = _load_config_yaml(hass)
    items = []

    def add(kind, typ, entry, copyable):
        entry = _jsonable(entry)
        items.append({
            "kind": kind,
            "type": typ,
            "config": entry,
            "yaml": _dump(entry),
            "copyable": copyable,
        })

    for domain in TYPES:
        val = cfg.get(domain) or []
        for e in val if isinstance(val, list) else [val]:
            if isinstance(e, Mapping):
                add(f"{domain} (platform)", domain, e, False)

    tpl = cfg.get("template") or []
    for block in tpl if isinstance(tpl, list) else [tpl]:
        if not isinstance(block, Mapping):
            continue
        for domain in TYPES:
            for e in block.get(domain, []) or []:
                if isinstance(e, Mapping):
                    add(f"template {domain}", domain, e, True)
    return items


def _managed_view(managed: dict[str, list]) -> list[dict]:
    out = []
    for t in TYPES:
        for i, s in enumerate(managed[t]):
            s = _jsonable(s)
            out.append({
                "type": t,
                "index": i,
                "config": s,
                "yaml": _dump(s),
            })
    return out


def _normalize(data, default_type: str) -> dict[str, list]:
    """Accept bare entries, lists, sensor:/binary_sensor: or template:."""
    result = {t: [] for t in TYPES}

    def walk(node, dtype):
        if isinstance(node, list):
            for n in node:
                walk(n, dtype)
        elif isinstance(node, Mapping):
            if "template" in node:
                walk(node["template"], dtype)
                return
            wrapped = False
            for t in TYPES:
                if t in node:
                    walk(node[t], t)
                    wrapped = True
            if not wrapped:
                result[dtype].append(_jsonable(node))

    walk(data, default_type)
    return result


def _same(a: dict, b: dict) -> bool:
    if a.get("unique_id") and b.get("unique_id"):
        return a["unique_id"] == b["unique_id"]
    return a.get("name") == b.get("name")


def _save(hass, text: str, default_type: str, replace: dict | None) -> int:
    try:
        data = parse_yaml(_clean_text(text), _secrets(hass))
    except Exception as err:  # noqa: BLE001
        raise ValueError(
            f"Invalid YAML: {err}. Tip: wrap templates in quotes, "
            "or use a | block."
        ) from err
    new = _normalize(data, default_type)
    count = sum(len(v) for v in new.values())
    if not count:
        raise ValueError("No sensors found in the pasted YAML.")
    for items in new.values():
        for s in items:
            if "name" not in s or "state" not in s:
                raise ValueError("Every sensor needs a name and a state.")

    managed = _read_managed(hass)
    if replace:
        try:
            managed[replace["type"]].pop(replace["index"])
        except IndexError as err:
            raise ValueError("The original sensor no longer exists.") from err
    for t, items in new.items():
        for s in items:
            existing = managed[t]
            for i, old in enumerate(existing):
                if _same(old, s):
                    existing[i] = s
                    break
            else:
                existing.append(s)
    _write_managed(hass, managed)
    return count


def _delete(hass, typ: str, index: int) -> None:
    managed = _read_managed(hass)
    try:
        managed[typ].pop(index)
    except IndexError as err:
        raise ValueError("Sensor not found.") from err
    _write_managed(hass, managed)


async def _reload(hass) -> None:
    await hass.services.async_call(DOMAIN_TEMPLATE, "reload", blocking=True)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "ysm/list"})
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    try:
        yaml_items = await hass.async_add_executor_job(_scan_config, hass)
        managed = await hass.async_add_executor_job(_read_managed, hass)
        managed_view = _managed_view(managed)
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "load_failed", str(err))
        return
    connection.send_result(msg["id"], {
        "yaml": yaml_items,
        "managed": managed_view,
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/save",
    vol.Required("yaml"): str,
    vol.Optional("default_type", default="sensor"): vol.In(TYPES),
    vol.Optional("replace"): {
        vol.Required("type"): vol.In(TYPES),
        vol.Required("index"): int,
    },
})
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    try:
        count = await hass.async_add_executor_job(
            _save, hass, msg["yaml"], msg["default_type"], msg.get("replace")
        )
        await _reload(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "save_failed", str(err))
        return
    connection.send_result(msg["id"], {"saved": count})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/delete",
    vol.Required("sensor_type"): vol.In(TYPES),
    vol.Required("index"): int,
})
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    try:
        await hass.async_add_executor_job(
            _delete, hass, msg["sensor_type"], msg["index"]
        )
        await _reload(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "delete_failed", str(err))
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/format",
    vol.Required("yaml"): str,
})
@websocket_api.async_response
async def ws_format(hass, connection, msg):
    result = await hass.async_add_executor_job(_format, hass, msg["yaml"])
    connection.send_result(msg["id"], result)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_format)

    www = str(Path(__file__).parent / "www")
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/ysm_static", www, False)]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="ysm-panel",
        frontend_url_path="ysm",
        module_url=f"/ysm_static/panel.js?v={VERSION}",
        sidebar_title="Sensor Viewer",
        sidebar_icon="mdi:code-braces",
        require_admin=True,
    )
    return True
