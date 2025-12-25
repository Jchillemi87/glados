# src/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    # NETWORK & PORTS
    # defaults are set but are overridden by .env
    UNRAID_IP: str = "10.0.0.201"
    HOME_ASSISTANT_IP: str = "10.0.0.35"
    
    PORT_OLLAMA: int = 11434
    PORT_QDRANT: int = 6333
    PORT_PAPERLESS: int = 8000
    PORT_HOME_ASSISTANT: int = 8123
    PORT_PIPER: int = 10200

    # AUTHENTICATION
    PAPERLESS_API_TOKEN: str = "disabled" # Default to avoid crash if missing during dev
    HOME_ASSISTANT_TOKEN: str = "disabled" # Default to avoid crash if missing during dev

    # MODELS
    # qwen2.5:14b - recommended starting point, llama3.1:8b for logic, llama3.2:latest for speed
    DEFAULT_MODEL: str = "qwen2.5:14b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # PERSISTENCE
    STATE_DB_PATH: str = "agent_state.sqlite"

    # VOICE SETTINGS
    # Common GLaDOS file names: "glados", "en_US-glados-medium"
    PIPER_VOICE_ID: str = "glados"

    # COMPUTED URLS - automatically generated based on the IP/Port above.
    
    @computed_field
    def OLLAMA_BASE_URL(self) -> str:
        return f"http://{self.UNRAID_IP}:{self.PORT_OLLAMA}"

    @computed_field
    def QDRANT_URL(self) -> str:
        return f"http://{self.UNRAID_IP}:{self.PORT_QDRANT}"

    @computed_field
    def PAPERLESS_URL(self) -> str:
        return f"http://{self.UNRAID_IP}:{self.PORT_PAPERLESS}"
    
    @computed_field
    def HOME_ASSISTANT_URL(self) -> str:
        return f"http://{self.HOME_ASSISTANT_IP}:{self.PORT_HOME_ASSISTANT}"

    @computed_field
    def PIPER_URL(self) -> str:
        return f"http://{self.UNRAID_IP}:{self.PORT_PIPER}"

    # CONFIGURATION
    # Tells Pydantic to read from the .env file in the root directory
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra keys in .env
    )

# Instantiate the singleton
# When you import this, it immediately validates your .env file.
try:
    settings = Settings()
except Exception as e:
    print(f"CRITICAL CONFIG ERROR: Missing or invalid .env file.\n{e}")
    raise e