import os
import requests
from src.adapters.getcontact_client import GetContactClient
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GETCONTACT_TOKEN")
AES_KEY = os.getenv("GETCONTACT_AES_KEY")
DEVICE_ID = os.getenv("GETCONTACT_DEVICE_ID")

PHONE = "+380930075122" # Test number

print(f"--- THE GOLDEN KEY VERIFICATION ---")
print(f"Token: {TOKEN[:10]}...")
print(f"Key:   {AES_KEY[:10]}...")
print(f"ID:    {DEVICE_ID}")

try:
    client = GetContactClient(TOKEN, AES_KEY)
    # The client uses its own internals, we just trigger a search
    print("\nInitiating search...")
    info = client.get_full_info(PHONE)
    
    if info:
        print("\n✅ SUCCESS! Data retrieved:")
        print(f"Name: {info.get('displayName')}")
        if info.get('tags'):
            print(f"Tags: {', '.join(info.get('tags'))}")
    else:
        print("\n❌ Failed to retrieve data (Empty response or 403)")
except Exception as e:
    print(f"\n⚠️ Fatal Error: {e}")

print("\n--- TEST COMPLETE ---")
