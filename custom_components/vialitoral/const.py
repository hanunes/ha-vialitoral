"""Constants and shared helpers for the Vialitoral integration."""

DOMAIN = "vialitoral"

CONF_CAMERAS = "cameras"
CONF_SCAN_INTERVAL = "scan_interval"

# Default refresh interval (minutes) when none is stored in the config entry.
DEFAULT_SCAN_INTERVAL = 5

# Public map of camera locations, surfaced in the config flow descriptions.
MAP_URL = "https://www.vialitoral.com/map"

# --- "Possible accident" placeholder detection -----------------------------
# When a camera is offline (e.g. an accident is being cleared) Vialitoral
# serves a small, mostly-white placeholder JPEG instead of the live frame.
# We detect it by comparing each camera's current image size against a rolling
# median baseline of its own normal sizes.

# HA storage key/version for persisting per-camera size baselines across
# restarts, so detection works immediately without re-learning.
STORAGE_KEY = "vialitoral_size_baseline"
STORAGE_VERSION = 1

# Flag a camera only if the current image dropped by at least this fraction
# below its baseline (0.7 == the image is under 30% of its normal size).
SIZE_DROP_THRESHOLD = 0.7

# Secondary absolute guard: the current image must also be smaller than this
# many bytes to be considered a placeholder.
ABSOLUTE_MAX_PLACEHOLDER_BYTES = 80_000

# Number of normal (non-flagged) samples required before a baseline is trusted
# enough to flag drops. Avoids cold-start false positives.
MIN_BASELINE_SAMPLES = 3

# How many recent non-flagged sizes to keep per camera for the median baseline.
BASELINE_HISTORY_SIZE = 20

# Bus events fired when a camera's placeholder flag changes state, carrying a
# payload with the camera id, entity label and size stats. Useful for
# edge-triggered automations (platform: event).
EVENT_ACCIDENT_DETECTED = f"{DOMAIN}_accident_detected"
EVENT_ACCIDENT_CLEARED = f"{DOMAIN}_accident_cleared"

# Subdirectory under the HA ``www`` folder where the last good frame is written
# when a possible accident is detected, so automations can attach it to a
# notification. Files are served at ``/local/vialitoral/<camera_id>.jpg``.
SNAPSHOT_DIR = "vialitoral"


def camera_label(cam: dict) -> str:
    """Return the human-readable label for a camera.

    The API name looks like ``km 12.3 Some Place``; the label is everything
    after the kilometre marker (``Some Place``).
    """
    return " ".join(cam["name"].split(" ")[2:])
