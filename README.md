# Macless Haystack for Home Assistant

Track a [Macless Haystack](https://github.com/dchristl/macless-haystack) beacon
from Home Assistant. The integration polls your local macless-haystack endpoint,
decrypts the FindMy reports with your private keys, and shows the beacon on the
Home Assistant map.

No Apple hardware is necessary. No MQTT broker is necessary.

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

1. A running macless-haystack endpoint, reachable from the Home Assistant host.
   The endpoint address looks like `http://192.168.0.15:6176`.
2. The accessory JSON with your private keys. Export it from the Accessories
   page of the macless-haystack web portal, or use the file that
   `haystack keys` writes. Keep this file private.

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
3. Step 1: set the endpoint URL, for example `http://192.168.0.15:6176`. Add the
   user name and password only when you set `endpoint_user` and `endpoint_pass`
   in the endpoint `config.ini`. This integration does not support TLS. Use a
   plain HTTP endpoint on the LAN.
4. Step 2: paste the accessory JSON and submit.

The endpoint answers with reports for the last N days. The default window is 3
days. Change the window and the update interval in the integration options. The
default update interval is 900 seconds.

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

## Notes and limits

- The tracker is `unknown` until an iPhone or another Apple device hears the
  beacon and Apple sends a report. This can take a few minutes.
- The endpoint runs on your server. When the endpoint is unreachable, Home
  Assistant keeps the last known position and continues when the endpoint
  answers again.
- The battery levels are estimates. The beacon reports four levels only.
- This integration shows the history that Home Assistant records. It does not
  show the history of the Apple cloud.

## Troubleshooting

| Problem | Cause and solution |
| --- | --- |
| `unknown` state | No report arrived yet. Check that the beacon sends, and that the portal shows a location. |
| Cannot connect | Home Assistant cannot reach the endpoint. Test the URL in a browser on the same network. |
| Wrong user name or password | The endpoint has basic authentication. Set `endpoint_user` and `endpoint_pass`. |
| No reports after a key change | The beacon was re-flashed with new keys. Add the new accessory JSON as a new integration entry and remove the old entry. |

## License

MIT
