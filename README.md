# WMS WebControl pro for Home Assistant

Custom integration (HACS) for the Warema WMS WebControl pro gateway. It controls the
components of the WMS radio system through the local API of the gateway. The domain is
`ha_wms_webcontrol_pro`, it can be installed next to the core integration `wmspro`, but
both must never control the same gateway at the same time.

The integration uses the library
[`pywmswebcontrolpro`](https://github.com/zomtec/pywmswebcontrolpro). All device logic
lives in the library, the integration only maps it to Home Assistant entities.

## Status

Work in progress. The setup, the config flow, the polling and the diagnostics are done.
Covers, number entities, buttons, lights, switches, scenes and the identify button
follow in separate steps.

## Polling

The gateway is a radio gateway, every status request puts traffic on the radio channel.
One coordinator per gateway therefore asks each destination only rarely (every 30
minutes) and never repeats a request when the radio channel is busy. After a command
the entity asks the affected destination once for its status. The library counts the
results per destination and logs a warning only if a destination stays silent for a
long time. The counters are part of the diagnostics download.

## Stored data

Settings and learned values are stored by the library in
`.storage/ha_wms_webcontrol_pro-<entry id>/<destination id>/<action id>.json`. The
directory is removed when the config entry is removed.

## Origin and license

The integration is derived from the `wmspro` integration of Home Assistant Core by
Marc Hoersken and licensed under the Apache License 2.0, see [LICENSE](LICENSE).

## Development

```bash
python -m pip install -r requirements_lint.txt -r requirements_test.txt
ruff check . && ruff format --check . && mypy
python -m pytest
```

The version in `manifest.json` stays `0.0.0`, the release workflow writes the tag of
the GitHub release into it. The manifest pins the exact version of the library.
