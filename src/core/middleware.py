# src/core/middleware.py
from typing import Any
import re
from datetime import datetime
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, AIMessage

class ToolEnforcementMiddleware(AgentMiddleware):
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def _get_context_message(self) -> SystemMessage:
        now = datetime.now()
        timestamp_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
        
        content = f"""
[SYSTEM CONTEXT]
Current System Time: {timestamp_str}

[OPERATIONAL GUARDRAILS]
1. LANGUAGE: English ONLY.
2. OUTPUT: When using tools, parse the JSON output strictly.
3. PROTOCOL: Discovery (list) -> Action (control).
"""
        return SystemMessage(content=content)

    def before_model(self, request: Any) -> Any:
        if not self.strict_mode:
            return request

        context_msg = self._get_context_message()

        if isinstance(request, dict):
            messages = request.get('messages', [])
            request['messages'] = list(messages) + [context_msg]
            return request

        if hasattr(request, "messages"):
            new_msgs = list(request.messages) + [context_msg]
            return request.override(messages=new_msgs)

        return request

    def after_model(self, *args, **kwargs) -> Any:
        response = None
        if len(args) == 1:
            response = args[0]
        elif len(args) >= 2:
            response = args[1]
        
        if not response or not self.strict_mode:
            return response

        try:
            messages = []
            if isinstance(response, dict):
                messages = response.get("messages", [])
            elif hasattr(response, "messages"):
                messages = response.messages
            
            if not messages:
                return response

            last_msg = messages[-1]
            content = last_msg.content if isinstance(last_msg.content, str) else ""
            tool_calls = getattr(last_msg, "tool_calls", [])

            # --- CHECK 1: FOREIGN LANGUAGE ---
            if content:
                # (Existing logic...)
                if len(content) > 0 and non_ascii > 0:
                    print(f"[Middleware] BLOCKED FOREIGN CONTENT. (Count: {non_ascii})")
                    # Simpler error message to reset the model's brain
                    correction = AIMessage(content="ERROR: INVALID_OUTPUT_FORMAT. RETRY_IN_ENGLISH_ONLY.")
                    
                    if isinstance(response, dict):
                        response['messages'][-1] = correction
                    elif hasattr(response, "override"):
                        new_msgs = list(messages)[:-1] + [correction]
                        return response.override(messages=new_msgs)
                    return response

            # --- CHECK 2: MIME DETECTOR ---
            suspicious_phrases = ["turned on", "turned off", "switched", "activated", "is now on", "is now off", "logged", "scheduled"]
            if not tool_calls and any(phrase in content.lower() for phrase in suspicious_phrases):
                print(f"[Middleware] Detected Hallucination: '{content[:50]}...'")
                correction = AIMessage(content="[SYSTEM ERROR] You claimed to perform an action but did not generate a Tool Call. STOP roleplaying. Call the tool now.")
                
                if isinstance(response, dict):
                    response['messages'][-1] = correction
                elif hasattr(response, "override"):
                    new_msgs = list(messages)[:-1] + [correction]
                    return response.override(messages=new_msgs)

        except Exception as e:
            print(f"[Middleware Error] Could not validate response: {e}")

        return response