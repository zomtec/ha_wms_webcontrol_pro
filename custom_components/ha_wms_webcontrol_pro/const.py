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
