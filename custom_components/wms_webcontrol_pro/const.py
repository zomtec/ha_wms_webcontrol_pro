"""Constants for the WMS WebControl pro integration."""

from datetime import timedelta

DOMAIN = "wms_webcontrol_pro"
SUGGESTED_HOST = "webcontrol"

ATTRIBUTION = "Data provided by WMS WebControl pro API"
MANUFACTURER = "WAREMA Renkhoff SE"

# The hub is a radio gateway, a long interval keeps the radio traffic low. The
# hub and each destination are asked once in this time, evenly spread over it.
BASE_POLL_INTERVAL = timedelta(minutes=30)
# Shortest time between two regular requests, for hubs with many destinations.
MIN_POLL_INTERVAL = timedelta(seconds=10)
# Time between two requests while a destination was not asked yet after the start.
STARTUP_POLL_INTERVAL = timedelta(seconds=15)
# A hub that did not answer is asked again after this many seconds.
RETRY_AFTER_FAILURE = 60.0
# Pause between two status requests to the hub. Requests after a scene or after
# commands for several destinations fall together and are spread by it.
STATUS_REQUEST_SPACING = 10.0

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
# Seconds until every destination is asked after a scene. The hub does not tell
# which drives a scene moves or for how long, so this is the delay that the
# library uses for a drive of unknown duration.
SETTLE_SCENE = 120.0
