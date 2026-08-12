"""Gemini LLM utility — uses the new google.genai SDK."""
from google import genai
from google.genai import types
import asyncio
import time

from core.config import settings

# Configure Gemini clients for rotation
_clients = [genai.Client(api_key=key) for key in settings.GEMINI_API_KEYS]
if not _clients:
    raise ValueError("No GEMINI_API_KEY provided in .env")

_current_key_idx = 0
_key_lock = asyncio.Lock()

# Rate limiting — separate state per model tier
_last_call: dict[str, float] = {"flash": 0.0, "flash-lite": 0.0, "pro": 0.0}
_rate_limit_locks: dict[str, asyncio.Lock] = {
    "flash": asyncio.Lock(),
    "flash-lite": asyncio.Lock(),
    "pro": asyncio.Lock(),
}

def _get_tier(model: str) -> str:
    """Map a model name to its rate-limit tier."""
    if "pro" in model:
        return "pro"
    if "flash-lite" in model:
        return "flash-lite"
    return "flash"


def _get_interval(tier: str) -> float:
    """Return the minimum interval for a tier from settings."""
    if tier == "pro":
        return settings.PRO_MIN_INTERVAL
    if tier == "flash-lite":
        return settings.FLASH_LITE_MIN_INTERVAL
    return settings.FLASH_MIN_INTERVAL


async def call_gemini_flash(prompt: str, response_schema=None) -> str:
    return await call_gemini(prompt, model=settings.GEMINI_FLASH_LITE_MODEL, response_schema=response_schema)


async def call_gemini(prompt: str, model: str = None, response_schema=None) -> str:
    if model is None:
        model = settings.GEMINI_FLASH_MODEL

    tier = _get_tier(model)
    interval = _get_interval(tier)
    
    max_retries = 6
    base_delay = 5.0
    
    global _current_key_idx
    for attempt in range(max_retries + 1):
        async with _rate_limit_locks[tier]:
            now = time.time()
            wait = interval - (now - _last_call[tier])
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call[tier] = time.time()

        try:
            kwargs = {"response_mime_type": "application/json"}
            if response_schema:
                kwargs["response_schema"] = response_schema
            config = types.GenerateContentConfig(**kwargs)
            
            # Use current client
            client = _clients[_current_key_idx]
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text
            
        except Exception as e:
            _last_call[tier] = time.time()
            err_str = str(e)
            is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            is_server_busy = "503" in err_str
            
            if (is_quota or is_server_busy) and attempt < max_retries:
                # ONLY rotate keys for Quota Limits (429), not Server Overload (503)
                if is_quota and len(_clients) > 1:
                    async with _key_lock:
                        _current_key_idx = (_current_key_idx + 1) % len(_clients)
                    print(f"Gemini API quota hit. Switching to key #{_current_key_idx + 1}/{len(_clients)} and retrying...")
                    continue # Instant retry with new key
                    
                # For 503 (or if we only have 1 key), use exponential backoff
                import re
                match = re.search(r"Please retry in ([0-9.]+)s", err_str)
                delay = float(match.group(1)) + 1.0 if match else base_delay * (2 ** attempt)
                err_type = "quota limit (429)" if is_quota else "server overload (503)"
                print(f"Gemini {model} {err_type}. Retrying in {delay:.1f}s (Attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(delay)
                continue
            
            print(f"Gemini API error ({model}): {e}")
            return "{}"
            
    return "{}"
