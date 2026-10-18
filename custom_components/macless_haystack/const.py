"""Constants for the Macless Haystack integration."""

DOMAIN = "macless_haystack"

CONF_ENDPOINT = "endpoint"
CONF_ACCESSORIES = "accessories"
CONF_AUTH_USER = "auth_user"
CONF_AUTH_PASS = "auth_pass"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DAYS = "days"

DEFAULT_ENDPOINT = "http://192.168.0.15:6176"
DEFAULT_SCAN_INTERVAL = 900
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 86400
DEFAULT_DAYS = 3
MIN_DAYS = 1
MAX_DAYS = 30

REQUEST_TIMEOUT = 300

# Seconds between 1904-01-01 and 1970-01-01.
APPLE_EPOCH_OFFSET = 978307200

# Battery field of the status byte, two bits.
BATTERY_PERCENT = {0: 100, 1: 50, 2: 20, 3: 5}
BATTERY_STATUS = {0: "full", 1: "medium", 2: "low", 3: "critical"}
