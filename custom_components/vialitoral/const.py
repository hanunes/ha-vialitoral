"""Constants and shared helpers for the Vialitoral integration."""

DOMAIN = "vialitoral"

CONF_CAMERAS = "cameras"
CONF_SCAN_INTERVAL = "scan_interval"

# Default refresh interval (minutes) when none is stored in the config entry.
DEFAULT_SCAN_INTERVAL = 5


def camera_label(cam: dict) -> str:
    """Return the human-readable label for a camera.

    The API name looks like ``km 12.3 Some Place``; the label is everything
    after the kilometre marker (``Some Place``).
    """
    return " ".join(cam["name"].split(" ")[2:])
