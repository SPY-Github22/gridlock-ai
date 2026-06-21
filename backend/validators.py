"""
validators.py
-------------
Shared Pydantic field validators for Bangalore geographic bounds.
Written once here, imported everywhere — no copy-paste drift.
"""

BANGALORE_LAT_MIN = 12.7
BANGALORE_LAT_MAX = 13.2
BANGALORE_LON_MIN = 77.4
BANGALORE_LON_MAX = 77.8


def validate_latitude(v):
    """Validate that a latitude value falls within Bangalore bounds."""
    if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
        raise TypeError("Latitude must be a float or integer")
    v = float(v)
    if not (BANGALORE_LAT_MIN <= v <= BANGALORE_LAT_MAX):
        raise ValueError(
            f"Latitude must be within Bengaluru bounds "
            f"[{BANGALORE_LAT_MIN}, {BANGALORE_LAT_MAX}]"
        )
    return v


def validate_longitude(v):
    """Validate that a longitude value falls within Bangalore bounds."""
    if v is None or not isinstance(v, (int, float)) or isinstance(v, bool):
        raise TypeError("Longitude must be a float or integer")
    v = float(v)
    if not (BANGALORE_LON_MIN <= v <= BANGALORE_LON_MAX):
        raise ValueError(
            f"Longitude must be within Bengaluru bounds "
            f"[{BANGALORE_LON_MIN}, {BANGALORE_LON_MAX}]"
        )
    return v
