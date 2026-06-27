import os
from . import robert, mike


def get_entities():
    profile = os.environ.get("TV_PROFILE", "mike").lower()
    if profile == "robert":
        return robert.ENTITIES
    return mike.ENTITIES
