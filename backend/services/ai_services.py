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
            httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS)
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
            timeout=settings.LLM_TIMEOUT_SECONDS,
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

    async def generate_embedding(self, text: str) -> List[float]:
        """A real embedding vector from the local embedding model.

        The endpoint that calls this returned a 500 on every request because
        this method did not exist. It uses a dedicated embedding model: a chat
        model cannot produce one, so this fails loudly rather than returning
        something vector-shaped that means nothing.
        """
        if not text or not text.strip():
            raise AIServiceError("There is nothing to embed.")
        if not (HTTPX_AVAILABLE and self.http_client is not None):
            raise AIServiceError("No HTTP client is available to reach the embedding model.")

        model = os.environ.get("LLM_EMBEDDING_MODEL") or "nomic-embed-text"
        try:
            res = await self.http_client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=60.0,
            )
            res.raise_for_status()
            vector = res.json().get("embedding") or []
        except Exception as e:
            raise AIServiceError(
                f"The embedding model '{model}' could not be reached. "
                f"Pull it with 'ollama pull {model}' if it is not installed. ({e})") from e

        if not vector:
            raise AIServiceError(f"The embedding model '{model}' returned no vector.")
        return vector

    async def generate_text(self, prompt: str, system_instruction: str = "", task_type: str = "general") -> str:
        result = await self._with_retry(self._call_ollama, prompt, system_instruction, tools=None)
        if isinstance(result, dict) and "tool_calls" in result:
            raise AIServiceError("Unexpected tool call returned during text generation.")
        return result if isinstance(result, str) else str(result)

    @staticmethod
    def _describe_schema(schema: dict) -> str:
        """Render a JSON Schema as a short field list.

        Small local models reliably echo a raw JSON Schema back instead of
        producing an instance of it, so we hand them a plain field list plus a
        skeleton rather than the schema document itself.
        """
        defs = schema.get("$defs", {}) or {}

        def placeholder(spec):
            """A concrete example value for one property, resolving $ref objects."""
            ref = spec.get("$ref")
            if ref:
                target = defs.get(ref.split("/")[-1], {})
                return {k: placeholder(v) for k, v in (target.get("properties", {}) or {}).items()}
            typ = spec.get("type", "string")
            if typ == "array":
                return [placeholder(spec.get("items", {"type": "string"}))]
            if typ == "object":
                return {}
            return {"integer": 0, "number": 0, "boolean": True}.get(typ, "...")

        props = schema.get("properties", {}) or {}
        required = set(schema.get("required", []) or [])
        lines, skeleton = [], {}
        for name, spec in props.items():
            if name == "user_id":
                continue  # injected server-side
            typ = "object" if "$ref" in spec else spec.get("type", "string")
            desc = spec.get("description", "")
            flag = "required" if name in required else "optional"
            lines.append(f'- "{name}" ({typ}, {flag}){": " + desc if desc else ""}')
            skeleton[name] = placeholder(spec)
        return "\n".join(lines), json.dumps(skeleton)

    @staticmethod
    def _looks_like_schema(obj: dict) -> bool:
        """True when the model echoed the schema instead of an instance."""
        return isinstance(obj, dict) and bool({"properties", "$defs", "$schema"} & set(obj.keys()))

    @staticmethod
    def _coerce_to_schema(obj: dict, schema: dict) -> dict:
        """Repair shape mistakes small local models routinely make.

        An 8B model will happily return a string where a nested object is
        required (e.g. memory_config: "long_term,500MB"). Rather than failing the
        whole request, coerce each top-level field to the type the schema expects
        and let validation judge the content.
        """
        defs = schema.get("$defs", {}) or {}
        props = schema.get("properties", {}) or {}
        fixed = dict(obj)
        for name, spec in props.items():
            if name not in fixed:
                continue
            value = fixed[name]

            # Optional nested models come through as anyOf: [{$ref}, {type: null}].
            variants = spec.get("anyOf") or spec.get("oneOf")
            if variants:
                nullable = any(v.get("type") == "null" for v in variants)
                inner = next((v for v in variants if "$ref" in v), None)
                if not isinstance(value, dict):
                    if nullable:
                        fixed[name] = None          # the field is optional; drop the malformed value
                        continue
                    spec = inner or spec            # fall through to $ref repair below

            ref = spec.get("$ref")
            if ref and not isinstance(value, dict):
                target = defs.get(ref.split("/")[-1], {})
                required = target.get("required", []) or []
                # Keep the model's intent as the first required field when it is a string.
                rebuilt = {}
                for key in required:
                    key_spec = (target.get("properties", {}) or {}).get(key, {})
                    if key_spec.get("type") == "string":
                        rebuilt[key] = str(value)[:64] if isinstance(value, (str, int, float)) else "short_term"
                    else:
                        rebuilt[key] = 0
                fixed[name] = rebuilt or {}
            elif spec.get("type") == "array" and not isinstance(value, list):
                fixed[name] = [] if value in (None, "") else [value]
            elif spec.get("type") == "string" and isinstance(value, (dict, list)):
                fixed[name] = json.dumps(value)
        return fixed

    async def generate_json_response(self, prompt: str, response_schema: dict, task_type: str = "general") -> dict:
        fields, skeleton = self._describe_schema(response_schema)
        p = (
            f"{prompt}\n\n"
            f"Produce ONE JSON object with exactly these keys:\n{fields}\n\n"
            f"Shape (replace every placeholder with a real value):\n{skeleton}\n\n"
            "Return the filled-in object only. Do not return the schema or any explanation."
        )
        json_system_instruction = (
            "You output a single valid JSON object and nothing else. "
            "Never output a JSON Schema, never use markdown fences, never add commentary."
        )
        # ponytail: prompt-enforced JSON + robust extraction, not Ollama's format=json
        # (format=json is unreliable across Ollama versions).
        for attempt in range(2):
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
                parsed = json.loads(obj.group(0) if obj else clean)
            except Exception as e:
                logger.error(f"AI JSON parsing failed: {e}. Raw: {text[:200]}...")
                parsed = None

            if isinstance(parsed, dict) and not self._looks_like_schema(parsed):
                return self._coerce_to_schema(parsed, response_schema)

            if attempt == 0:
                logger.warning("Model returned a schema (or unparsable text); retrying with a stricter prompt.")
                p = (
                    f"{prompt}\n\nFill in this object with real values and return only it:\n{skeleton}\n"
                    "Do NOT include the words 'properties', 'type' or 'required'."
                )
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
