"""Constants for the Macless Haystack integration."""

DOMAIN = "macless_haystack"

CONF_MODE = "mode"
CONF_ENDPOINT = "endpoint"
CONF_ACCESSORIES = "accessories"
CONF_AUTH_USER = "auth_user"
CONF_AUTH_PASS = "auth_pass"
CONF_APPLE_ID = "apple_id"
CONF_ACCOUNT = "account"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DAYS = "days"

MODE_APPLE = "apple"
MODE_ENDPOINT = "endpoint"
DEFAULT_MODE = MODE_APPLE

DEFAULT_ENDPOINT = ""
DEFAULT_SCAN_INTERVAL = 900
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 86400
DEFAULT_DAYS = 3
MIN_DAYS = 1
MAX_DAYS = 30

REQUEST_TIMEOUT = 300

# The anisette engine needs a library bundle of about 2 MB.
ANISETTE_STORAGE_DIR = "macless_haystack"
ANISETTE_LIBS_FILE = "anisette_libs.bin"

# Seconds between 1904-01-01 and 1970-01-01.
APPLE_EPOCH_OFFSET = 978307200

# Battery field of the status byte, two bits.
BATTERY_PERCENT = {0: 100, 1: 50, 2: 20, 3: 5}
BATTERY_STATUS = {0: "full", 1: "medium", 2: "low", 3: "critical"}
