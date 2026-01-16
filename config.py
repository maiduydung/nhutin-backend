"""
Configuration module for Nhu Tin Backend.
Loads settings from local.settings.json, environment variables.
"""
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load local.settings.json
try:
    with open("local.settings.json", "r") as f:
        settings = json.load(f)
        localSettings = settings.get("Values", {})
except (FileNotFoundError, json.JSONDecodeError):
    localSettings = {}


def getConfig(key: str, default=None):
    """Get config from local.settings.json or environment."""
    if key in localSettings:
        return localSettings[key]
    return os.getenv(key, default)


# Database config
POSTGRES_USER = getConfig("POSTGRES_USER")
POSTGRES_PASSWORD = getConfig("POSTGRES_PASSWORD")
POSTGRES_HOST = getConfig("POSTGRES_HOST")
POSTGRES_PORT = getConfig("POSTGRES_PORT")
POSTGRES_DATABASE = getConfig("POSTGRES_DATABASE")

# =============================================================================
# Walking Floor Configuration
# =============================================================================
WALKING_FLOORS = {
    "R2DX": {"type": "walking_floor_r2dx", "weight": 751},
    "KSD": {"type": "walking_floor_ksd", "weight": 503},
    "KMD": {"type": "walking_floor_kmd", "weight": 502},
}

# =============================================================================
# Container Type Configuration
# =============================================================================
CONTAINER_TYPES_WITH_CONTAINER = ["container_20ft", "container_40ft"]
CONTAINER_TYPES_WITHOUT_CONTAINER = ["mooc_long", "thung_xe_tai"]

# Pre-built container empty weights (kg)
CONTAINER_EMPTY_WEIGHTS = {
    "container_20ft": 1900,
    "container_40ft": 2500,
}

# Default weight for existing truck body when buildContainer=False
# Used when user has existing truck body but doesn't specify weight
DEFAULT_EXISTING_TRUCK_BODY_WEIGHT = 1800  # kg (typical truck body)

# Default lengths (meters) - used if user doesn't specify
CONTAINER_DEFAULT_LENGTHS = {
    "container_20ft": 6.096,
    "container_40ft": 12.192,
    "mooc_long": 15.0,
    "thung_xe_tai": 15.0,
}

# =============================================================================
# Container Build Specs (when building from materials)
# Based on: THUYETMINHKYTHUAT.pdf - Walking Floor S-Drive KSD 4.25"
# =============================================================================
CONTAINER_BUILD_SPECS = {
    "40ft": {
        "length_m": 12.192,
        "steel_frame_kg": 983,
        "galvanized_sheet_m": 100,
    },
    "20ft": {
        "length_m": 6.096,
        "steel_frame_kg": 492,
        "galvanized_sheet_m": 50,
    },
}

# =============================================================================
# Hydraulic Equipment
# =============================================================================
HYDRAULIC_PUMP_MAP = {
    "R2DX": "130cc",
    "KSD": "108cc",
    "KMD": "108cc",
}

HYDRAULIC_OIL_WEIGHT_KG = 200  # Full barrel ~200kg (oil + drum)
HYDRAULIC_PUMP_WEIGHT_KG = 50  # Approximate pump weight

# Emails
SENDER_EMAIL = "maiduydungvn@gmail.com"
SENDER_EMAIL_APP_PASSWORD = getConfig("SENDER_EMAIL_APP_PASSWORD")
EMAILS = ["maiduydungvn@gmail.com"]
