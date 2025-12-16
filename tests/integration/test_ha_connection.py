# tests/integration/test_ha_connection.py
import sys
import os
import requests

# --- PATH SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.core.config import settings

def test_connection():
    print("--- HOME ASSISTANT CONNECTIVITY TEST ---")
    print(f"Target URL: {settings.HOME_ASSISTANT_URL}")
    print(f"Token: {settings.HOME_ASSISTANT_TOKEN[:5]}...******")

    # 1. Test API Status
    try:
        url = f"{settings.HOME_ASSISTANT_URL}/api/"
        headers = {
            "Authorization": f"Bearer {settings.HOME_ASSISTANT_TOKEN}",
            "Content-Type": "application/json",
        }
        
        print(f"\n1. Pinging API Root ({url})...")
        response = requests.get(url, headers=headers, timeout=5)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("   [SUCCESS] API is accessible.")
            print(f"   Message: {response.json().get('message', 'No message')}")
        elif response.status_code == 401:
            print("   [FAILURE] 401 Unauthorized. Your Token is invalid.")
        else:
            print(f"   [FAILURE] Unexpected Status: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"   [CRITICAL] Connection Refused. Is the IP {settings.UNRAID_IP} correct? Is Home Assistant running?")
        return
    except Exception as e:
        print(f"   [ERROR] {e}")
        return

    # 2. Test Device List
    print(f"\n2. Fetching Device List...")
    try:
        url = f"{settings.HOME_ASSISTANT_URL}/api/states"
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   [SUCCESS] Found {len(data)} entities.")
            lights = [x['entity_id'] for x in data if x['entity_id'].startswith('light.')]
            print(f"   Found {len(lights)} lights: {lights[:3]}...")
        else:
            print(f"   [FAILURE] Could not fetch states. Status: {response.status_code}")

    except Exception as e:
        print(f"   [ERROR] {e}")

if __name__ == "__main__":
    test_connection()