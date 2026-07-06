# ha-vialitoral

Home Assistant custom component for the [ViaLitoral](https://www.vialitoral.com) highway network in Portugal. Automatically discovers and exposes all public CCTV cameras as Home Assistant `camera` entities, plus a `select` entity that lets you switch between cameras dynamically from the frontend.

---

## Features

- **Auto-discovery** — fetches the full camera list from the ViaLitoral API at setup, then lets you pick which cameras to add
- **Camera entities** — one entity per selected CCTV, with live JPEG snapshots refreshed by a shared update coordinator on a configurable interval (2–10 min)
- **Select entity** — a single dropdown that lists all selected cameras; its state attributes expose the selected camera's HA entity ID and GPS coordinates, making it easy to drive Lovelace cards dynamically
- **Active camera** — a `camera.vialitoral_active` proxy entity that always shows whichever camera is chosen in the select, with no extra API calls
- **Possible accident detection** — each camera watches its own image size and raises a `possible_accident` attribute when the live feed is replaced by ViaLitoral's small "unavailable" placeholder (often shown while an incident is being cleared)
- **Single HTTP session** — all requests share one `aiohttp.ClientSession` with a 10 s timeout; the session is properly closed on integration unload
- **Device grouping** — all entities are grouped under a single *Vialitoral CCTV* device in the HA device registry

---

## Requirements

| Requirement | Notes |
|---|---|
| Home Assistant | 2024.11 or newer |
| Python | 3.11+ (bundled with HA) |
| External access | HA instance must be able to reach `https://www.vialitoral.com` |

No additional Python packages are required beyond what ships with Home Assistant (`aiohttp` is already a core dependency).

---

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add `https://github.com/hanunes/ha-vialitoral` with category **Integration**
3. Search for *Vialitoral* and click **Download**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/vialitoral/` folder into your HA `<config>/custom_components/` directory
2. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Vialitoral CCTV**
3. Click **Submit** to discover the cameras (no credentials required)
4. Choose which cameras to add and set the refresh interval, then **Submit**

The integration fetches the camera list and creates the entities for your
selection. You can change the selection or interval later via the integration's
**Reconfigure** menu.

---

## Entities

### Camera entities (`camera.*`)

One entity is created per selected CCTV camera. Each entity exposes the following state attributes:

| Attribute | Description |
|---|---|
| `latitude` | GPS latitude of the camera |
| `longitude` | GPS longitude of the camera |
| `type` | Camera type as returned by the API (e.g. `vialitoral`) |
| `id` | Camera identifier (the API's `image` field) |
| `distance` | Kilometre marker from the camera name |
| `possible_accident` | `true` when the camera appears to be showing the placeholder image (see below) |
| `current_size` | Size in bytes of the most recent image |
| `baseline_size` | Rolling median size (bytes) of the camera's normal images |
| `drop_pct` | How far the current image has dropped below its baseline, as a percentage |

### Select entity (`select.active_camera`)

A single dropdown listing all selected camera names. Useful for building dynamic Lovelace dashboards.

State attributes:

| Attribute | Description |
|---|---|
| `total` | Number of selected cameras added to Home Assistant |
| `selected_camera_id` | Identifier (the API's `image` field) of the currently selected camera |
| `selected_entity_id` | Derived HA entity ID (e.g. `camera.some_location`) |
| `selected_latitude` | GPS latitude of the selected camera |
| `selected_longitude` | GPS longitude of the selected camera |

> **Note:** `selected_entity_id` is derived by slugifying the camera label. If a camera name contains accented characters or special symbols the slug may differ from what HA assigns. Use `selected_camera_id` as a reliable fallback.

### Active camera entity (`camera.vialitoral_active`)

A proxy camera that always serves the image of whichever camera is chosen in the select. Unlike the per-camera entities above, it exposes a smaller, select-driven attribute set (no `latitude`/`longitude`/`type`/`id`/`distance`):

| Attribute | Description |
|---|---|
| `active_camera` | Identifier (the API's `image` field) of the currently selected camera |
| `possible_accident` | `true` when the selected camera appears to be showing the placeholder image |
| `current_size` | Size in bytes of the selected camera's most recent image |
| `baseline_size` | Rolling median size (bytes) of the selected camera's normal images |
| `drop_pct` | How far the current image has dropped below its baseline, as a percentage |

---

## Possible Accident Detection

When a camera goes offline — for example while an incident is being cleared —
ViaLitoral replaces the live feed with a small, mostly-white "unavailable"
placeholder image. Because that placeholder is far smaller than a normal
highway frame, the integration can detect it by watching each camera's image
size.

**How it works**

- Every refresh, each camera's image size is compared against a rolling
  **median baseline** of its own recent normal sizes.
- A camera is flagged (`possible_accident: true`) only when the current image
  is **both**:
  - at least **70%** smaller than its baseline, **and**
  - under **80 KB** in absolute size.
- The baseline is built only from normal (non-flagged) frames, so a placeholder
  never poisons it, and it needs at least **3 samples** before any flag can be
  raised (avoiding cold-start false positives).
- Baselines are persisted to disk, so detection keeps working immediately after
  a Home Assistant restart.

> **Note:** This is a heuristic. It cannot tell the difference between an
> accident, scheduled maintenance, or a temporary camera outage — all of these
> show the same placeholder. Treat `possible_accident` as *"this camera is
> currently unavailable, possibly due to an incident"* rather than a confirmed
> accident.

### Events

In addition to the attribute, the integration fires a Home Assistant bus event
whenever a camera's flag changes state — ideal for edge-triggered automations:

| Event | Fired when |
|---|---|
| `vialitoral_accident_detected` | A camera starts showing the placeholder (`false → true`) |
| `vialitoral_accident_cleared` | A camera returns to its normal feed (`true → false`) |

Each event carries the following data:

| Field | Description |
|---|---|
| `camera_id` | Camera identifier (the API's `image` field) |
| `label` | Human-readable camera name |
| `latitude` / `longitude` | GPS coordinates of the camera |
| `current_size` | Size in bytes of the triggering image |
| `baseline_size` | Rolling median baseline size (bytes) |
| `drop_pct` | Percentage the image dropped below its baseline |
| `snapshot_path` | *(detected only)* Filesystem path (e.g. `/config/www/vialitoral/<camera_id>.jpg`) to the last good frame captured **before** the placeholder appeared. Useful for server-side file access, **not** for notification images |
| `snapshot_url` | *(detected only)* Companion-app URL for that same frame (`/local/vialitoral/<camera_id>.jpg`). Use this as the notification `image` |
| `entity_id` | *(cleared only)* The camera entity that now proxies the recovered live feed (e.g. `camera.some_location`). Build the live image URL as `/api/camera_proxy/<entity_id>` |

> **Note:** `snapshot_path`/`snapshot_url` capture the last normal frame seen
> *before* the camera went offline — so a notification shows the scene as it
> was just before the placeholder, not the placeholder itself. They are omitted
> if no good frame has been captured yet (e.g. the camera was already showing
> the placeholder when Home Assistant started), so guard with
> `{{ trigger.event.data.snapshot_url is defined }}`.

> **Note (notification images):** The companion apps need a **URL**, not a disk
> path. Use `snapshot_url` (the `/local/...` URL) for the detected image and
> `/api/camera_proxy/{{ entity_id }}` for the recovered live image, both under
> the notification's `image` key. `snapshot_path` is the raw filesystem path and
> will **not** load in a notification. On the iOS companion app you may instead
> pass `entity_id: {{ trigger.event.data.entity_id }}`, but `image` works on
> both Android and iOS.

### Automation examples

Using the event (recommended for notifications on change):

```yaml
automation:
  - alias: Notify on possible accident
    trigger:
      - platform: event
        event_type: vialitoral_accident_detected
    action:
      - service: notify.notify
        data:
          message: >-
            Possible incident at {{ trigger.event.data.label }}
            (camera unavailable, image {{ trigger.event.data.drop_pct }}% below normal).
          data:
            image: >-
              {{ trigger.event.data.snapshot_url
                 if trigger.event.data.snapshot_url is defined else '' }}
```

Notify when a camera recovers:

```yaml
automation:
  - alias: Notify on camera recovered
    trigger:
      - platform: event
        event_type: vialitoral_accident_cleared
    action:
      - service: notify.notify
        data:
          message: "{{ trigger.event.data.label }} is back online."
          data:
            image: "/api/camera_proxy/{{ trigger.event.data.entity_id }}"
```

Handle both events in one automation (detected + cleared):

```yaml
automation:
  - alias: Vialitoral incident status
    trigger:
      - platform: event
        event_type: vialitoral_accident_detected
        id: detected
      - platform: event
        event_type: vialitoral_accident_cleared
        id: cleared
    action:
      - choose:
          - conditions: "{{ trigger.id == 'detected' }}"
            sequence:
              - service: notify.notify
                data:
                  message: >-
                    Possible incident at {{ trigger.event.data.label }}
                    ({{ trigger.event.data.drop_pct }}% below normal).
                  data:
                    image: >-
                      {{ trigger.event.data.snapshot_url
                         if trigger.event.data.snapshot_url is defined else '' }}
          - conditions: "{{ trigger.id == 'cleared' }}"
            sequence:
              - service: notify.notify
                data:
                  message: "{{ trigger.event.data.label }} is back online."
                  data:
                    image: "/api/camera_proxy/{{ trigger.event.data.entity_id }}"
```

Using the attribute (for a single specific camera):

```yaml
automation:
  - alias: Notify on possible accident (specific camera)
    trigger:
      - platform: template
        value_template: "{{ state_attr('camera.some_location', 'possible_accident') }}"
    action:
      - service: notify.notify
        data:
          message: "Possible incident: the ViaLitoral camera at some_location is unavailable."
```

---

## Lovelace Examples

### Show the currently selected camera

```yaml
type: picture-entity
entity: camera.vialitoral_active
```

### Camera selector + live view side by side

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - select.active_camera
  - type: picture-entity
    entity: camera.vialitoral_active
    show_name: true
```

> **Note:** Built-in Lovelace cards (`picture-entity`, `picture-glance`) may take a moment to reflect the newly selected camera due to browser-side image caching. For immediate updates install the [Advanced Camera Card](https://github.com/dermotduffy/advanced-camera-card) custom card from HACS and use:
> ```yaml
> type: custom:advanced-camera-card
> cameras:
>   - camera_entity: camera.vialitoral_active
>     live_provider: image
> ```

### All cameras in a grid

```yaml
type: grid
columns: 3
cards:
  - type: picture-entity
    entity: camera.some_location
  # repeat for each camera entity
```

---

## Architecture

```
ha-vialitoral/                        # repository root
├── README.md
└── custom_components/
    └── vialitoral/
        ├── __init__.py               # Integration setup/unload, shared coordinator in hass.data
        ├── api.py                    # aiohttp HTTP client for vialitoral.com
        ├── coordinator.py            # DataUpdateCoordinator — shared image refresh loop + placeholder detection
        ├── const.py                  # Domain, config keys, shared helpers
        ├── camera.py                 # Camera platform — one VialitoralCamera entity per CCTV
        ├── select.py                 # Select platform — camera picker with rich state attributes
        ├── config_flow.py            # UI config flow (discover + pick cameras)
        ├── strings.json              # Config-flow UI text (source)
        ├── translations/             # Localised config-flow text (en.json, …)
        └── manifest.json             # Integration metadata
```

**Data flow:**

1. `async_setup_entry` (`__init__.py`) creates a single `Api` instance and a `VialitoralCoordinator`, performs the first refresh, and stores the coordinator in `hass.data[DOMAIN][entry.entry_id]`
2. Both `camera.py` and `select.py` read the shared coordinator from `hass.data` — no duplicate HTTP sessions
3. On unload, `async_unload_entry` closes the `aiohttp.ClientSession` and removes the entry from `hass.data`

---

## Contributing

Pull requests are welcome. Please open an issue first to discuss significant changes.

---

## License

MIT
