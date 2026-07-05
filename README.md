# ha-vialitoral

Home Assistant custom component for the [ViaLitoral](https://www.vialitoral.com) highway network in Portugal. Automatically discovers and exposes all public CCTV cameras as Home Assistant `camera` entities, plus a `select` entity that lets you switch between cameras dynamically from the frontend.

---

## Features

- **Auto-discovery** — fetches the full camera list from the ViaLitoral API at setup, then lets you pick which cameras to add
- **Camera entities** — one entity per selected CCTV, with live JPEG snapshots refreshed by a shared update coordinator on a configurable interval (2–10 min)
- **Select entity** — a single dropdown that lists all selected cameras; its state attributes expose the selected camera's HA entity ID and GPS coordinates, making it easy to drive Lovelace cards dynamically
- **Active camera** — a `camera.vialitoral_active` proxy entity that always shows whichever camera is chosen in the select, with no extra API calls
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
| `id` | Raw numeric camera ID from the API |
| `distance` | Kilometre marker from the camera name |

### Select entity (`select.active_camera`)

A single dropdown listing all selected camera names. Useful for building dynamic Lovelace dashboards.

State attributes:

| Attribute | Description |
|---|---|
| `total` | Total number of cameras available |
| `selected_camera_id` | Raw API numeric ID of the currently selected camera |
| `selected_entity_id` | Derived HA entity ID (e.g. `camera.some_location`) |
| `selected_latitude` | GPS latitude of the selected camera |
| `selected_longitude` | GPS longitude of the selected camera |

> **Note:** `selected_entity_id` is derived by slugifying the camera label. If a camera name contains accented characters or special symbols the slug may differ from what HA assigns. Use `selected_camera_id` as a reliable fallback.

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
        ├── coordinator.py            # DataUpdateCoordinator — single shared image refresh loop
        ├── const.py                  # Domain, config keys, shared helpers
        ├── camera.py                 # Camera platform — one VialitoralCamera entity per CCTV
        ├── select.py                 # Select platform — camera picker with rich state attributes
        ├── config_flow.py            # UI config flow (discover + pick cameras)
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
