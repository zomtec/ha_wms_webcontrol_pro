"""Constants for the WMS WebControl pro integration."""

from datetime import timedelta

DOMAIN = "ha_wms_webcontrol_pro"
SUGGESTED_HOST = "webcontrol"

ATTRIBUTION = "Data provided by WMS WebControl pro API"
MANUFACTURER = "WAREMA Renkhoff SE"

# The hub is a radio gateway, a long interval keeps the radio traffic low.
BASE_POLL_INTERVAL = timedelta(minutes=30)
# Pause between two status requests to the hub.
STATUS_REQUEST_SPACING = 2.0

SERVICE_SET_COVER_POSITION_AND_TILT = "set_cover_position_and_tilt"

# A deviating measurement is checked again, up to this many times.
FOLLOW_UP_POLL_DELAY = 30.0
MAX_FOLLOW_UP_POLLS = 3
# How often the calculated position of a running drive is written.
TRAVEL_UPDATE_INTERVAL = timedelta(seconds=1)
ATTR_POSITION_SOURCE = "position_source"
# Seconds until the status is requested after a rotation command.
SETTLE_ROTATION = 5.0

BRIGHTNESS_SCALE = (1, 100)
# Seconds until the status is requested after a light or switch command.
SETTLE_SWITCH = 2.0
