import requests
from langchain_core.tools import tool
from src.core.config import settings

def _format_size(size_bytes: int) -> str:
    """Helper to format bytes into GB/MB."""
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    return f"{size_bytes / (1024**2):.2f} MB"

@tool
def list_ollama_models() -> str:
    """
    Lists all AI models currently available on the local Ollama instance.
    Returns details like Model Name, Size, and Family (Llama, Qwen, etc.).
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        models = data.get("models", [])
        if not models:
            return "No models found on the Ollama instance."
            
        # Format for readability
        output = ["### AVAILABLE MODELS"]
        for m in models:
            name = m.get("name", "Unknown")
            size = _format_size(m.get("size", 0))
            details = m.get("details", {})
            family = details.get("family", "Unknown")
            param_size = details.get("parameter_size", "?")
            quant = details.get("quantization_level", "?")
            
            output.append(f"- **{name}**")
            output.append(f"  - Size: {size}")
            output.append(f"  - Type: {family} ({param_size} params, {quant})")
            
        return "\n".join(output)

    except Exception as e:
        return f"FAILURE: Could not connect to Ollama at {settings.OLLAMA_BASE_URL}. Error: {e}"