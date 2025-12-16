# src/utils/parsing.py
import json
import re

def parse_json_markdown(json_string: str) -> dict:
    """
    Parses a JSON string that might be wrapped in Markdown code blocks.
    Example: 
      Input:  ```json\n{"next_step": "home_agent"}\n```
      Output: {"next_step": "home_agent"}
    """
    # 1. Try direct parsing first
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        pass

    # 2. Extract content between ```json and ```
    # Regex to find everything between ```json (or just ```) and the closing ```
    match = re.search(r"```(json)?(.*?)```", json_string, re.DOTALL)
    
    if match:
        json_str = match.group(2).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
    # 3. Last resort: Try to find the first '{' and last '}'
    try:
        start = json_string.find("{")
        end = json_string.rfind("}") + 1
        if start != -1 and end != 0:
            return json.loads(json_string[start:end])
    except Exception:
        pass

    # 4. Fail
    raise ValueError(f"Could not parse JSON from: {json_string}")