from langchain_core.tools import tool

@tool
def check_server_temp(query: str = "") -> str:
    return "The server CPU is 45 degrees Celsius."

@tool
def check_fan_speed(query: str = "") -> str:
    return "Fan speed is 1200 RPM."