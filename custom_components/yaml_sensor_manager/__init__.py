"""Custom Sensor Viewer."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import tempfile
import textwrap
from collections.abc import Mapping
from pathlib import Path

import voluptuous as vol
import yaml
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util.yaml.loader import Secrets, parse_yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

DOMAIN = "yaml_sensor_manager"
DOMAIN_TEMPLATE = "template"
VERSION = "0.6.0"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Every entity type the template integration can create.
TEMPLATE_DOMAINS = (
    "sensor", "binary_sensor", "button", "number", "select", "switch",
    "light", "cover", "fan", "lock", "image", "update", "vacuum",
    "weather", "alarm_control_panel",
)
# Legacy `sensor: - platform: ...` entries in configuration.yaml.
LEGACY_TYPES = ("sensor", "binary_sensor")
TRIGGER_KEYS = ("trigger", "triggers")
# A mapping with any of these keys is a whole template block.
BLOCK_KEYS = set(TEMPLATE_DOMAINS) | set(TRIGGER_KEYS)

BAK_SUFFIX = ".ysm.bak"
HEADER = "# Managed by Custom Sensor Viewer\n"

LOC = vol.Schema({
    vol.Required("section"): vol.In(("template", "platform")),
    vol.Optional("type"): vol.In(LEGACY_TYPES),
    vol.Required("index"): int,
})


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

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
    """Fallback only: used when the raw text of an entry isn't available."""
    return yaml.dump(
        _jsonable(data),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _secrets(hass) -> Secrets:
    return Secrets(Path(hass.config.config_dir))


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _state(hass) -> dict:
    return hass.data.setdefault(
        DOMAIN, {"restart": [], "lock": asyncio.Lock()}
    )


# --------------------------------------------------------------------------
# Text cleanup (smart quotes, tabs, lost indentation). No re-dumping.
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


def _compose(text: str, what: str = "YAML"):
    try:
        return yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        raise ValueError(
            f"Invalid {what}: {err}. Tip: wrap templates in quotes, "
            "or use a | block."
        ) from err


def _format(text: str) -> dict:
    """Clean pasted text. The text is never re-dumped, so styles survive."""
    cleaned = _clean_text(text)
    try:
        yaml.compose(cleaned, Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        return {"yaml": cleaned, "error": str(err)}
    return {"yaml": cleaned}


# --------------------------------------------------------------------------
# YAML node / line surgery (keeps comments, >, |, !secret, !include)
# --------------------------------------------------------------------------

def _map_get(node, key):
    if not isinstance(node, MappingNode):
        return None
    for k, v in node.value:
        if isinstance(k, ScalarNode) and k.value == key:
            return v
    return None


def _keys(node) -> set[str]:
    return {k.value for k, _ in node.value if isinstance(k, ScalarNode)}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _leaf_end(node) -> int:
    """Exclusive end line of the last scalar inside a node."""
    if isinstance(node, ScalarNode):
        mark = node.end_mark
        return mark.line + (1 if mark.column > 0 else 0)
    if isinstance(node, SequenceNode):
        return max(
            (_leaf_end(n) for n in node.value),
            default=node.end_mark.line + 1,
        )
    best = node.start_mark.line + 1
    for k, v in node.value:
        best = max(best, _leaf_end(k), _leaf_end(v))
    return best


def _span(lines: list[str], node) -> tuple[int, int]:
    """Line range [start, end) of a node, without trailing blank lines."""
    start = node.start_mark.line
    col = node.start_mark.column
    end = min(_leaf_end(node), len(lines))
    # PyYAML can overshoot by the next token's line; that line is always
    # indented less than the node itself, so trim it.
    while end > start + 1 and (
        not lines[end - 1].strip() or _indent(lines[end - 1]) < col
    ):
        end -= 1
    return start, end


def _body_lines(lines: list[str], node) -> list[str]:
    """Raw text of a node with its own indentation (and any dash) removed."""
    start, end = _span(lines, node)
    col = node.start_mark.column
    body = [lines[start][col:].rstrip()]
    for ln in lines[start + 1:end]:
        if not ln.strip():
            body.append("")
        elif ln[:col].strip() == "":
            body.append(ln[col:].rstrip())
        else:
            raise ValueError(
                "This entry's layout isn't supported "
                "(flow style or unusual indentation)."
            )
    return body


def _emit(body: list[str], pad: int = 0) -> list[str]:
    """Turn body lines back into a YAML list item."""
    sp = " " * pad
    out = [sp + "- " + body[0]]
    out += [(sp + "  " + ln) if ln else "" for ln in body[1:]]
    return out


def _hash(body: list[str]) -> str:
    return hashlib.sha1("\n".join(body).encode("utf-8")).hexdigest()[:12]


def _item_pad(lines: list[str], node) -> int:
    """Indent of the dash of a list item, or an error if it isn't one."""
    prefix = lines[node.start_mark.line][: node.start_mark.column]
    if prefix.strip() != "-":
        raise ValueError("This entry's layout isn't supported for editing.")
    return _indent(prefix)


def _parse_body(hass, body: list[str]):
    try:
        return parse_yaml("\n".join(body) + "\n", _secrets(hass))
    except Exception as err:  # noqa: BLE001
        raise ValueError(f"Invalid YAML: {err}") from err


# --------------------------------------------------------------------------
# Describing blocks for the panel
# --------------------------------------------------------------------------

def _trigger_text(trig) -> str:
    if not isinstance(trig, dict):
        return str(trig)
    kind = trig.get("trigger") or trig.get("platform") or "trigger"
    text = str(kind)
    for key in ("entity_id", "event_type", "at", "topic", "webhook_id"):
        if key in trig:
            val = trig[key]
            val = ", ".join(map(str, val)) if isinstance(val, list) else val
            text = f"{kind}: {val}"
            break
    if trig.get("id"):
        text += f" ({trig['id']})"
    return text


def _entity_info(domain: str, entry: dict) -> dict:
    icon = entry.get("icon")
    return {
        "domain": domain,
        "name": None if entry.get("name") is None else str(entry["name"]),
        "unique_id": entry.get("unique_id"),
        "device_class": entry.get("device_class"),
        "unit_of_measurement": entry.get("unit_of_measurement"),
        "icon": icon if isinstance(icon, str) else None,
        "platform": entry.get("platform"),
    }


def _describe(block) -> dict:
    block = _jsonable(block) if isinstance(block, Mapping) else {}
    entities = []
    for domain in TEMPLATE_DOMAINS:
        for entry in _as_list(block.get(domain)):
            if isinstance(entry, dict):
                entities.append(_entity_info(domain, entry))
    trig_key = next((k for k in TRIGGER_KEYS if k in block), None)
    triggers = [_trigger_text(t) for t in _as_list(block.get(trig_key))]
    return {
        "entities": entities,
        "triggers": triggers,
        "trigger": trig_key is not None,
    }


def _check_block(block) -> None:
    if not isinstance(block, Mapping) or not _describe(block)["entities"]:
        raise ValueError(
            "Each block needs at least one entity under sensor:, "
            "binary_sensor:, button:, number: and so on."
        )


def _unique_ids(block) -> list[str]:
    return [
        str(e["unique_id"])
        for e in _describe(block)["entities"]
        if e.get("unique_id")
    ]


# --------------------------------------------------------------------------
# Restart tracking (in memory, so a restart clears it automatically)
# --------------------------------------------------------------------------

def _need_restart(hass, reason: str) -> None:
    reasons = _state(hass)["restart"]
    if reason not in reasons:
        reasons.append(reason)


def _restart_reasons(hass) -> list[str]:
    return list(_state(hass)["restart"])


# --------------------------------------------------------------------------
# Safe file writes
# --------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _commit(path: Path, new_text: str) -> bool:
    """Back up, then atomically replace a file. Returns True if it existed."""
    if not new_text.endswith("\n"):
        new_text += "\n"
    existed = path.exists()
    if existed:
        shutil.copy2(path, path.with_name(path.name + BAK_SUFFIX))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ysm-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        if existed:
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return existed


def _rollback(path: Path, existed: bool) -> None:
    if existed:
        shutil.copy2(path.with_name(path.name + BAK_SUFFIX), path)
    else:
        path.unlink(missing_ok=True)


async def _validate(hass, path: Path, existed: bool) -> None:
    """Run HA's config check; restore the file if it is rejected."""
    try:
        await hass.services.async_call(
            "homeassistant", "check_config", blocking=True
        )
    except Exception as err:  # noqa: BLE001
        await hass.async_add_executor_job(_rollback, path, existed)
        raise ValueError(
            f"Home Assistant rejected the change, so it was rolled back: {err}"
        ) from err


async def _reload(hass) -> None:
    await hass.services.async_call(DOMAIN_TEMPLATE, "reload", blocking=True)


# --------------------------------------------------------------------------
# Splitting pasted text into template blocks
# --------------------------------------------------------------------------

def _split_blocks(hass, text: str, default_type: str) -> list[list[str]]:
    """Parse pasted text into template blocks (as raw body lines).

    Accepts a template: wrapper, a list of blocks, a single block, or bare
    entries. Bare entries are wrapped in `default_type:`.
    """
    cleaned = _clean_text(text)
    root = _compose(cleaned)
    if root is None:
        raise ValueError("Nothing to save.")
    lines = cleaned.split("\n")
    out: list[list[str]] = []
    pending: list[list[str]] = []

    def flush() -> None:
        if pending:
            body = [f"{default_type}:"]
            for entry in pending:
                body += _emit(entry, 2)
            out.append(body)
            pending.clear()

    def visit(node) -> None:
        if isinstance(node, SequenceNode):
            for child in node.value:
                visit(child)
        elif isinstance(node, MappingNode):
            wrapped = _map_get(node, "template")
            if wrapped is not None:
                visit(wrapped)
            elif _keys(node) & BLOCK_KEYS:
                flush()
                out.append(_body_lines(lines, node))
            else:
                pending.append(_body_lines(lines, node))
        else:
            raise ValueError(
                "Expected a sensor, a list of sensors, or a template: block."
            )

    visit(root)
    flush()
    if not out:
        raise ValueError("No sensors found in the pasted YAML.")
    return out


# --------------------------------------------------------------------------
# Managed file (packages/ysm.yaml): a list of template blocks
# --------------------------------------------------------------------------

def _managed_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path("packages", "ysm.yaml"))


def _managed_nodes(text: str) -> tuple[list[str], list]:
    """Lines of ysm.yaml and the block nodes of its template: list."""
    lines = text.split("\n")
    root = _compose(text, "packages/ysm.yaml")
    seq = _map_get(root, "template") if root is not None else None
    if seq is None or (isinstance(seq, ScalarNode) and not seq.value):
        return lines, []
    if not isinstance(seq, SequenceNode):
        raise ValueError(
            "packages/ysm.yaml has an unexpected layout "
            "(template: must be a list)."
        )
    return lines, list(seq.value)


def _managed_data(hass, text: str) -> list:
    if not text.strip():
        return []
    data = parse_yaml(text, _secrets(hass))
    if not isinstance(data, Mapping):
        return []
    return list(_as_list(data.get("template")))


def _scan_managed(hass) -> list[dict]:
    text = _read_text(_managed_path(hass))
    lines, nodes = _managed_nodes(text)
    blocks = _managed_data(hass, text)
    items = []
    for i, node in enumerate(nodes):
        block = blocks[i] if i < len(blocks) else {}
        try:
            body = _body_lines(lines, node)
        except ValueError:
            body = None
        desc = _describe(block)
        items.append({
            "index": i,
            "hash": _hash(body) if body else None,
            "yaml": (
                "\n".join(_emit(body)) if body
                else _dump([block]).rstrip("\n")
            ),
            "kind": "template trigger" if desc["trigger"] else "template",
            **desc,
        })
    return items


def _edit_managed(
    hass,
    bodies: list[list[str]],
    index: int | None = None,
    digest: str | None = None,
) -> bool:
    """Add blocks, or replace/delete block `index`. Returns `existed`."""
    path = _managed_path(hass)
    text = _read_text(path)
    lines, nodes = _managed_nodes(text)
    existing = _managed_data(hass, text)

    # No two managed blocks may share a unique_id.
    taken: set[str] = set()
    for i, block in enumerate(existing):
        if i != index:
            taken.update(_unique_ids(block))
    for body in bodies:
        for uid in _unique_ids(_parse_body(hass, body)):
            if uid in taken:
                raise ValueError(
                    f"unique_id '{uid}' is already used by another managed "
                    "block. Edit that block instead."
                )
            taken.add(uid)

    if index is not None:
        if not 0 <= index < len(nodes):
            raise ValueError("That block no longer exists. Refresh and retry.")
        node = nodes[index]
        pad = _item_pad(lines, node)
        if digest and _hash(_body_lines(lines, node)) != digest:
            raise ValueError(
                "This block changed since you loaded it. Refresh and retry."
            )
        start, end = _span(lines, node)
        block_lines = [ln for b in bodies for ln in _emit(b, pad)]
        new_lines = lines[:start] + block_lines + lines[end:]
        remaining = len(nodes) - 1 + len(bodies)
    elif nodes:
        pad = _item_pad(lines, nodes[-1])
        _, end = _span(lines, nodes[-1])
        block_lines = [ln for b in bodies for ln in _emit(b, pad)]
        new_lines = lines[:end] + block_lines + lines[end:]
        remaining = len(nodes) + len(bodies)
    else:
        block_lines = [ln for b in bodies for ln in _emit(b, 2)]
        new_lines = HEADER.split("\n")[:-1] + ["template:"] + block_lines
        remaining = len(bodies)

    new_text = "\n".join(new_lines) if remaining else HEADER
    _compose(new_text, "result")
    return _commit(path, new_text)


def _save(hass, text, default_type, replace) -> tuple[bool, int]:
    bodies = _split_blocks(hass, text, default_type)
    count = 0
    for body in bodies:
        block = _parse_body(hass, body)
        _check_block(block)
        count += len(_describe(block)["entities"])
    existed = _edit_managed(
        hass,
        bodies,
        index=replace["index"] if replace else None,
        digest=replace.get("hash") if replace else None,
    )
    return existed, count


def _delete(hass, index: int, digest: str | None) -> bool:
    return _edit_managed(hass, [], index=index, digest=digest)


# --------------------------------------------------------------------------
# configuration.yaml scanning and editing
# --------------------------------------------------------------------------

def _config_path(hass) -> Path:
    return Path(hass.config.path("configuration.yaml"))


def _locate(root, loc: dict):
    """Find the list item node for a loc, or None (e.g. !include)."""
    if root is None:
        return None
    if loc["section"] == "platform":
        seq = _map_get(root, loc.get("type", ""))
    else:
        seq = _map_get(root, "template")
    if not isinstance(seq, SequenceNode) or loc["index"] >= len(seq.value):
        return None
    return seq.value[loc["index"]]


def _raw(lines, root, loc):
    """(body lines, hash) of an editable entry, else (None, None)."""
    node = _locate(root, loc)
    if node is None:
        return None, None
    try:
        _item_pad(lines, node)
        body = _body_lines(lines, node)
    except ValueError:
        return None, None
    return body, _hash(body)


def _scan_config(hass) -> tuple[list[dict], bool]:
    path = _config_path(hass)
    text = path.read_text(encoding="utf-8")
    with open(path, encoding="utf-8") as f:
        cfg = parse_yaml(f, _secrets(hass)) or {}
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        root = None
    lines = text.split("\n")
    items: list[dict] = []

    def shown(body, fallback):
        return "\n".join(_emit(body)) if body else _dump([fallback]).rstrip("\n")

    for domain in LEGACY_TYPES:
        val = cfg.get(domain) or []
        for i, entry in enumerate(val if isinstance(val, list) else [val]):
            if not isinstance(entry, Mapping):
                continue
            entry = _jsonable(entry)
            loc = {"section": "platform", "type": domain, "index": i}
            body, digest = _raw(lines, root, loc)
            info = _entity_info(domain, entry)
            info["name"] = info["name"] or entry.get("platform")
            items.append({
                "kind": f"{domain} (platform)",
                "platform": True,
                "copyable": False,
                "loc": loc if body else None,
                "hash": digest,
                "yaml": shown(body, entry),
                "entities": [info],
                "triggers": [],
                "trigger": False,
            })

    tpl = cfg.get("template") or []
    for bi, block in enumerate(tpl if isinstance(tpl, list) else [tpl]):
        if not isinstance(block, Mapping):
            continue
        loc = {"section": "template", "index": bi}
        body, digest = _raw(lines, root, loc)
        desc = _describe(block)
        items.append({
            "kind": "template trigger" if desc["trigger"] else "template",
            "platform": False,
            "copyable": True,
            "loc": loc if body else None,
            "hash": digest,
            "yaml": shown(body, _jsonable(block)),
            **desc,
        })

    # Is packages/ysm.yaml actually being loaded?
    core = cfg.get("homeassistant")
    pk = core.get("packages") if isinstance(core, Mapping) else None
    loaded = isinstance(pk, Mapping) and "ysm" in pk
    packages_ok = loaded or not _managed_path(hass).exists()
    return items, packages_ok


def _single_body(hass, text: str, loc: dict) -> list[str]:
    if loc["section"] == "template":
        bodies = _split_blocks(hass, text, "sensor")
        if len(bodies) != 1:
            raise ValueError("Edit exactly one block here.")
        _check_block(_parse_body(hass, bodies[0]))
        return bodies[0]
    cleaned = _clean_text(text)
    node = _compose(cleaned)
    if isinstance(node, SequenceNode):
        if len(node.value) != 1:
            raise ValueError("Edit exactly one sensor here.")
        node = node.value[0]
    if not isinstance(node, MappingNode):
        raise ValueError("Edit exactly one sensor here.")
    return _body_lines(cleaned.split("\n"), node)


def _edit_config(hass, loc: dict, text: str | None, digest) -> bool:
    """Replace (text given) or delete (text None) one config entry."""
    path = _config_path(hass)
    original = path.read_text(encoding="utf-8")
    root = _compose(original, "configuration.yaml")
    node = _locate(root, loc)
    if node is None:
        raise ValueError(
            "Couldn't find this entry as a plain list item in "
            "configuration.yaml (it may come from an !include file). "
            "Refresh and try again."
        )
    lines = original.split("\n")
    pad = _item_pad(lines, node)
    if digest and _hash(_body_lines(lines, node)) != digest:
        raise ValueError(
            "This entry changed since you loaded it. Refresh and retry."
        )
    start, end = _span(lines, node)
    if text is None:
        new_lines = lines[:start] + lines[end:]
    else:
        body = _single_body(hass, text, loc)
        new_lines = lines[:start] + _emit(body, pad) + lines[end:]
    new_text = "\n".join(new_lines)
    _compose(new_text, "result")
    return _commit(path, new_text)


# --------------------------------------------------------------------------
# Changes (serialised, validated, rolled back on failure)
# --------------------------------------------------------------------------

async def _change_config(hass, loc: dict, text: str | None, digest) -> dict:
    async with _state(hass)["lock"]:
        existed = await hass.async_add_executor_job(
            _edit_config, hass, loc, text, digest
        )
        await _validate(hass, _config_path(hass), existed)
        restart = loc["section"] == "platform"
        if restart:
            _need_restart(
                hass, "A sensor platform in configuration.yaml was changed."
            )
        else:
            await _reload(hass)
    return {"saved": 1, "ok": True, "restart": restart}


async def _save_and_reload(hass, msg) -> dict:
    async with _state(hass)["lock"]:
        existed, count = await hass.async_add_executor_job(
            _save, hass, msg["yaml"], msg["default_type"], msg.get("replace")
        )
        await _validate(hass, _managed_path(hass), existed)
        await _reload(hass)
    return {"saved": count}


async def _delete_and_reload(hass, msg) -> dict:
    async with _state(hass)["lock"]:
        existed = await hass.async_add_executor_job(
            _delete, hass, msg["index"], msg.get("hash")
        )
        await _validate(hass, _managed_path(hass), existed)
        await _reload(hass)
    return {"ok": True}


async def _respond(connection, msg, coro, code: str) -> None:
    try:
        result = await coro
    except ValueError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], code, str(err))
        return
    connection.send_result(msg["id"], result)


def _attach_entity_ids(hass, items: list[dict]) -> None:
    """Look up real entity_ids by unique_id so live state is exact."""
    registry = er.async_get(hass)
    for item in items:
        for ent in item["entities"]:
            uid = ent.get("unique_id")
            if uid:
                ent["entity_id"] = registry.async_get_entity_id(
                    ent["domain"], ent.get("platform") or "template", str(uid)
                )


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
        managed = await hass.async_add_executor_job(_scan_managed, hass)
        _attach_entity_ids(hass, yaml_items)
        _attach_entity_ids(hass, managed)
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "load_failed", str(err))
        return
    connection.send_result(msg["id"], {
        "yaml": yaml_items,
        "managed": managed,
        "restart": _restart_reasons(hass),
        "packages_ok": packages_ok,
    })


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/save",
    vol.Required("yaml"): str,
    vol.Optional("default_type", default="sensor"): vol.In(TEMPLATE_DOMAINS),
    vol.Optional("replace"): {
        vol.Required("index"): int,
        vol.Optional("hash"): str,
    },
})
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    await _respond(connection, msg, _save_and_reload(hass, msg), "save_failed")


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/delete",
    vol.Required("index"): int,
    vol.Optional("hash"): str,
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
    vol.Optional("hash"): str,
})
@websocket_api.async_response
async def ws_config_save(hass, connection, msg):
    await _respond(
        connection, msg,
        _change_config(hass, msg["loc"], msg["yaml"], msg.get("hash")),
        "save_failed",
    )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/config_delete",
    vol.Required("loc"): LOC,
    vol.Optional("hash"): str,
})
@websocket_api.async_response
async def ws_config_delete(hass, connection, msg):
    await _respond(
        connection, msg,
        _change_config(hass, msg["loc"], None, msg.get("hash")),
        "delete_failed",
    )


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "ysm/format",
    vol.Required("yaml"): str,
})
@websocket_api.async_response
async def ws_format(hass, connection, msg):
    result = await hass.async_add_executor_job(_format, msg["yaml"])
    connection.send_result(msg["id"], result)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _state(hass)
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
