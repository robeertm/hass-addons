import os
from profiles import get_entities

HA_BASE_URL = os.environ.get("HA_BASE_URL", "http://supervisor/core")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
REFRESH_INTERVAL_SEC = int(os.environ.get("REFRESH_INTERVAL_SEC", "15"))
PAGE_ROTATE_SEC = int(os.environ.get("PAGE_ROTATE_SEC", "22"))
PROFILE = os.environ.get("TV_PROFILE", "mike").lower()

ENTITIES = get_entities()
