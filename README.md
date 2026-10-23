# Custom Sensor Viewer

A Home Assistant custom integration that adds a sidebar panel to view, add,
edit and delete your YAML sensors, including the ones in `configuration.yaml`.

## Features

- Lists `sensor`, `binary_sensor` and `template` entries from
  `configuration.yaml`
- Paste YAML to add sensors. It accepts a single sensor, a list,
  `sensor:` / `binary_sensor:` blocks, or a full `template:` block
- Pasted text is cleaned up automatically (smart quotes, tabs, lost
  indentation on the first line)
- Edit and delete managed sensors
- Edit and delete sensors directly in `configuration.yaml`, with an
  automatic backup and rollback
- Copy a `configuration.yaml` template sensor into the managed file
- Live state badge on each sensor
- Search box and tabs, and it works on mobile
- Restart/reload banner and a Reload / Restart dialog
- Template changes apply straight away through `template.reload`

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

If `packages` isn't set up correctly, the panel shows a **Setup needed**
banner with the snippet to add.

## Usage

### Add sensors

Click **Add sensor** and paste YAML. Any of these work:

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

Use **Format** to tidy the YAML before saving. If it can't be parsed, the
cleaned text is shown along with the error.

### Edit and delete managed sensors

Use **Edit** or **Delete** on a card in the **Managed** tab. Saving a sensor
with the same `unique_id` (or the same `name` if it has no `unique_id`)
replaces the existing one.

### Edit and delete sensors in configuration.yaml

Cards in the **Config** tab also have **Edit** and **Delete** buttons.

- Only the selected entry is rewritten. The rest of the file, including
  comments and `!include` / `!secret` lines elsewhere, is left alone.
- Before every change, a backup is saved as `configuration.yaml.ysm.bak`.
- Home Assistant then validates the configuration. If it is rejected, the
  backup is restored automatically and the error is shown.
- Template sensors reload instantly. Platform sensors
  (`sensor: - platform: ...`) need a restart, and the panel will prompt you.

Things to know:

- Comments inside the edited entry are lost.
- A `!secret` inside the edited entry is replaced by its actual value.
- Entries that come from `!include` files are shown, but can't be edited in
  place. Edit those files directly, or use **Copy to managed**.
- To move a template sensor into the managed file, use **Copy to managed**,
  then delete the original so you don't get duplicates.

### Reload and restart

An orange banner appears when a restart is needed (for example after editing
a platform sensor). Click it, or use **Reload / Restart** in the panel
header, to open a dialog with these options:

| Option | What it does |
| --- | --- |
| Check configuration | Validates your YAML without changing anything |
| Reload template entities | Applies template sensor changes with no downtime |
| Reload all YAML | Reloads core, templates, automations, scripts and more |
| Restart Home Assistant | Needed for sensor platforms in `configuration.yaml` |

The banner clears itself after Home Assistant restarts.

### Do I need to restart?

| Change | Restart needed? |
| --- | --- |
| Add, edit or delete a managed sensor | No |
| Edit or delete a template sensor in `configuration.yaml` | No |
| Edit or delete a platform sensor in `configuration.yaml` | Yes |
| First-time setup of `packages` | Yes |

## How it works

Managed sensors are stored in `packages/ysm.yaml` under `template:`. The
integration rewrites only that file, then calls `template.reload`.

Edits to `configuration.yaml` replace only the lines of the selected list
item, check that the result is valid YAML, write a backup, save the file,
and run Home Assistant's configuration check.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Not in the sidebar | Do a full restart, log in as admin, then hard-refresh |
| "Secrets not supported" | Update to the latest version and restart |
| Blank page | Check the browser console for a 404 on `/ysm_static/panel.js` |
| Sensors don't appear | Check that `packages/` is loaded in your config |
| "Setup needed" banner | Add the `packages` snippet to `configuration.yaml` |
| "mapping values are not allowed here" | Update to 0.4.1 or newer. It fixes pastes where the first line lost its indentation |
| "Couldn't find this entry as a plain list item" | The entry comes from an `!include` file. Edit that file directly |
| "Home Assistant rejected the change" | The change was rolled back. Fix the YAML and try again |
| Panel looks outdated after an update | Restart Home Assistant, then hard-refresh the browser |

To undo a bad edit by hand, copy `configuration.yaml.ysm.bak` over
`configuration.yaml`. It holds the state from just before the last change.

Check **Settings → System → Logs** for `yaml_sensor_manager`.

## Limitations

- Only the modern `template:` format is editable in the managed file.
  Legacy `platform: template` sensors in `configuration.yaml` can be edited
  or deleted, but not copied to managed.
- Live state matches on `friendly_name`, so it is approximate.
- Only one backup is kept (the most recent).
- Back up your config before first use.

## License

MIT. Add a `LICENSE` file to match.
