import os
from src.adapters.getcontact_client import GetContactClient
from dotenv import load_dotenv

load_dotenv()

# Well-known secret keys from older/leaked implementations
SECRET_KEYS = [
    "6c9f717a4a082d9727e7dd2ca5a032cf", # MD5 of api_token
    "4595a8987ec46029f6323c2a059d648f", # Known legacy secret
    "1603ab5ec6e7683c754f58b764f087c8", # Another candidate
]

TOKEN = "AnKlaRo0QGDvQfPQJj1h4uyIR" # Using the string from your logs
DEVICE_ID = "8b7557a9db284ada"
PHONE = "+380930075122"

print(f"--- SECRET KEY PROBE ---")

for key in SECRET_KEYS:
    print(f"\n[KEY: {key}]")
    os.environ["GETCONTACT_DEVICE_ID"] = DEVICE_ID
    try:
        client = GetContactClient(TOKEN, key)
        info = client.get_full_info(PHONE)
        if info and info.get("displayName"):
            print(f"✅ BINGO! Key worked: {key}")
            exit(0)
        else:
            print(f"❌ 403")
    except Exception as e:
        print(f"⚠️ Error: {e}")

print("\n--- PROBE FAILED ---")
