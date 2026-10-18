# Macless Haystack for Home Assistant

Track a [Macless Haystack](https://github.com/dchristl/macless-haystack) beacon
from Home Assistant. The integration shows the beacon on the Home Assistant map
and gives you sensors for the battery, the accuracy, and the last report.

The integration gets the FindMy reports in one of two ways.

| Mode | What it needs | What it does |
| --- | --- | --- |
| Apple ID | Your Apple ID and the accessory JSON | Logs in to Apple, makes the anisette data locally, fetches the reports, and decrypts them. No other server. |
| Endpoint | The URL of a macless-haystack endpoint and the accessory JSON | Polls the endpoint and decrypts the reports. |

The Apple ID mode is the default. It runs fully inside Home Assistant. No Mac,
no Docker, and no anisette server are necessary.

## Entities

Each accessory becomes one Home Assistant device with these entities:

| Entity | Type | Description |
| --- | --- | --- |
| `device_tracker.NAME` | device tracker | Latest position, with map history |
| `sensor.NAME_battery` | sensor | Battery level in percent, exact status as an attribute |
| `sensor.NAME_accuracy` | sensor | Horizontal accuracy of the latest report in meters |
| `sensor.NAME_last_seen` | sensor | Time of the latest report |

The device tracker holds these attributes: `confidence`, `battery`,
`raw_status`, and `last_seen`. The tracker state is `home`, `not_home`, or the
name of a zone. You can use the state in automations.

## Requirements

- Home Assistant 2025.6 or later.
- An Apple ID with 2FA. The second factor can be an SMS or a trusted device.
- The accessory JSON with your private keys. Export it from the Accessories
  page of the macless-haystack web portal, or use the file that
  `haystack keys` writes. Keep this file private.
- Internet access. The integration contacts Apple. It also installs the
  [FindMy.py](https://github.com/malmeloo/FindMy.py) library from PyPI.

For the endpoint mode you also need a running macless-haystack endpoint that is
reachable from the Home Assistant host.

## Installation

### HACS

1. Open HACS.
2. Select the three dots in the top right corner, then "Custom repositories".
3. Add `https://github.com/ketan21/ha-macless-haystack` with category
   "Integration".
4. Search for "Macless Haystack" and install it.
5. Restart Home Assistant.

### Manual

Copy the folder `custom_components/macless_haystack` into the `config` folder of
Home Assistant, so that the result is
`config/custom_components/macless_haystack/manifest.json`, and restart Home
Assistant.

## Configuration

1. Go to Settings > Devices & services > Add integration.
2. Search for "Macless Haystack".
3. Choose the mode.

### Apple ID mode

1. Enter your Apple ID and password. The password is used one time. It is not
   stored.
2. Choose the second factor. Apple sends a code to a trusted device or by SMS.
3. Enter the code.
4. Paste the accessory JSON and submit.

The first setup downloads a library bundle of about 2 MB for the anisette
engine. The integration caches the bundle. Later starts need no download.

### Endpoint mode

1. Set the endpoint URL, for example `http://192.168.0.15:6176`.
2. Add the user name and password only when you set `endpoint_user` and
   `endpoint_pass` in the endpoint `config.ini`.
3. Paste the accessory JSON and submit.

### Options

Open the integration options to change these values:

- Update interval. Default: 900 seconds.
- Report window in days. Default: 3.

## Dashboard

A map card shows the position and the trail of the tracker. Add this code to a
dashboard in the raw editor. Replace `nanobeacon` with your device name.

```yaml
views:
  - title: Beacon
    cards:
      - type: map
        entities:
          - device_tracker.nanobeacon
        hours_to_show: 72
        default_zoom: 14
      - type: history-graph
        entities:
          - entity: sensor.nanobeacon_last_seen
          - entity: sensor.nanobeacon_battery
        hours_to_show: 24
      - type: entities
        entities:
          - entity: device_tracker.nanobeacon
          - entity: sensor.nanobeacon_last_seen
          - entity: sensor.nanobeacon_battery
          - entity: sensor.nanobeacon_accuracy
```

## Automation example

Tell when the beacon leaves the home zone:

```yaml
triggers:
  - trigger: state
    entity_id: device_tracker.nanobeacon
    from: home
    to: not_home
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: The beacon left home.
```

## Data and privacy

- The Apple ID password is not stored. At a reauth you enter it again.
- The session token is stored in the Home Assistant config entry. The token
  lets the integration fetch your reports.
- The anisette libraries are cached in
  `/config/.storage/macless_haystack/anisette_libs.bin`.
- The decryption runs in Home Assistant. Your keys and the location history
  stay in your system.

## Notes and limits

- The tracker is `unknown` until an iPhone or another Apple device hears the
  beacon and Apple sends a report. This can take a few minutes.
- The Apple ID session expires after some months. Home Assistant then shows a
  repair and asks for a new login (reauth).
- When the report source is unreachable, Home Assistant keeps the last known
  position and continues when the source answers again.
- The battery levels are estimates. The beacon reports four levels only.
- Apple changes the protocol from time to time. The FindMy.py library then
  needs an update.
- This integration shows the history that Home Assistant records. It does not
  show the history of the Apple cloud.

## Troubleshooting

| Problem | Cause and solution |
| --- | --- |
| `unknown` state | No report arrived yet. Check that the beacon sends. |
| Wrong Apple ID or password | Check the credentials. Apple can also lock an account after many failed tries. |
| Wrong or expired verification code | Request a new code and enter it quickly. |
| Cannot connect | No internet, or Apple did not answer. Try again later. |
| Cannot connect (endpoint mode) | Home Assistant cannot reach the endpoint. Test the URL in a browser on the same network. |
| No reports after a key change | The beacon was re-flashed with new keys. Add the new accessory JSON as a new integration entry and remove the old entry. |

## Credits

- [FindMy.py](https://github.com/malmeloo/FindMy.py) (MIT) for the Apple login,
  the anisette engine, and the report decryption.
- [Macless Haystack](https://github.com/dchristl/macless-haystack) and
  [OpenHaystack](https://github.com/seemoo-lab/openhaystack) for the beacon
  tooling and the report format.

## License

MIT
