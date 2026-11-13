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

> **Status:** the integration is complete, but it has only been tested with a simulated
> gateway, not with a real one. Use it with care until this note is removed.

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

To change the host later, use *Reconfigure* in the menu of the entry. The setup refuses
a gateway that has none of the components and rooms of the entry.

The API of the gateway has no serial number. A gateway that was set up by hand is
therefore recognized by its components and rooms, a gateway found by DHCP also by its
MAC address.

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
| Scene | Scenes of the gateway, attached to the device of their room, without a room to the gateway |
| Binary sensor | Connectivity of the gateway |
| Sensor | Polling statistics of the gateway and of each destination |

An awning with a valance has two covers, one for each drive, the second one is named
*Valance*. The valance has its own travel times.

### Diagnostic entities

The device of the gateway has three diagnostic entities:

- *Connectivity* is on while the gateway answers the regular request every 30 minutes.
  A gateway that does not answer is asked again every minute.
- *Poll success rate* is the share of all status requests since the start of Home
  Assistant that delivered data, over all destinations.
- *Last successful poll* is the time of the last status request that delivered data.

Each destination has its own *Poll success rate* and *Last successful poll*. They are
disabled by default, enable them to look into radio problems of one component. A
request counts as not successful when the radio channel was busy, the gateway had no
data for the destination or did not answer. The statistics start again with every
restart of Home Assistant, they stay available while the gateway does not answer.

### Covers

Position 0 is closed and 100 is open. The gateway does not report a position while a
drive is running, so the integration calculates the position from the travel times
while the drive runs and takes the measured position from the gateway afterwards. The
attribute `position_source` shows where the position comes from (`measured`,
`calculated` or `restored`).

Without travel times the target position is shown at once and checked later. Set the
travel times for a smooth position display and for the opening and closing states.

Covers with tilt (slat drive with rotation) support the tilt position. Tilt 100 is the
minimum rotation and tilt 0 the maximum rotation, see [Slat rotation](#slat-rotation).
Opening or closing such a cover also turns the slats to that end, like the WMS
WebControl pro does. *Open tilt* turns the slats horizontal (rotation 0), which lets
the most light through and is shown as tilt 50.

### Travel times

Every drive action has two number entities, *Opening time* and *Closing time* (in the
configuration category). They hold the time of a full drive in seconds, 0 means unknown.
Measure the time of a full drive with a stopwatch and enter it. The values are stored by
the library.

### Slat rotation

The slat drives with rotation have the number entities *Minimum rotation*, *Maximum
rotation* and *Raw rotation* and the button *Reset rotation range*.

**Firmware bug of the gateway:** the WMS WebControl pro reports the rotation limits of
slat drives as -127 and 127, but the drives turn from -75 to 75. With the reported
limits closed slats would be shown as 21 % open. Warema knows the bug, a fixed firmware
has not been announced.

The library `pywmswebcontrolpro` works around it, the integration only shows the result:

- While the gateway reports exactly -127 and 127, the limits are -75 and 75. The number
  entities show the limits that the cover really uses.
- A rotation that is measured beyond the limits widens them.
- A limit that is set in a number entity is stored and used at once. The button returns
  to -75 and 75.
- The rotation that is sent is a whole number within the limits.

The workaround ends by itself when a firmware reports other limits, and will then be
removed from the library.

*Raw rotation* is a diagnostic value with the limits of the gateway and disabled by
default, enable it in the entity settings if you need it.

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
three times in a 30 seconds interval. The awning and the valance of one destination
each get their own request.

The gateway does not tell which components a scene moves or for how long. Two minutes
after a scene every destination is asked once.

A command that the gateway rejects, for example because the radio channel is busy, or
does not answer is reported as an error of the action. It is not sent again.

If a single request for the configuration fails, the known configuration stays in use.
The entities only become unavailable when the gateway does not answer at all, it is
then asked again every minute.

The library counts the results per destination and logs a warning only if a destination
stays silent for a long time. The counters are part of the diagnostics download, the
success rate and the time of the last successful request are also shown by
[diagnostic entities](#diagnostic-entities). The host is redacted in the diagnostics.

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
- The configuration of the gateway is read again every 30 minutes. New components then
  get their entities. A component or scene that the gateway no longer reports loses its
  entities at once and its device when the next reading confirms it, so one incomplete
  answer deletes nothing. Names and functions of a component that is already known are
  not updated, reload the integration for that.
- The gateway offers its API only over HTTP without authentication. Run it in a
  trusted network.
- After a scene the state of the components is unknown for up to two minutes.

## Troubleshooting

- **Setup fails with "Failed to connect":** check the host name or IP address and that
  the gateway is reachable from Home Assistant. Open `http://<host>/control` in a browser.
- **A cover shows the wrong position:** enter the travel times of the drive. The next status
  request corrects the position. A cover that moved on its own
  is asked again up to three times.
- **A destination is unavailable:** the gateway reports a heartbeat error or a blocked
  drive for it, for example when the component is out of radio range. The diagnostics
  show how often each destination answered, was busy or failed, the sensors *Poll
  success rate* and *Last successful poll* of the device show it over time.
- **An action fails with "rejected the command":** the gateway did not send the
  command, usually because the radio channel was busy. Repeat the action.
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

The library stores its data in the directory `.storage/wms_webcontrol_pro-<entry id>/`:
`settings.json` holds the travel times and the rotation limits that were set or
learned, `state.json` the last known position and tilt of the covers. The directory is
removed when the config entry is removed.

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
