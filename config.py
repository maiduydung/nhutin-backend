import os
import json
from math import exp
from dotenv import load_dotenv
import logging

# Azure Key Vault stuff
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Load .env
load_dotenv()

# Basic logging configuration so logs show up when running modules directly
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Try to load local.settings.json
try:
    with open('local.settings.json', 'r') as f:
        settings = json.load(f)
        local_settings = settings.get('Values', {})
except (FileNotFoundError, json.JSONDecodeError):
    local_settings = {}

# # Attempt to get a Key Vault client
# def get_keyvault_client():
#     kv_name = "proplytics-key-vault"
#     try:
#         vault_url = f"https://{kv_name}.vault.azure.net"
#         logger.info(f"🔑 Key Vault URL: {vault_url}")
        
#         #User Assigned Managed Identity data-mi-container-prod Client ID to access Key Vault
#         credential = DefaultAzureCredential(managed_identity_client_id=os.getenv("UAMI_CLIENT_ID"))
#         return SecretClient(vault_url=vault_url, credential=credential)
#     except Exception as e:
#         logger.error(f"❌ Failed to initialize Key Vault client: {e}")
#         return None

# _keyvault_client = get_keyvault_client()

# # Helper: normalize Key Vault secret names
# def normalize_secret_key(key):
#     return key.replace("_", "-")

# Main config getter
def get_config(key, default=None):
    # 1. Check local.settings.json
    if key in local_settings:
        return local_settings[key]

    # 2. Check environment variables
    if os.getenv(key):
        return os.getenv(key)

    # # 3. Check Azure Key Vault
    # if _keyvault_client:
    #     try:
    #         secret_name = normalize_secret_key(key)
    #         return _keyvault_client.get_secret(secret_name).value
    #     except Exception:
    #         pass

    # 4. Fallback default
    return default

FORM_RECOGNIZER_ENDPOINT = get_config("FORM_RECOGNIZER_ENDPOINT")
FORM_RECOGNIZER_KEY = get_config("FORM_RECOGNIZER_KEY")
POSTGRES_USER = get_config("POSTGRES_USER")
POSTGRES_PASSWORD = get_config("POSTGRES_PASSWORD")
POSTGRES_HOST = get_config("POSTGRES_HOST")
POSTGRES_PORT = get_config("POSTGRES_PORT")
POSTGRES_DATABASE = get_config("POSTGRES_DATABASE")

WALKING_FLOORS = {
    # Weight of each walking floor type in kg, used for weight optimization and Items.type lookup
    "KSD": {
        "type": "walking_floor_ksd",
        "weight": 503,
    },
    "KMD": {
        "type": "walking_floor_kmd",
        "weight": 502,
    },
    "R2DX": {
        "type": "walking_floor_r2dx",
        "weight": 751,
    },
}

# Container Building Material Specifications
# Based on: THUYETMINHKYTHUAT.pdf - Walking Floor S-Drive KSD 4.25" system
# These specs define materials needed to BUILD a container from raw materials
# when a pre-built container is unavailable
CONTAINER_BUILD_SPECS = {
    # 40ft container with Walking Floor system (12.192m / 40 feet)
    # Reference: THAICUONG 23062025 THUYETMINHKYTHUAT.pdf
    "40ft": {
        "length_m": 12.192,
        # Aluminum bars for walking floor (Nhôm thanh #000)
        # 25 bars × 12m × 2.53 kg/m = 756.76 kg
        # 21 bars for floor slats + 4 bars for accessories/cover plates
        "aluminum_kg": 757,
        # Steel frame components (Khung phụ thép chịu tải 32-40 tấn)
        # - Sắt hộp vuông kẽm: 332.34 kg (~55m hộp 80×40 or 100×50)
        # - Thép vuông kẽm: 398.48 kg (~124m thép vuông 40×40mm)  
        # - Thép vuông mạ kẽm: 252.41 kg (~84m thép vuông 30×30-40×40mm)
        # Total steel frame: ~983 kg
        "steel_frame_kg": 983,
        # Steel plates for floor reinforcement (Thép tấm gia cố sàn/vách)
        # - 10ly: 244.48 kg (for S-Drive base, heavy load)
        # - 8ly: 58.93 kg (reinforcement ribs, connection plates)
        # - 5ly: 247.54 kg (floor base reinforcement)
        # - 4ly: 590.73 kg (floor patching, wall covering)
        # - 3ly: 282.67 kg (oil tank, inner covers, equipment covers)
        # Total plates: ~1,424 kg
        # Note: May not be available in inventory - use steel_box as substitute
        "steel_plate_kg": 1424,
        # Steel U-channel (Thép hình U)
        # - U thường: 33.67 kg (edge trim, auxiliary connections)
        # - U100: 34.03 kg (rear door frame, load-bearing edge)
        # - U120: 60.88 kg (longitudinal beam under floor, 40-ton discharge load)
        # Total U-channel: ~129 kg
        "steel_u_kg": 129,
        # Galvanized sheets (Tôn mạ kẽm)
        # Used for roof and wall panels, estimated based on surface area
        # 40ft container surface area: ~80-100 m²
        "galvanized_sheet_m": 100,
    },
    # 20ft container (6.096m / 20 feet) - roughly half of 40ft
    "20ft": {
        "length_m": 6.096,
        "aluminum_kg": 378,  # ~half of 40ft
        "steel_frame_kg": 492,  # ~half of 40ft
        "steel_plate_kg": 712,  # ~half of 40ft
        "steel_u_kg": 65,  # ~half of 40ft
        "galvanized_sheet_m": 50,  # ~half of 40ft
    },
}

# Material type mappings for container building
# Maps spec keys to database item types
CONTAINER_MATERIAL_TYPES = {
    "aluminum": ["aluminum"],
    "steel_frame": ["steel_box", "steel_square", "steel_galvanized_square"],
    "steel_plate": ["steel_plate"],
    "steel_u": ["steel_u"],
    "galvanized_sheet": ["galvanized_sheet"],
}

# Material substitution rules
# When primary material is unavailable, these alternatives can be used
MATERIAL_SUBSTITUTES = {
    "steel_frame": {
        # If steel_box insufficient, can use steel_square or steel_plate
        "alternatives": ["steel_plate", "aluminum"],
        "conversion_ratio": 1.0,  # 1 kg steel = 1 kg substitute (weight-based)
    },
    "steel_plate": {
        # If steel_plate insufficient, can use steel_box
        "alternatives": ["steel_box"],
        "conversion_ratio": 1.0,
    },
}

# =============================================================================
# Container Type Configuration
# =============================================================================

# Container types that include a container item (pre-built or built from materials)
CONTAINER_TYPES_WITH_CONTAINER = ["container_20ft", "container_40ft"]

# Container types that do NOT include container item (structure only)
CONTAINER_TYPES_WITHOUT_CONTAINER = ["mooc_long", "thung_xe_tai"]

# All valid container types
ALL_CONTAINER_TYPES = CONTAINER_TYPES_WITH_CONTAINER + CONTAINER_TYPES_WITHOUT_CONTAINER

# Empty weight of pre-built containers (kg)
# Only applies when using pre-built container from inventory
CONTAINER_EMPTY_WEIGHTS = {
    "container_20ft": 1900,  # kg
    "container_40ft": 2500,  # kg
    # mooc_long and thung_xe_tai don't have container, so no weight
}

# Default container lengths (meters)
CONTAINER_DEFAULT_LENGTHS = {
    "container_20ft": 6.096,
    "container_40ft": 12.192,
    "mooc_long": 15.0,
    "thung_xe_tai": 15.0,
}

# Base reference for material scaling (40ft container)
MATERIAL_SCALING_BASE = {
    "length_m": 12.192,  # 40ft in meters
    "steel_frame_kg": 983,  # kg
    "galvanized_sheet_m": 100,  # meters
}