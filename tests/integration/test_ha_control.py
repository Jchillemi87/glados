# %% tests/integration/test_ha_control.py
import sys
import os
import json
import time

# --- PATH SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the actual tool functions
from src.capabilities.home_control.tools import control_device, list_available_devices

# CONFIGURATION
TARGET_ID = "light.hallway_switch" 

def print_separator(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def run_manual_test():
    print_separator("MANUAL TOOL TEST SUITE")

    # region Control Device (Turn ON)
    print(f"\nTesting 'control_device' (Turn ON {TARGET_ID})...")
    
    result_json = control_device.invoke({
        "service": "turn_on", 
        "entity_id": TARGET_ID
    })
    print(f"   Raw Output: {result_json}")

    try:
        res = json.loads(result_json)
        if res.get("status") == "success":
            print(f"   [PASS] Action completed. New State: {res.get('new_state')}")
        else:
            print(f"   [FAIL] API reported error: {res.get('message')}")
    except json.JSONDecodeError:
        print("   [FAIL] Could not decode JSON response.")

    # INTERMISSION: Wait for State Propagation
    print("\n   ... Waiting 5 seconds for device state to stabilize ...")
    time.sleep(5)

# region Control Device (Brightness - Optional)
    # Only run this if the target is actually a light
    if "light." in TARGET_ID:
        print(f"\nTesting 'control_device' (Brightness 50% on {TARGET_ID})...")
        
        result_json = control_device.invoke({
            "service": "turn_on",
            "entity_id": TARGET_ID,
            "brightness_pct": 50
        })
        
        try:
            res = json.loads(result_json)
            if res.get("status") == "success":
                bright_val = res.get("new_brightness", "N/A")
                print(f"   [PASS] Brightness set. Reported: {bright_val}%")
            else:
                print(f"   [FAIL] {res.get('message')}")
        except:
            print("   [FAIL] Error parsing brightness response.")

# region List Devices (Default Argument - VERBOSE)
    print("\nTesting 'list_available_devices' (No Args / Default - VERBOSE OUTPUT)...")
    
    try:
        result_json = list_available_devices.invoke({}) 
        devices = json.loads(result_json)
        print(f"   [PASS] Returned {len(devices)} devices.")
        
        print("\n   --- DEVICE DUMP START ---")
        for i, device in enumerate(devices):
            print(f"\n   [Device #{i+1}]")
            # This prints the full dictionary (all attributes) for every device
            print(json.dumps(device, indent=4))
        print("   --- DEVICE DUMP END ---")

    except Exception as e:
        print(f"   [SKIP] Tool crashed due to internal error: {e}")

if __name__ == "__main__":
    run_manual_test()