"""Custom Sensor Viewer."""
from __future__ import annotations

import os
import re
import shutil
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
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

DOMAIN = "yaml_sensor_manager"
DOMAIN_TEMPLATE = "template"
TYPES = ("sensor", "binary_sensor")
VERSION = "0.5.0"

LOC = vol.Schema({
    vol.Required("section"): vol.In(("template", "platform")),
    vol.Required("type"): vol.In(TYPES),
    vol.Optional("block", default=0): int,
    vol.Required("index"): int,
})


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


# --------------------------------------------------------------------------
# Text cleanup
# --------------------------------------------------------------------------

_REPLACEMENTS = {
    "\u00a0": " ", "\u2007": " ", "\u202f": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
}

_LIST_ITEM = re.compile(r"^-( +)[\w\"'][^:]*:")


def _restore_first_indent(text: str) -> str:
    """Fix pastes where the first line lost its leading whitespace."""
    lines = text.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first is None:
        return text
    head = lines[first]
    match = _LIST_ITEM.match(head)
    if not match:
        return text
    key_offset = 1 + len(match.group(1))
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
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _restore_first_indent(text)
    return textwrap.dedent(text).strip("\n") + "\n"


def _parse_text(hass, text: str):
    try:
        return parse_yaml(_clean_text(text), _secrets(hass))
    except Exception as err: # noqa: BLE001
        raise ValueError(
            f"Invalid YAML: {err}. Tip: wrap templates in quotes, "
            "or use a | block."
        ) from err


def _format(hass, text: str) -> dict:
    cleaned = _clean_text(text)
    try:
        data = parse_yaml(cleaned, _secrets(hass))
        if data is None:
            return {"yaml": cleaned}
        return {"yaml": _dump(data)}
    except Exception as err: # noqa: BLE001
        return {"yaml": cleaned, "error": str(err)}


# --------------------------------------------------------------------------
# Restart tracking (in memory, so a restart clears it automatically)
# --------------------------------------------------------------------------

def _need_restart(hass, reason: str) -> None:
    reasons = hass.data.setdefault(DOMAIN, [])
    if reason not in reasons:
        reasons.append(reason)


def _restart_reasons(hass) -> list[str]:
    return list(hass.data.get(DOMAIN, []))


# --------------------------------------------------------------------------
# Managed file (packages/ysm.yaml)
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# configuration.yaml scanning
# --------------------------------------------------------------------------

def _config_path(hass) -> Path:
    return Path(hass.config.path("configuration.yaml"))


def _load_config_yaml(hass) -> dict:
    with open(_config_path(hass), encoding="utf-8") as f:
        return parse_yaml(f, _secrets(hass)) or {}


def _scan_config(hass) -> tuple[list[dict], bool]:
    cfg = _load_config_yaml(hass)
    items = []

    def add(kind, typ, entry, copyable, loc):
        entry = _jsonable(entry)
        items.append({
            "kind": kind,
            "type": typ,
            "config": entry,
            "yaml": _dump(entry),
            "copyable": copyable,
            "loc": loc,
        })

    for domain in TYPES:
        val = cfg.get(domain) or []
        for i, e in enumerate(val if isinstance(val, list) else [val]):
            if isinstance(e, Mapping):
                add(
                    f"{domain} (platform)", domain, e, False,
                    {"section": "platform", "type": domain,
                     "block": 0, "index": i},
                )

    tpl = cfg.get("template") or []
    for bi, block in enumerate(tpl if isinstance(tpl, list) else [tpl]):
        if not isinstance(block, Mapping):
            continue
        for domain in TYPES:
            for i, e in enumerate(block.get(domain, []) or []):
                if isinstance(e, Mapping):
                    add(
                        f"template {domain}", domain, e, True,
                        {"section": "template", "type": domain,
                         "block": bi, "index": i},
                    )

    # Is packages/ysm.yaml actually being loaded?
    core = cfg.get("homeassistant")
    pk = core.get("packages") if isinstance(core, Mapping) else None
    loaded = isinstance(pk, Mapping) and "ysm" in pk
    packages_ok = loaded or not os.path.exists(_managed_path(hass))
    return items, packages_ok


# --------------------------------------------------------------------------
# configuration.yaml editing (line surgery, keeps comments/!include/etc.)
# --------------------------------------------------------------------------

def _map_get(node, key):
    if not isinstance(node, MappingNode):
        return None
    for k, v in node.value:
        if isinstance(k, ScalarNode) and k.value == key:
            return v
    return None


def _locate(root, loc):
    if loc["section"] == "platform":
        seq = _map_get(root, loc["type"])
    else:
        tpl = _map_get(root, "template")
        blocks = tpl.value if isinstance(tpl, SequenceNode) else [tpl]
        if loc["block"] >= len(blocks):
            return None
        seq = _map_get(blocks[loc["block"]], loc["type"])
    if not isinstance(seq, SequenceNode) or loc["index"] >= len(seq.value):
        return None
    return seq.value[loc["index"]]


def _span(lines: list[str], node) -> tuple[int, int]:
    start = node.start_mark.line
    end = node.end_mark.line
    if node.end_mark.column > 0:
        end += 1
    end = min(end, len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return start, end


def _single_entry(hass, text: str, loc: dict) -> dict:
    data = _parse_text(hass, text)
    if loc["section"] == "platform":
        items = data if isinstance(data, list) else [data]
        if len(items) != 1 or not isinstance(items[0], Mapping):
            raise ValueError("Edit exactly one sensor here.")
        return _jsonable(items[0])
    new = _normalize(data, loc["type"])
    entries = [(t, s) for t, items in new.items() for s in items]
    if len(entries) != 1:
        raise ValueError("Edit exactly one sensor here.")
    typ, entry = entries[0]
    if typ != loc["type"]:
        raise ValueError(f"This entry must stay a {loc['type']}.")
    if "name" not in entry or "state" not in entry:
        raise ValueError("Every sensor needs a name and a state.")
    return entry


def _edit_config(hass, loc: dict, text: str | None) -> None:
    """Replace (text given) or delete (text None) one config entry."""
    path = _config_path(hass)
    original = path.read_text(encoding="utf-8")
    try:
        root = yaml.compose(original, Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        raise ValueError(f"Can't read configuration.yaml: {err}") from err
    node = _locate(root, loc)
    if node is None:
        raise ValueError(
            "Couldn't find this entry as a plain list item in "
            "configuration.yaml (it may come from an !include file). "
            "Refresh and try again."
        )
    lines = original.split("\n")
    start, end = _span(lines, node)
    prefix = lines[start][: node.start_mark.column]
    if prefix.strip() != "-":
        raise ValueError("This entry's layout isn't supported for editing.")

    if text is None:
        new_lines = lines[:start] + lines[end:]
    else:
        entry = _single_entry(hass, text, loc)
        pad = " " * (len(prefix) - len(prefix.lstrip(" ")))
        block = [
            pad + ln if ln else ln
            for ln in _dump([entry]).rstrip("\n").split("\n")
        ]
        new_lines = lines[:start] + block + lines[end:]

    new_text = "\n".join(new_lines)
    try:
        yaml.compose(new_text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        raise ValueError(f"The result wouldn't be valid YAML: {err}") from err

    shutil.copy2(path, path.with_name("configuration.yaml.ysm.bak"))
    path.write_text(new_text, encoding="utf-8")


def _restore_config(hass) -> None:
    path = _config_path(hass)
    shutil.copy2(path.with_name("configuration.yaml.ysm.bak"), path)


async def _change_config(hass, loc: dict, text: str | None) -> dict:
    await hass.async_add_executor_job(_edit_config, hass, loc, text)
    try:
        await hass.services.async_call(
            "homeassistant", "check_config", blocking=True
        )
    except Exception as err: # noqa: BLE001
        await hass.async_add_executor_job(_restore_config, hass)
        raise ValueError(
            f"Home Assistant rejected the change, so it was rolled back: {err}"
        ) from err
    restart = loc["section"] == "platform"
    if restart:
        _need_restart(
            hass, "A sensor platform in configuration.yaml was changed."
        )
    else:
        await _reload(hass)
    return {"saved": 1, "ok": True, "restart": restart}


# --------------------------------------------------------------------------
# Managed sensors
# --------------------------------------------------------------------------

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
    data = _parse_text(hass, text)
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


async def _respond(connection, msg, coro, code: str) -> None:
    try:
        result = await coro
    except ValueError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    except Exception as err: # noqa: BLE001
        connection.send_error(msg["id"], code, str(err))
        return
    connection.send_result(msg["id"], result)


# --------------------------------------------------------------------------
# WebSocket API
# --------------------------------------------------------------------------

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "ysm/list"})
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    try:
        yaml_items, packages_ok = await hass.async_add_executor_job(
            _scan_config, hass
        )
        managed = await hass.async_add_executor_job(_read_managed, hass)
        managed_view = _managed_view(managed)
    except Exception as err: # noqa: BLE001
        connection.send_error(msg["id"], "load_failed", str(err))
        return
    connection.send_result(msg["id"], {
        "yaml": yaml_items,
        "managed": managed_view,
        "restart": _restart_reasons(hass),
        "packages_ok": packages_ok,
    })


async def _save_and_reload(hass, msg) -> dict:
    count = await hass.async_add_executor_job(
        _save, hass, msg["yaml"], msg["default_type"], msg.get("replace")
    )
    await _reload(hass)
    return {"saved": count}


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
    await _respond(connection, msg, _save_and_reload(hass, msg), "save_failed")


async def _delete_and_reload(hass, msg) -> dict:
    await hass.async_add_executor_job(
        _delete, hass, msg["sensor_type"], msg["index"]
    )
    await _reload(hass)
    return {"ok": True}


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/delete",
    vol.Required("sensor_type"): vol.In(TYPES),
    vol.Required("index"): int,
})
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    await _respond(
        connection, msg, _delete_and_reload(hass, msg), "delete_failed"
    )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/config_save",
    vol.Required("yaml"): str,
    vol.Required("loc"): LOC,
})
@websocket_api.async_response
async def ws_config_save(hass, connection, msg):
    await _respond(
        connection, msg,
        _change_config(hass, msg["loc"], msg["yaml"]), "save_failed",
    )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/config_delete",
    vol.Required("loc"): LOC,
})
@websocket_api.async_response
async def ws_config_delete(hass, connection, msg):
    await _respond(
        connection, msg,
        _change_config(hass, msg["loc"], None), "delete_failed",
    )


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
    for cmd in (
        ws_list, ws_save, ws_delete, ws_format,
        ws_config_save, ws_config_delete,
    ):
        websocket_api.async_register_command(hass, cmd)

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
