# Changelog

## 0.3.0 (unreleased)

Requires `pywmswebcontrolpro` 0.3.0.

Breaking changes:

- The stored data moves to two files for each hub, `settings.json` and `state.json` in
  `.storage/wms_webcontrol_pro-<entry id>/`. The files of earlier versions
  (`<destination id>/<action id>.json`) are not read: enter the travel times and
  changed rotation limits again after the update. The old directories can be deleted.

## 0.2.1

Requires `pywmswebcontrolpro` 0.2.1.

Fixed:

- A status that contains the rotation of the slats but no position updates the tilt
  position. Before, such a status was dropped.
- A destination that is renamed on the gateway gets the new name as device name with
  the next reading of the configuration. A name given in Home Assistant and the
  entity ids stay as they are.

## 0.2.0

Requires `pywmswebcontrolpro` 0.2.0.

Breaking changes:

- The rotation limits of slat drives are -75 and 75 by default. Before, the number
  entities showed these values, but the cover used the limits of the gateway (-127 and
  127) until a limit was set by hand. Tilt positions of such covers change accordingly.
- A tilt position is sent as a whole rotation within the limits. Before, tilt 100 was
  sent one step below the minimum and values in between as decimals.
- A command that the gateway rejects or does not answer raises an error for covers,
  lights, switches, the rotation number, the identify button and scenes. Before, a
  rejected cover command was only logged and the other platforms ignored the answer.
- The devices of rooms have a new identifier. Their old devices are removed after the
  second reading of the configuration, the scene entities move to the new devices.
- The valance of an awning is named *Valance*. An existing entity keeps its entity id.

Added:

- Every destination is asked for its status two minutes after a scene.
- The awning and the valance of one destination each get their own status request.
- Translated values of the attribute `position_source`.

Fixed:

- A single failed request for the configuration no longer makes all entities
  unavailable for 30 minutes. A gateway that does not answer is asked again every
  minute.
- Values and fields of a newer firmware no longer break the setup or the updates.
- A device is only removed when two readings of the configuration in a row do not
  contain it. A scene that is gone is removed.
- Reconfigure recognizes another gateway also while the entry is not loaded, and a
  second setup of the same gateway also while its entry is not loaded.
- A gateway that answers the ping with an error is not set up.
- The reset button returns to the default limits instead of the limits of the gateway.

## 0.1.0

- First release.
