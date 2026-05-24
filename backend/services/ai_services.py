# /backend/services/ai_services.py - REPLACEMENT (Tooling Robustness, Multi-Call, and Ollama Fix)
import logging
import json
import re
from typing import Dict, Any, Optional, Union, Callable, Awaitable, List
import os # 🚨 FIX: Import os to read environment variables for Ollama model name

# --- CRITICAL FIX: Robust Dependency Imports ---
try:
    import httpx
    from httpx import HTTPStatusError # CRITICAL FIX: Import HTTPStatusError for 429 check
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None
    HTTPX_AVAILABLE = False
# Assuming other imports like gemini and groq are defined elsewhere
try:
    import google.genai as genai
    from google import genai as gemini
    from google.genai.errors import ResourceExhaustedError # CRITICAL FIX: Import Google's 429 error
    GEMINI_AVAILABLE = True
except ImportError:
    genai = gemini = ResourceExhaustedError = None
    GEMINI_AVAILABLE = False

try:
    import groq
    from groq.lib.api_client import APIError # CRITICAL FIX: Import Groq's general API error
    GROQ_AVAILABLE = True
except ImportError:
    groq = APIError = None
    GROQ_AVAILABLE = False


import asyncio
import time # CRITICAL FIX: Import time for sleep in retry logic
from config.settings import settings

logger = logging.getLogger(__name__)

class AIServiceError(Exception):
    """Custom exception for AI service failures."""
    pass

class AIService:
    """Unified AI service with resilient fallback logic."""
    MAX_RETRIES = 3 # CRITICAL FIX: Define retry constant
    BASE_DELAY = 1 # CRITICAL FIX: Define base delay for exponential backoff

    def __init__(self):
        self.providers = {}
        self.http_client = httpx.AsyncClient(timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS) if HTTPX_AVAILABLE else None
        self.default_model = getattr(settings, 'LLM_MODEL_NAME', 'gemini-2.5-flash')
        self._initialize_providers()

        logger.info(f"AI Service Initialized. Active Providers: {', '.join(self.providers.keys())}")

    def _get_secret_value(self, secret_attr: Any) -> str:
        """Helper to safely retrieve the secret string from a Pydantic SecretStr object."""
        return secret_attr.get_secret_value() if hasattr(secret_attr, 'get_secret_value') else str(secret_attr)

    def _initialize_providers(self):
        
        # 1. Gemini (Primary Cloud)
        if GEMINI_AVAILABLE:
            gemini_api_key = self._get_secret_value(settings.GEMINI_API_KEY)
            gemini_model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-2.5-flash')

            if gemini_api_key and gemini_api_key != "":
                try:
                    gemini.configure(api_key=gemini_api_key)
                    self.providers['gemini'] = {
                        'client': gemini.GenerativeModel(gemini_model_name),
                        'name': 'Gemini',
                        'priority': 1,
                        'model': gemini_model_name
                    }
                except Exception as e:
                    logger.error(f"Gemini configuration failed: {e}. Running without primary cloud provider.")
        
        # 2. Groq (High Speed - Requires Groq SDK)
        groq_api_key = self._get_secret_value(settings.GROQ_API_KEY)
        # Using the model defined in settings.py (llama-3.1-8b-instant)
        groq_model = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant') 

        if groq_api_key and groq_api_key != "":
            if GROQ_AVAILABLE:
                try:
                    self.providers['groq'] = {
                        'client': groq.Groq(api_key=groq_api_key), 
                        'name': 'Groq (SDK)',
                        'model': groq_model, 
                        'priority': 2
                    }
                except Exception as e:
                    logger.error(f"Groq native client configuration failed: {e}")
            else:
                # Groq HTTP fallback is less reliable for tool calls, prioritize native client or skip.
                logger.warning("Groq API key configured but SDK not available. Tooling disabled for Groq.")

        # 3. Ollama (Local/Fallback - Requires HTTPX)
        if HTTPX_AVAILABLE and settings.OLLAMA_BASE_URL:
            # 🚨 FIX 2: Check for specific LLM_OLLAMA_MODEL_NAME (set in docker-compose) or fallback to system default (Gemini)
            ollama_model = os.environ.get('LLM_OLLAMA_MODEL_NAME') or self.default_model 
            self.providers['ollama'] = {
                'url': settings.OLLAMA_BASE_URL,
                'name': 'Ollama',
                'priority': 3,
                'model': ollama_model
            }
        
        if not self.providers:
            logger.critical("No AI providers were successfully configured. AI services are disabled.")

    
    async def _with_retry(self, func: Callable[..., Awaitable[Union[str, Dict[str, Any]]]], *args, **kwargs) -> Union[str, Dict[str, Any]]:
        """Implements exponential backoff and retry for rate limiting and transient errors."""
        last_error = AIServiceError("Unknown AI service failure.")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except (ResourceExhaustedError, APIError, HTTPStatusError) as e:
                
                # Check for specific 429 status code for httpx and groq
                is_rate_limit_error = False
                if isinstance(e, ResourceExhaustedError): # Google error type
                    is_rate_limit_error = True
                elif isinstance(e, APIError) and getattr(e, 'status_code', 0) == 429: # Groq/OpenAI error type
                    is_rate_limit_error = True
                elif isinstance(e, HTTPStatusError) and e.response.status_code == 429: # Ollama/HTTPX error type
                    is_rate_limit_error = True

                if not is_rate_limit_error:
                    # Reraise non-rate limit errors immediately
                    raise AIServiceError(f"Non-transient API error: {type(e).__name__}: {str(e)}") from e
                
                # Handle rate limit (429) error
                last_error = AIServiceError(f"Rate limit exceeded (429) or temporary API failure on attempt {attempt + 1}. Error: {e}")
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt) + (random.random() * 0.5) # Exponential backoff with jitter
                    logger.warning(f"{func.__name__} rate limited. Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                # Catch general exceptions (network, etc.)
                last_error = AIServiceError(f"General AI service failure on attempt {attempt + 1}. Error: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BASE_DELAY) # Use base delay for general errors
                
        logger.error(f"AI service failed after {self.MAX_RETRIES} attempts.")
        raise last_error # Raise the final error after all retries fail


    async def _call_groq(self, prompt: str, system_instruction: str = "", tools: Optional[List[Dict[str, Any]]] = None) -> Union[str, Dict[str, Any]]:
        provider = self.providers.get('groq')
        if not provider or not GROQ_AVAILABLE:
            raise AIServiceError("Groq SDK service not configured.")

        messages = [{"role": "user", "content": prompt}]
        if system_instruction:
             messages.insert(0, {"role": "system", "content": system_instruction})

        client_args = {
            "messages": messages,
            # 🚨 FIX 3: Update the hardcoded fallback model name here as well
            "model": provider.get('model', 'llama-3.1-8b-instant'),
            "temperature": 0.1,
            "max_tokens": 4000,
            "tool_choice": "auto"
        }
        
        # CRITICAL FIX: Convert internal tool list (schema only) to Groq's required format
        if tools:
            # Groq's Python SDK tool definition: list of dicts, each with a 'function' key
            # Example: [{"type": "function", "function": {"name": "func_name", "description": "..."}}]
            client_args['tools'] = [{"type": "function", "function": t} for t in tools]
        
        # CRITICAL FIX: Use asyncio.to_thread and handle errors outside the retry logic
        response = await asyncio.to_thread(
            provider['client'].chat.completions.create,
            **client_args
        )
        
        # ✨ MULTI-CALL FIX: Check for and process ALL tool calls
        if response.choices[0].message.tool_calls:
            tool_calls = []
            for tc in response.choices[0].message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name, 
                    "args": json.loads(tc.function.arguments)
                })
            # Return the list of all tool calls
            return {"tool_calls": tool_calls} # Note the plural 'tool_calls'

        return response.choices[0].message.content.strip()


    async def _call_gemini(self, prompt: str, system_instruction: str = "", tools: Optional[List[Dict[str, Any]]] = None) -> Union[str, Dict[str, Any]]:
        provider = self.providers.get('gemini')
        if not provider or not GEMINI_AVAILABLE:
            raise AIServiceError("Gemini service not configured.")

        config_args = {}
        if system_instruction and genai:
             config_args['system_instruction'] = system_instruction
        
        # CRITICAL FIX: Convert internal tool list (schema only) to Gemini's required format
        if tools and genai:
             # Gemini uses the tools list directly in the config
             config_args['tools'] = tools

        config = genai.types.GenerateContentConfig(**config_args) if config_args else None
        
        # CRITICAL FIX: Call the client directly and handle errors outside the retry logic
        res = await provider['client'].generate_content_async(
            contents=prompt, 
            config=config
        )

        # ✨ MULTI-CALL FIX: Check for and process ALL tool calls
        if res.function_calls:
            tool_calls = []
            for tc in res.function_calls:
                # CRITICAL FIX: Convert tool args from attribute dictionary to standard dict
                tool_calls.append({
                    "name": tc.name, 
                    "args": dict(tc.args)
                })
            # Return the list of all tool calls
            return {"tool_calls": tool_calls} # Note the plural 'tool_calls'
        
        if not res.text:
            if res.candidates and res.candidates[0].safety_ratings:
                raise AIServiceError("Gemini returned an empty response due to safety settings.")
            raise AIServiceError("Gemini returned an empty response.")
        
        return res.text

    async def _call_ollama(self, prompt: str, system_instruction: str = "", tools: Optional[List[Dict[str, Any]]] = None) -> str:
        provider = self.providers.get('ollama')
        if not provider or httpx is None:
            raise AIServiceError("Ollama service not configured or HTTPX missing.")

        # Ollama typically uses an OpenAI-compatible endpoint for chat (more reliable for system prompts)
        messages = [{"role": "user", "content": prompt}]
        if system_instruction:
            messages.insert(0, {"role": "system", "content": system_instruction})
        
        # CRITICAL FIX 4: Use the OpenAI-compatible endpoint for better robustness.
        res = await self.http_client.post(
            f"{provider['url']}/v1/chat/completions", # Changed endpoint
            json={
                "model": provider['model'], 
                "messages": messages, # Changed to use messages list
                "stream": False,
                "temperature": 0.1
            },
            timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS
        )
        res.raise_for_status()
        data = res.json()
        # Extract content from the response structure
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


    async def generate_text(self, prompt: str, system_instruction: str = "", task_type: str = "general") -> str:
        # NOTE: Tool use is only supported via generate_tool_call_or_text
        caller: Optional[Callable[[str, str], Awaitable[Union[str, Dict[str, Any]]]]] = None
        provider_name = "None"
        
        # Determine preferred caller chain (Prioritizes Groq for Coding Tasks)
        is_coding_task = task_type in ("configuration_generation", "bpcl_generation", "correction")
        
        # 1. Primary Choice: Groq (for specialized coding/analysis tasks)
        if is_coding_task and 'groq' in self.providers:
            caller = self._call_groq
            provider_name = "Groq"
        # 2. General/Default Choice: Gemini
        elif 'gemini' in self.providers:
            caller = self._call_gemini
            provider_name = "Gemini"
        # 3. Last Default Choice: Ollama
        elif 'ollama' in self.providers:
            caller = self._call_ollama
            provider_name = "Ollama"
        else:
            raise AIServiceError("No active AI provider is configured for this task.")

        # Execution with Cascading Fallback (Groq -> Gemini -> Ollama for coding)
        
        # Attempt 1 (Primary Caller)
        try:
            # CRITICAL FIX: Wrap call in retry logic
            result = await self._with_retry(caller, prompt, system_instruction, tools=None) 
            if isinstance(result, str):
                 return result
            # If tool call is returned, convert to error string since text was expected
            if isinstance(result, dict) and 'tool_calls' in result:
                 raise AIServiceError(f"Unexpected tool call returned by {provider_name}.")
            
            return result
            
        except AIServiceError as e:
            logger.warning(f"Provider {provider_name} failed for {task_type}: {e}")
            
            # CASCADING FALLBACK FIX: Explicitly try Gemini if the primary failure was Groq
            if provider_name == "Groq" and 'gemini' in self.providers:
                 logger.warning("Groq failed. Retrying with Gemini (Cloud Backup).")
                 try:
                     # CRITICAL FIX: Wrap call in retry logic
                     result = await self._with_retry(self._call_gemini, prompt, system_instruction, tools=None) 
                     if isinstance(result, str):
                          return result
                     raise AIServiceError("Unexpected response from Gemini fallback.")
                 except AIServiceError as e_gemini:
                      logger.warning(f"Gemini fallback also failed: {e_gemini}")
            
            # Final Fallback to Ollama if the current attempt (Groq or Gemini) failed and Ollama is available
            if 'ollama' in self.providers:
                logger.warning("Retrying via Ollama (Local/Final Backup).")
                # CRITICAL FIX: Wrap call in retry logic
                result = await self._with_retry(self._call_ollama, prompt, system_instruction, tools=None)
                if isinstance(result, str):
                    return result
                raise AIServiceError(f"Unexpected response from Ollama final fallback.")
            else:
                # If all fallbacks are exhausted, raise the original error
                raise

    async def generate_json_response(self, prompt: str, response_schema: dict, task_type: str = "general") -> dict:
        # CRITICAL FIX 1: Inject schema requirement into prompt for LLM guidance
        p = f"{prompt}\nOutput valid JSON ONLY strictly matching the following schema: {json.dumps(response_schema)}"

        # CRITICAL FIX 2: Define and pass the JSON generation instruction as system_instruction
        json_system_instruction = "You are a highly efficient JSON generating model. You must strictly adhere to the provided schema and output only the valid JSON object, nothing else (no markdown fences, no conversational text)."
        
        try:
            text = await self.generate_text(p, system_instruction=json_system_instruction, task_type=task_type)
        except AIServiceError:
            return {}

        try:
            clean = text.strip()

            # Robust JSON extraction logic (handles markdown fences, non-JSON text)
            if clean.startswith('```'):
                match = re.search(r'```(?:json)?\s*(.*?)\s*```', clean, re.DOTALL)
                if match:
                    clean = match.group(1).strip()

            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                return json.loads(match.group(0))

            return json.loads(clean)

        except Exception as e:
            logger.error(f"AI JSON Parsing Failed: {e}. Raw Text: {text[:200]}...")
            return {}
            
    async def generate_tool_call_or_text(self, prompt: str, tool_schema: Dict[str, Any], task_type: str = "general") -> Dict[str, Any]:
        """
        [CRITICAL NEW METHOD] Generates either one or more tool calls (function name + args) or a final text response.
        
        Returns: {"tool_calls": List[{"name": str, "args": dict}]} OR {"text_response": str}
        """
        
        # CRITICAL FIX 1: Extract the list of tool definitions/schemas
        tools = tool_schema.get("tools", [])
        
        if not tools:
             # Fallback to pure text generation if no tools are exposed
             text = await self.generate_text(prompt, system_instruction="You are a helpful assistant.", task_type=task_type)
             return {"text_response": text}

        # ✨ PRIORITY FIX 1: Gemini (Standard Tooling - Highest Reliability Priority)
        if 'gemini' in self.providers and GEMINI_AVAILABLE and tools:
            try:
                # CRITICAL FIX: Wrap call in retry logic
                response = await self._with_retry(self._call_gemini, prompt, system_instruction="You are a tool-using orchestrator agent. Use tools to execute tasks.", tools=tools)
                if isinstance(response, dict) and "tool_calls" in response:
                    return response
                return {"text_response": response} 
            except AIServiceError as e:
                 logger.warning(f"Gemini tool call failed: {e}. Falling back to Groq.")

        # ✨ PRIORITY FIX 2: Groq (High Speed - Secondary Priority)
        if 'groq' in self.providers and GROQ_AVAILABLE and tools:
            try:
                # CRITICAL FIX: Wrap call in retry logic
                response = await self._with_retry(self._call_groq, prompt, system_instruction="You are a tool-using orchestrator agent. Use tools to execute tasks.", tools=tools)
                if isinstance(response, dict) and "tool_calls" in response:
                    return response
                return {"text_response": response} 
            except AIServiceError as e:
                 logger.warning(f"Groq tool call failed: {e}. Falling back to text only.")
                 
        # 3. Final Fallback to text (No tool use)
        try:
            # NOTE: Use generate_text which handles its own internal fallbacks (e.g., to Ollama)
            text = await self.generate_text(prompt, system_instruction="You are a helpful assistant.", task_type=task_type)
            return {"text_response": text}
        except AIServiceError:
             return {"text_response": "ERROR: All AI services failed to respond or use tools."}