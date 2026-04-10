import os
from src.adapters.getcontact_client import GetContactClient
from dotenv import load_dotenv

load_dotenv()

# New theories for X-Token
API_TOKEN_RAW = "DGt4zG3FiM9Oj_9RERADvw"
CANDIDATES = [
    f"{API_TOKEN_RAW}==",           # Base64 padding fixed
    f"{API_TOKEN_RAW}=",            # Base64 padding single
    "AnKlaRo0QGDvQfPQJj1h4uyIR",    # From logs
    "28d4ca6b8b8f1a61096ac1f07a9aa28c8a4fcbbfa", # Original from .env
]

DEVICE_ID = "8b7557a9db284ada"
AES_KEY = "6c9f717a4a082d9727e7dd2ca5a032cf"
PHONE = "+380930075122"

print(f"--- PROTOCOL PROBE ---")

for token in CANDIDATES:
    print(f"\n[TARGET TOKEN: {token}]")
    os.environ["GETCONTACT_DEVICE_ID"] = DEVICE_ID
    try:
        client = GetContactClient(token, AES_KEY)
        info = client.get_full_info(PHONE)
        if info and info.get("displayName"):
            print(f"✅ FOUND IT! Token: {token}")
            exit(0)
        else:
            print(f"❌ 403 or No Result")
    except Exception as e:
        print(f"⚠️ Error: {e}")

print("\n--- PROBE FAILED ---")
