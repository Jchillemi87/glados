from langchain_core.tools import tool
from src.core.iot import ha_client

@tool
def list_available_devices(domain_filter: str = "light") -> str:
    """
    Lists devices in the house. 
    ALWAYS CALL THIS FIRST.
    """
    states = ha_client.get_all_states()
    
    if isinstance(states, dict) and "error" in states:
        return f"SYSTEM ERROR: Could not connect to Home Assistant. {states['error']}"
    
    if not states:
        return "No devices found (Empty Response)."
    
    found_devices = []
    for s in states:
        entity_id = s.get("entity_id", "")
        # Broaden search to include generic 'homeassistant' or matched names
        if domain_filter in entity_id or domain_filter in s.get("attributes", {}).get("friendly_name", "").lower():
            friendly_name = s.get("attributes", {}).get("friendly_name", "Unknown")
            state = s.get("state", "unknown")
            found_devices.append(f"- {friendly_name} (ID: {entity_id}) | State: {state}")
    
    if not found_devices:
        return f"No devices found matching '{domain_filter}'."
        
    return "\n".join(found_devices[:50])

@tool
def get_device_state(entity_id: str) -> str:
    """Checks device status."""
    data = ha_client.get_state(entity_id)
    if "error" in data:
        return f"Error: {data['error']}"
    
    name = data.get("attributes", {}).get("friendly_name", entity_id)
    state = data.get("state", "unknown")
    return f"{name} ({entity_id}) is currently {state}."

@tool
def control_device(service: str, entity_id: str) -> str:
    """
    Controls a device.
    - service: 'turn_on', 'turn_off', 'toggle'
    - entity_id: The exact ID found via list_available_devices.
    """
    # 1. Force Generic Domain
    domain = "homeassistant"
    
    # 2. Execute
    result = ha_client.call_service(domain, service, {"entity_id": entity_id})
    
    if "error" in result:
        return f"FAILURE: API Error: {result['error']}"
    
    # 3. Verify
    final_state = ha_client.get_state(entity_id)
    state_val = final_state.get("state", "unknown")
    
    # 4. Strict Feedback
    if state_val == "unavailable":
        return f"FAILURE: Device '{entity_id}' is UNAVAILABLE. Check power/connection."
    
    return f"SUCCESS: Called {service} on {entity_id}. New State: {state_val}."