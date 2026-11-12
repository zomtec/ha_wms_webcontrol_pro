# WMS WebControl pro for Home Assistant

[![License](https://img.shields.io/github/license/zomtec/ha_wms_webcontrol_pro)](https://github.com/zomtec/ha_wms_webcontrol_pro/blob/main/LICENSE)
[![Release](https://img.shields.io/github/v/release/zomtec/ha_wms_webcontrol_pro)](https://github.com/zomtec/ha_wms_webcontrol_pro/releases)
[![Commit activity](https://img.shields.io/github/commit-activity/y/zomtec/ha_wms_webcontrol_pro?style=flat-square)](https://github.com/zomtec/ha_wms_webcontrol_pro/commits)
[![Home Assistant Marketplace](https://img.shields.io/badge/Home%20Assistant-Marketplace-41BDF5?style=flat-square)](https://www.home-assistant.io/integrations/marketplace/)

Custom integration (HACS) for the [Warema](https://www.warema.com) WMS WebControl pro
gateway. The gateway connects the WMS radio system of Warema (awnings, roller shutters,
blinds, lights and other components) to the network. This integration controls these
components from Home Assistant through the local API of the gateway, without a cloud.

The integration uses the library
[`pywmswebcontrolpro`](https://github.com/zomtec/pywmswebcontrolpro). All device logic
lives in the library, the integration only maps it to Home Assistant entities.

## Disclaimer

This is an independent community project and is not affiliated with, endorsed by, or sponsored by Warema Renkhoff SE, the manufacturer of the WMS WebControl pro. Warema, WMS and related product names are trademarks of their respective owners.

## Why this integration exists next to the core integration

Home Assistant Core has an integration for the same gateway, `wmspro`. This integration
is a continuation of it with a different focus:

- **Less radio traffic.** The core integration asks every component for its status every
  10 to 15 seconds. This integration asks rarely and once after each command, see
  [Data updates](#data-updates).
- **A position while the cover moves.** The gateway reports no position during a drive.
  This integration calculates it from configurable travel times, also for the valance
  of an awning.
- **Devices are controlled only through Home Assistant.** The integration assumes that
  the Warema WMS devices are controlled exclusively through Home Assistant. The state is
  read back from the gateway only very rarely, because a status request (`getStatus`)
  often fails with an error, see [Known limitations](#known-limitations). The shown state
  therefore comes from the commands that Home Assistant sent. Changes made with a wall
  transmitter or another app are not noticed reliably.

The last two points are the reason why these changes would most likely not be accepted
in the core integration. They contradict a principle of Home Assistant: the controlled
device determines its current state and Home Assistant only takes it over. That way the
state is always correct, even when a device is controlled from several sources. This
integration works the other way round, the shown state comes from the commands and the
calculation, and the gateway cannot deliver the state reliably enough to do it differently.

Both integrations can be installed at the same time, but only one of them should control
a gateway.

> **Status:** not released yet. The integration is complete, but it has only been tested
> with a simulated gateway, not with a real one. The library has to be published on PyPI
> before the integration can be installed.

## Requirements

- Home Assistant 2026.10.0 or newer.
- A WMS WebControl pro reachable from Home Assistant by host name or IP address.
- The domain is `wms_webcontrol_pro`. It can be installed next to the core
  integration [`wmspro`](https://github.com/home-assistant/core/tree/dev/homeassistant/components/wmspro), but both must never control the same gateway at the same time.

## Supported devices and functions

The integration supports the gateway with all components that it announces with one of
these functions:

- awnings, valances, roller shutters, blinds and slat drives (with and without tilt)
- switchable lights, dimmers and loads
- scenes of the gateway
- the identify function of components that offer it

Other functions of a component, for example sensors, are not supported. Which entities
a component gets is described in [Entities](#entities).

## Use cases

- Open, close and position awnings, shutters and blinds from the dashboard, with the
  slats of blinds tilted separately.
- Shade a room automatically by sun, temperature or time.
- Switch the lights and loads that are connected to the WMS system.
- Start the scenes that are configured in the gateway.

## Installation

### Marketplace

The integration is installed from the Home Assistant Marketplace (formerly HACS). It is
not part of the default catalog yet, so the repository has to be added as a custom
repository first. On Home Assistant 2026.10, which has no Marketplace yet, use
[HACS](https://hacs.xyz).

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zomtec&repository=ha_wms_webcontrol_pro&category=integration)

1. Click the button above, or add `https://github.com/zomtec/ha_wms_webcontrol_pro` as a
   custom repository of type *Integration*.
2. Search for *WMS WebControl pro*, choose *Download* and confirm.
3. Restart Home Assistant if asked.
4. Continue with [Set up the integration](#set-up-the-integration).

Updates appear under *Settings, Updates*.

### Manual installation

Copy the folder `custom_components/wms_webcontrol_pro` of this repository into the
`custom_components` folder of your Home Assistant configuration and restart Home
Assistant.

## Set up the integration

[![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wms_webcontrol_pro)

1. Click the button above, or go to *Settings, Devices & services, Add integration* and
   search for *WMS WebControl pro*.
2. Enter the host name or IP address of the gateway. The setup checks that the gateway
   answers.
3. Finish the dialog. The gateway and its components appear as devices.

### Installation parameters

| Parameter | Description |
| --- | --- |
| Host | Host name or IP address of the WMS WebControl pro, `webcontrol` is suggested. |

A gateway that is set up once cannot be set up a second time. The integration has no
options, all settings (travel times, rotation limits) are number entities.

### Discovery

A gateway is found by DHCP (MAC address prefix `0023D5`) and shown as *Discovered* in
*Settings, Devices & services*. Choose *Add* to set it up. If the gateway is already set
up with an IP address and gets a new one, the host of the entry is updated. A host name
stays as it is.

### Removal

1. Go to *Settings, Devices & services*, open *WMS WebControl pro* and choose *Delete*
   in the menu of the entry. The devices and entities are removed and the stored data
   (see [Stored data](#stored-data)) is deleted.
2. Remove the integration in the Marketplace (or HACS) if it is not needed any more.

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

## Actions

### `wms_webcontrol_pro.set_cover_position_and_tilt`

Moves a slat drive and its tilt to the target values with one request, so the two
movements do not cancel each other. Fields: `position` and `tilt_position`, both 0 to 100.

## Data updates


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

## Examples

Move a blind and tilt its slats with one request, so the tilt does not cancel the movement:

```yaml
actions:
  - action: wms_webcontrol_pro.set_cover_position_and_tilt
    target:
      entity_id: cover.living_room_blind
    data:
      position: 60
      tilt_position: 30
```

Retract an awning when the wind picks up:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.wind_speed
    above: 40
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.awning
```

## Known limitations

- The gateway reports no position while a drive is running. Changes that are made
  outside Home Assistant, for example with a wall transmitter, are noticed with the
  next status request, the regular request is made every 30 minutes.
- The radio channel can be busy. The integration then skips the request instead of
  repeating it, the position is checked again after the next command or the next
  regular request.
- Without travel times the position of a moving cover is not shown. The target position
  is shown at once.
- Only one Home Assistant integration should control a gateway. Do not set up the gateway
  with this integration and with the core integration `wmspro` at the same time.
- Components are found when the integration is loaded. Reload the integration after you
  change the configuration of the gateway.

## Troubleshooting

- **Setup fails with "Failed to connect":** check the host name or IP address and that
  the gateway is reachable from Home Assistant. Open `http://<host>/control` in a browser.
- **A cover shows the wrong position:** enter the travel times of the drive. The next status
  request corrects the position. A cover that moved on its own
  is asked again up to three times.
- **A destination is unavailable:** the gateway reports no data for it, for example when
  the component is out of radio range. The diagnostics show how often each destination
  answered, was busy or failed.
- **Download the diagnostics** in *Settings, Devices & services* with *Download
  diagnostics* when you report a problem. The host is redacted.
- **Debug logs:** add this to `configuration.yaml` and restart:

  ```yaml
  logger:
    logs:
      custom_components.wms_webcontrol_pro: debug
      pywmswebcontrolpro: debug
  ```

## Stored data

Settings and learned values are stored by the library in
`.storage/wms_webcontrol_pro-<entry id>/<destination id>/<action id>.json`. The
directory is removed when the config entry is removed.

## Acknowledgments

This integration was created with substantial assistance from Claude, an AI assistant by Anthropic.

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
