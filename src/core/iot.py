# src/core/iot.py
import requests
from typing import Dict, Any, List, Union
from src.core.config import settings

class HomeAssistantClient:
    def __init__(self):
        self.base_url = settings.HOME_ASSISTANT_URL
        self.headers = {
            "Authorization": f"Bearer {settings.HOME_ASSISTANT_TOKEN}",
            "Content-Type": "application/json",
        }

    def get_all_states(self) -> Union[List[Dict], Dict]:
        """Fetch ALL states. Returns list of states OR error dict."""
        url = f"{self.base_url}/api/states"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP Error {e.response.status_code}: {e.response.reason}"}
        except requests.exceptions.ConnectionError:
             return {"error": f"Connection Refused to {self.base_url}. Check IP."}
        except Exception as e:
            return {"error": str(e)}

    def get_state(self, entity_id: str) -> Dict[str, Any]:
        """Fetch the state of a specific entity."""
        url = f"{self.base_url}/api/states/{entity_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            return {"error": f"Entity {entity_id} not found."}
        except Exception as e:
            return {"error": str(e)}

    def call_service(self, domain: str, service: str, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a service (e.g., light.turn_on)."""
        url = f"{self.base_url}/api/services/{domain}/{service}"
        try:
            response = requests.post(url, headers=self.headers, json=service_data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_all_states(self) -> list:
        """Fetch ALL states. Expensive call, use sparingly."""
        url = f"{self.base_url}/api/states"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return []

# Singleton instance
ha_client = HomeAssistantClient()