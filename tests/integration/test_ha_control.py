# tests/integration/test_ha_control.py
import sys
import os

# --- PATH SETUP ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the actual tool function
from src.capabilities.home_control.tools import control_device, get_device_state

# CONFIGURATION
# We use the ID found in your previous logs ("1. Hallway Bulb (ID: light.hallway_bulb)")
TARGET_ID = "light.hallway_switch" 

def run_manual_test():
    print(f"--- MANUAL TOOL TEST: {TARGET_ID} ---")

    # 1. Check Initial State
    print("\n1. Checking Initial State...")
    initial_state = get_device_state.invoke(TARGET_ID)
    print(f"   Result: {initial_state}")

    # 2. Send Command (Turn ON)
    print("\n2. Sending 'turn_on' Command...")
    # Note: We pass arguments exactly how the Agent would
    result = control_device.invoke({
        "domain": "light", 
        "service": "turn_on", 
        "entity_id": TARGET_ID
    })
    print(f"   Result: {result}")

    # 3. Verification
    if "is now on" in result or "turned on" in result:
        print("\n[PASS] The tool claims success.")
    elif "Failed" in result:
        print("\n[FAIL] The tool reported an API error.")
    else:
        print(f"\n[?] Ambiguous result: {result}")

if __name__ == "__main__":
    run_manual_test()