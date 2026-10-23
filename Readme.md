# Custom Sensor Viewer

A Home Assistant custom integration that adds a sidebar panel to view, add,
edit and delete your YAML sensors.

## Features

- Lists `sensor`, `binary_sensor` and `template` entries from
  `configuration.yaml`, including `!include` and `!secret`
- Paste YAML to add sensors. It accepts a single sensor, a list,
  `sensor:` / `binary_sensor:` blocks, or a full `template:` block
- Edit and delete the sensors the integration manages
- Copy a `configuration.yaml` template sensor into the managed file
- Live state badge on each sensor
- Search box and tabs, and it works on mobile
- Changes apply straight away through `template.reload`, with no restart

## Requirements

- Home Assistant 2024.7 or newer
- [HACS](https://hacs.xyz)
- An administrator account (the panel is admin-only)

## Installation

1. In HACS, open the ⋮ menu and choose **Custom repositories**.
2. Add `https://github.com/iamjmitch/HA-Custom-Sensor-Viewer` as type
   **Integration**.
3. Download **Custom Sensor Viewer**, then restart Home Assistant.
4. Add this to `configuration.yaml`:

   ```yaml
   yaml_sensor_manager:

   homeassistant:
     packages: !include_dir_named packages
   ```

   If you already use `packages`, skip the `homeassistant:` block and make
   sure `packages/ysm.yaml` is loaded.
5. Create an empty `packages/` folder next to `configuration.yaml`.
6. Restart Home Assistant again.
7. Open **Sensor Viewer** in the sidebar, or go to `/ysm`.

## Usage

### Add sensors

Click **+ Add sensor** and paste YAML. Any of these work:

```yaml
- name: Example Double
  unique_id: example_double
  unit_of_measurement: "W"
  state: "{{ states('sensor.x') | float(0) * 2 }}"
```

```yaml
template:
  - binary_sensor:
      - name: Door Open
        state: "{{ is_state('binary_sensor.door', 'on') }}"
```

Quote templates, or use a `|` block. An unquoted `state: {{ ... }}` is not
valid YAML.

If the pasted entries have no `sensor:` or `binary_sensor:` wrapper, the
dropdown in the dialog decides which type they become.

### Edit and delete

Use **Edit** or **Delete** on a card in the **Managed** tab. Saving a sensor
with the same `unique_id` (or the same `name` if it has no `unique_id`)
replaces the existing one.

### Sensors from configuration.yaml

These are read-only, because rewriting your YAML would remove comments and
formatting. Template sensors have a **Copy to managed** button that lets you
edit a copy. Remove the original from `configuration.yaml` afterwards, or
you'll have duplicates.

## How it works

Managed sensors are stored in `packages/ysm.yaml` under `template:`. The
integration rewrites only that file, then calls `template.reload`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Not in the sidebar | Do a full restart, log in as admin, then hard-refresh |
| "Secrets not supported" | Update to the latest version and restart |
| Blank page | Check the browser console for a 404 on `/ysm_static/panel.js` |
| Sensors don't appear | Check that `packages/` is loaded in your config |
| Save error about YAML | Quote your templates or use a `|` block |

Check **Settings → System → Logs** for `yaml_sensor_manager`.

## Limitations

- Only the modern `template:` format is editable. Legacy
  `platform: template` sensors are display-only.
- Live state matches on `friendly_name`, so it is approximate.
- Back up your config before first use.

## License

MIT. Add a `LICENSE` file to match.
