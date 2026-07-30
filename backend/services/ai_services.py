# /backend/services/ai_services.py — Local-only LLM service (Ollama + qwen2.5)
#
# HiRo runs entirely on a local Ollama instance. No cloud providers, no API keys.
# All calls go through Ollama's OpenAI-compatible endpoint (/v1/chat/completions),
# which gives a single code path for plain text, JSON, and native tool-calling
# (qwen2.5 supports function calling).
import logging
import json
import re
import os
import asyncio
import random
from typing import Dict, Any, Optional, Union, List

try:
    import httpx
    from httpx import HTTPStatusError
    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover - httpx is a hard dependency in practice
    httpx = None
    HTTPStatusError = Exception
    HTTPX_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Custom exception for AI service failures."""
    pass


class AIService:
    """Unified AI service backed by a local Ollama server (qwen2.5 by default)."""
    MAX_RETRIES = 3
    BASE_DELAY = 1

    def __init__(self):
        # Model precedence: explicit Ollama env override -> configured default.
        self.model = (
            os.environ.get("LLM_OLLAMA_MODEL_NAME")
            or os.environ.get("OLLAMA_MODEL")
            or getattr(settings, "LLM_MODEL_NAME", "qwen2.5:7b")
        )
        self.base_url = getattr(settings, "OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        self.http_client = (
            httpx.AsyncClient(timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS)
            if HTTPX_AVAILABLE else None
        )
        if not HTTPX_AVAILABLE:
            logger.critical("httpx is not installed — AI services are disabled.")
        else:
            logger.info(f"AIService using Ollama model '{self.model}' at {self.base_url}")

    @property
    def providers(self) -> Dict[str, Any]:
        """Back-compat shim: some callers introspect `.providers` to check availability."""
        return {"ollama": {"model": self.model, "url": self.base_url}} if HTTPX_AVAILABLE else {}

    async def _with_retry(self, func, *args, **kwargs):
        """Exponential backoff on rate-limit / transient errors."""
        last_error = AIServiceError("Unknown AI service failure.")
        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except HTTPStatusError as e:
                status = getattr(getattr(e, "response", None), "status_code", 0)
                if status not in (429, 500, 502, 503, 504):
                    raise AIServiceError(f"Non-transient Ollama error {status}: {e}") from e
                last_error = AIServiceError(f"Transient Ollama error {status} (attempt {attempt + 1}).")
            except Exception as e:
                last_error = AIServiceError(f"AI service failure on attempt {attempt + 1}: {e}")
            if attempt < self.MAX_RETRIES - 1:
                delay = self.BASE_DELAY * (2 ** attempt) + random.random() * 0.5
                logger.warning(f"{getattr(func, '__name__', 'call')} failed; retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
        logger.error(f"AI service failed after {self.MAX_RETRIES} attempts.")
        raise last_error

    async def _call_ollama(
        self,
        prompt: str,
        system_instruction: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[str, Dict[str, Any]]:
        """One call to Ollama's OpenAI-compatible chat endpoint.

        Returns a plain string, or {"tool_calls": [{"name", "args"}, ...]} when the
        model requests tools.
        """
        if not HTTPX_AVAILABLE or self.http_client is None:
            raise AIServiceError("Ollama service not configured (httpx missing).")

        messages = [{"role": "user", "content": prompt}]
        if system_instruction:
            messages.insert(0, {"role": "system", "content": system_instruction})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.1,
        }
        if tools:
            # OpenAI tool format: [{"type": "function", "function": {schema}}]
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"

        res = await self.http_client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS,
        )
        res.raise_for_status()
        message = res.json().get("choices", [{}])[0].get("message", {})

        if message.get("tool_calls"):
            calls = []
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                calls.append({"name": fn.get("name"), "args": args})
            return {"tool_calls": calls}

        return (message.get("content") or "").strip()

    async def get_ai_models(self) -> List[Dict[str, str]]:
        """Real list of available local Ollama models ([{name, label}]) for the
        provider/model pickers. Falls back to the configured model if Ollama is
        unreachable, so the UI never breaks."""
        def _label(name: str) -> str:
            base = name.split(":")[0].replace("-", " ").replace("_", " ")
            return f"{base.title()} ({name.split(':')[1]})" if ":" in name else base.title()

        if HTTPX_AVAILABLE and self.http_client is not None:
            try:
                res = await self.http_client.get(f"{self.base_url}/api/tags", timeout=5.0)
                res.raise_for_status()
                models = res.json().get("models", [])
                out = [{"name": m["name"], "label": _label(m["name"])}
                       for m in models if m.get("name")]
                if out:
                    return out
            except Exception as e:
                logger.warning(f"Could not list Ollama models ({e}); using configured default.")
        return [{"name": self.model, "label": _label(self.model)}]

    async def generate_text(self, prompt: str, system_instruction: str = "", task_type: str = "general") -> str:
        result = await self._with_retry(self._call_ollama, prompt, system_instruction, tools=None)
        if isinstance(result, dict) and "tool_calls" in result:
            raise AIServiceError("Unexpected tool call returned during text generation.")
        return result if isinstance(result, str) else str(result)

    async def generate_json_response(self, prompt: str, response_schema: dict, task_type: str = "general") -> dict:
        p = f"{prompt}\nOutput valid JSON ONLY strictly matching this schema: {json.dumps(response_schema)}"
        json_system_instruction = (
            "You are a highly efficient JSON generating model. Output only the valid JSON object "
            "matching the schema — no markdown fences, no conversational text."
        )
        # ponytail: prompt-enforced JSON + regex extraction, not Ollama's format=json
        # (format=json is unreliable across Ollama versions).
        try:
            text = await self.generate_text(p, system_instruction=json_system_instruction, task_type=task_type)
        except AIServiceError:
            return {}

        try:
            clean = text.strip()
            if clean.startswith("```"):
                fence = re.search(r"```(?:json)?\s*(.*?)\s*```", clean, re.DOTALL)
                if fence:
                    clean = fence.group(1).strip()
            obj = re.search(r"\{.*\}", clean, re.DOTALL)
            return json.loads(obj.group(0) if obj else clean)
        except Exception as e:
            logger.error(f"AI JSON parsing failed: {e}. Raw: {text[:200]}...")
            return {}

    async def generate_tool_call_or_text(self, prompt: str, tool_schema: Dict[str, Any], task_type: str = "general") -> Dict[str, Any]:
        """Returns {"tool_calls": [{"name", "args"}]} or {"text_response": str}."""
        tools = tool_schema.get("tools", [])
        if not tools:
            text = await self.generate_text(prompt, system_instruction="You are a helpful assistant.", task_type=task_type)
            return {"text_response": text}

        try:
            response = await self._with_retry(
                self._call_ollama,
                prompt,
                system_instruction="You are a tool-using orchestrator agent. Use tools to execute tasks.",
                tools=tools,
            )
            if isinstance(response, dict) and "tool_calls" in response:
                return response
            return {"text_response": response}
        except AIServiceError as e:
            logger.warning(f"Ollama tool call failed: {e}. Falling back to plain text.")

        try:
            text = await self.generate_text(prompt, system_instruction="You are a helpful assistant.", task_type=task_type)
            return {"text_response": text}
        except AIServiceError:
            return {"text_response": ""}
