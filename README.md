# WMS WebControl pro for Home Assistant

Custom integration (HACS) for the Warema WMS WebControl pro gateway. It controls the
components of the WMS radio system through the local API of the gateway.

The integration uses the library
[`pywmswebcontrolpro`](https://github.com/zomtec/pywmswebcontrolpro). All device logic
lives in the library, the integration only maps it to Home Assistant entities.

> **Status:** not released yet. The integration is complete, but it has only been tested
> with a simulated gateway, not with a real one. The library has to be published on PyPI
> before the integration can be installed.

## Requirements

- Home Assistant 2026.10.0 or newer.
- A WMS WebControl pro reachable from Home Assistant by host name or IP address.
- The domain is `wms_webcontrol_pro`. It can be installed next to the core
  integration [`wmspro`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/wmspro), but both must never control the same gateway at the same time.

## Installation

1. Add this repository as a custom repository of type *Integration* in HACS.
2. Download the integration and restart Home Assistant.
3. Go to *Settings, Devices & services, Add integration* and search for
   *WMS WebControl pro*. Enter the host name or IP address of the gateway. A gateway
   announced by DHCP is offered for setup automatically.

## Entities

The gateway is a device of its own. Each destination of the gateway (a drive, a light,
a load) is a device that is connected to it.

| Platform | Entities |
| --- | --- |
| Cover | Awning, valance, roller shutter or blind, slat drive and slat drive with tilt |
| Number | Travel times, rotation limits and rotation of slat drives |
| Button | Identify, reset of the rotation limits |
| Light | Switchable lights and dimmers |
| Switch | Loads |
| Scene | Scenes of the gateway, attached to the device of their room |

An awning with a valance has two covers, one for each drive. The valance has its own
travel times.

### Covers

Position 0 is closed and 100 is open. The gateway does not report a position while a
drive is running, so the integration calculates the position from the travel times
while the drive runs and takes the measured position from the gateway afterwards. The
attribute `position_source` shows where the position comes from (`measured`,
`calculated` or `restored`).

Without travel times the target position is shown at once and checked later. Set the
travel times for a smooth position display and for the opening and closing states.

Covers with tilt (slat drive with rotation) support the tilt position. Opening or
closing such a cover also moves the slats like the WMS WebControl pro does.

### Travel times

Every drive action has two number entities, *Opening time* and *Closing time* (in the
configuration category). They hold the time of a full drive in seconds, 0 means unknown.
Measure the time of a full drive with a stopwatch and enter it. The values are stored by
the library.

### Slat rotation

The slat drives with rotation have the number entities *Minimum rotation*, *Maximum
rotation* and *Raw rotation* and the button *Reset rotation range*. The limits start
at -75 and 75 and are widened automatically when a larger rotation is measured. The
button restores the limits.

## Services

### `wms_webcontrol_pro.set_cover_position_and_tilt`

Moves a slat drive and its tilt to the target values with one request, so the two
movements do not cancel each other. Fields: `position` and `tilt_position`, both 0 to 100.

## Polling

The gateway is a radio gateway, every status request puts traffic on the radio channel.
One coordinator per gateway therefore asks each destination only rarely (every 30
minutes) and never repeats a request when the radio channel is busy. After a command
the integration asks the affected destination once for its status: after the calculated
drive time for covers, after a few seconds for lights, switches and the rotation. If a
cover reports a position that differs from the calculated one, it is asked again up to
three times in a 30 seconds interval.

The library counts the results per destination and logs a warning only if a destination
stays silent for a long time. The counters are part of the diagnostics download. The
host is redacted in the diagnostics.

## Stored data

Settings and learned values are stored by the library in
`.storage/wms_webcontrol_pro-<entry id>/<destination id>/<action id>.json`. The
directory is removed when the config entry is removed.

## Origin and license

The integration is derived from the [`wmspro`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/wmspro) integration of Home Assistant Core by
Marc Hoersken and licensed under the Apache License 2.0, see [LICENSE](LICENSE).

## Development

```bash
python -m pip install -r requirements_lint.txt -r requirements_test.txt
ruff check . && ruff format --check . && mypy
python -m pytest
```

The version in `manifest.json` stays `0.0.0`, the release workflow writes the tag of
the GitHub release into it. The manifest pins the exact version of the library.
