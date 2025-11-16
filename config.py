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