# %% src/capabilities/home_control/tools.py
import json
from typing import Optional, Any, Dict
from langchain_core.tools import tool
from src.core.iot import ha_client

@tool
def get_active_domains() -> str:
    """
    Returns a list of active Home Assistant domains (e.g., ['light', 'switch', 'sensor']).
    """
    try:
        states = ha_client.get_all_states()
        if not states: return "[]"
        
        domains = set()
        for s in states:
            state_val = s.get("state", "unknown")
            if state_val.lower() in ["unavailable", "unknown"]:
                continue
                
            entity_id = s.get("entity_id", "")
            if "." in entity_id:
                d = entity_id.split(".")[0]
                if d not in ["automation", "script", "update", "zone", "person", "scene"]:
                    domains.add(d)
        
        return json.dumps(list(sorted(domains)))
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def list_entities_in_domain(domain: str) -> str:
    """
    Lists all active entities within a specific domain.
    """
    try:
        states = ha_client.get_all_states()
        matches = []
        
        for s in states:
            entity_id = s.get("entity_id", "")
            if not entity_id.startswith(f"{domain}."):
                continue
                
            state_val = s.get("state", "unknown")
            if state_val.lower() in ["unavailable", "unknown"]:
                continue
            
            obj = {
                "id": entity_id,
                "name": s.get("attributes", {}).get("friendly_name", entity_id),
                "state": state_val,
                "attributes": s.get("attributes", {}) 
            }
            matches.append(obj)
            
        return json.dumps(matches, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def control_device(
    entity_id: str, 
    service: str, 
    parameters: Optional[Dict[str, Any]] = None 
) -> str:
    """
    Sends a command to a device.
    - entity_id: e.g., 'light.hallway'
    - service: e.g., 'turn_on', 'turn_off'
    - parameters: Dictionary of arguments (e.g., {"brightness_pct": 50})
    """
    try:
        # Extract domain
        if "." not in entity_id:
            return json.dumps({"error": f"Invalid entity_id format: {entity_id}"})
            
        domain = entity_id.split(".")[0]
        
        # Prepare Payload
        service_data = {"entity_id": entity_id}
        
        # Safely merge dictionary parameters
        if parameters and isinstance(parameters, dict):
            service_data.update(parameters)

        # Call Service
        result = ha_client.call_service(domain, service, service_data)
        
        if "error" in result:
             return json.dumps({"status": "error", "message": result['error']})

        # Verification
        final_state = ha_client.get_state(entity_id)
        return json.dumps({
            "status": "success", 
            "executed": f"{domain}.{service}",
            "params": service_data,
            "current_state": final_state.get("state")
        })

    except Exception as e:
        return json.dumps({"error": str(e)})