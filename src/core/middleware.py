from typing import Any
from datetime import datetime
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, AIMessage

class ToolEnforcementMiddleware(AgentMiddleware):
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def _get_context_message(self) -> SystemMessage:
        """
        Generates the dynamic context and guardrails.
        This ensures the Agent always knows the EXACT real-time.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%A, %B %d, %Y at %I:%M %p") # Tuesday, December 23, 2025 at 08:30 PM
        
        content = f"""
[SYSTEM CONTEXT]
Current System Time: {timestamp_str}

[OPERATIONAL GUARDRAILS]
1. You are a REMOTE INTERFACE. You have NO physical body.
2. To "turn on", "check", or "list" anything, you MUST output a Tool Call.
3. If you output text claiming you did something WITHOUT a tool call, it is a CRITICAL ERROR.
4. DO NOT explain what you are going to do. JUST CALL THE TOOL.
"""
        return SystemMessage(content=content)

    def before_model(self, request: Any) -> Any:
        """Injects guardrails into the context window."""
        if not self.strict_mode:
            return request
        
        context_msg = self._get_context_message()

        # Handle Dict-based state (LangGraph v1 standard)
        if isinstance(request, dict):
            messages = request.get('messages', [])
            # Inject Guardrail at the very end of history
            request['messages'] = list(messages) + [context_msg]
            return request

        # Handle Object-based state
        if hasattr(request, "messages"):
            new_msgs = list(request.messages) + [context_msg]
            return request.override(messages=new_msgs)

        return request

    def after_model(self, *args, **kwargs) -> Any:
        """
        Flexible handler for the after_model hook.
        Adapts to different call signatures (response-only vs request+response).
        """
        # 1. Determine what we received
        response = None
        if len(args) == 1:
            response = args[0]
        elif len(args) >= 2:
            response = args[1]
        
        if not response or not self.strict_mode:
            return response

        # 2. Extract Message
        try:
            # Normalize access to messages
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

            # 3. HEURISTIC: Did it claim action without action?
            suspicious_phrases = ["turned on", "turned off", "switched", "activated", "is now on", "is now off"]
            
            if not tool_calls and any(phrase in content.lower() for phrase in suspicious_phrases):
                print(f"[Middleware] Detected Hallucination: '{content[:50]}...'")
                correction = AIMessage(content="[SYSTEM ERROR] You claimed to perform an action but did not generate a Tool Call. STOP roleplaying. You MUST use the 'control_device' tool to actually change the state. Try again.")
                
                # 4. Apply Correction
                if isinstance(response, dict):
                    # Direct mutation for dict state
                    response['messages'][-1] = correction
                elif hasattr(response, "override"):
                    # Method for object state
                    new_msgs = list(messages)[:-1] + [correction]
                    return response.override(messages=new_msgs)
                    
        except Exception as e:
            print(f"[Middleware Error] Could not validate response: {e}")

        return response