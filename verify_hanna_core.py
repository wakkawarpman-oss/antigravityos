import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_shodan():
    key = os.getenv("SHODAN_API_KEY")
    if not key: return "❌ No key"
    try:
        r = requests.get(f"https://api.shodan.io/api-info?key={key}")
        if r.status_code == 200:
            return f"✅ OK (Credits: {r.json().get('query_credits')})"
        return f"❌ Error {r.status_code}"
    except Exception as e:
        return f"⚠️ {e}"

def test_firms():
    key = os.getenv("FIRMS_MAP_KEY")
    if not key: return "❌ No key"
    return "✅ Configured"

def test_serpapi():
    key = os.getenv("SERPAPI_API_KEY")
    if not key: return "❌ No key"
    try:
        # SerpApi account check
        r = requests.get(f"https://serpapi.com/account?api_key={key}")
        if r.status_code == 200:
            return "✅ OK"
        return f"❌ Error {r.status_code}"
    except Exception as e:
        return f"⚠️ {e}"

print("--- HANNA CORE ADAPTER VERIFICATION ---")
print(f"Shodan:   {test_shodan()}")
print(f"FIRMS:    {test_firms()}")
print(f"SerpApi:  {test_serpapi()}")
print("---------------------------------------")
