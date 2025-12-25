# src/capabilities/home_control/tools.py
import json
from typing import Optional
from langchain_core.tools import tool
from src.core.iot import ha_client

@tool
def list_available_devices(domain_filter: str = "light") -> str:
    """
    Lists devices. ALWAYS CALL THIS FIRST.
    - If multiple devices match, returns a summary list.
    - If EXACTLY ONE device matches, returns full details (attributes, brightness, etc).
    """
    states = ha_client.get_all_states()
    
    if isinstance(states, dict) and "error" in states:
        return f"SYSTEM ERROR: Could not connect to Home Assistant. {states['error']}"
    
    if not states:
        return "No devices found (Empty Response)."
    
    matches = []
    for s in states:
        entity_id = s.get("entity_id", "")
        friendly_name = s.get("attributes", {}).get("friendly_name", "Unknown")
        
        # Filter Logic: Check ID, Name, or Domain
        if (domain_filter.lower() in entity_id.lower() or 
            domain_filter.lower() in friendly_name.lower()):
            matches.append(s)
            
    if not matches:
        return f"No devices found matching '{domain_filter}'."

    # --- SMART EXPANSION LOGIC ---
    # Case A: Single Match -> Show Detail
    if len(matches) == 1:
        s = matches[0]
        attrs = s.get("attributes", {})
        
        # Format key attributes
        details = []
        if "brightness" in attrs:
            pct = int((attrs['brightness'] / 255) * 100)
            details.append(f"Brightness: {pct}%")
        if "temperature" in attrs:
            details.append(f"Temp: {attrs['temperature']}")
        if "battery_level" in attrs:
            details.append(f"Battery: {attrs['battery_level']}%")
            
        detail_str = f" | {', '.join(details)}" if details else ""
        return f"FOUND EXACT MATCH:\n- {attrs.get('friendly_name')} ({s['entity_id']}) is {s['state']}{detail_str}"

    # Case B: Multiple Matches -> Show Summary
    output = [f"Found {len(matches)} devices containing '{domain_filter}':"]
    for s in matches[:50]: # Limit to 50 to protect context window
        eid = s['entity_id']
        name = s.get("attributes", {}).get("friendly_name", "Unknown")
        state = s.get("state", "unknown")
        output.append(f"- {name} ({eid}) is {state}")
        
    return "\n".join(output)

@tool
def control_device(
    service: str, 
    entity_id: str, 
    brightness_pct: Optional[int] = None
) -> str:
    """
    Controls a device.
    - service: 'turn_on', 'turn_off', 'toggle'
    - entity_id: The exact ID found via list_available_devices.
    - brightness_pct: Optional (0-100) for dimming lights.
    """
    # Determine Domain
    # We prefer 'light.turn_on' if brightness is involved to ensure params are accepted.
    # Otherwise 'homeassistant.turn_on' is safer for generic switches.
    domain = "homeassistant"
    if entity_id.startswith("light.") and brightness_pct is not None:
        domain = "light"

    # Build Payload
    payload = {"entity_id": entity_id}
    
    if brightness_pct is not None:
        if domain != "light":
            return f"FAILURE: Cannot set brightness for non-light entity '{entity_id}'."
        payload["brightness_pct"] = brightness_pct

    # Execute
    result = ha_client.call_service(domain, service, payload)
    
    if "error" in result:
        return f"FAILURE: API Error: {result['error']}"
    
    # Verify
    final_state = ha_client.get_state(entity_id)
    state_val = final_state.get("state", "unknown")
    
    # Verification Message
    msg = f"SUCCESS: {entity_id} is now {state_val}."
    if brightness_pct:
        # Verify specific brightness level
        attrs = final_state.get("attributes", {})
        actual = attrs.get("brightness", 0)
        actual_pct = int((actual / 255) * 100)
        msg += f" (Level: {actual_pct}%)"
        
    return msg