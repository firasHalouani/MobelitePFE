import os
import logging
import requests
import json
try:
    import openai as _openai_pkg
    from openai import OpenAI
except Exception:
    _openai_pkg = None
    OpenAI = None

logger = logging.getLogger(__name__)


# Configure client: prefer OpenRouter if OPENROUTER_API_KEY is set, otherwise use OPENAI_API_KEY
_client = None
_client_type = None

_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Development helper: allow a fake AI mode when no real client is available
FAKE_AI = os.getenv("FAKE_AI", "false").lower() in ("1", "true", "yes")

# If an OpenRouter API key is provided, prefer calling the OpenRouter HTTP API
# directly via `requests` (no SDK required).
if _OPENROUTER_KEY:
    _client_type = "openrouter"
    logger.info("ai_helper: configured OpenRouter via HTTP (requests)")
elif OpenAI is not None:
    _openai_key = os.getenv("OPENAI_API_KEY")
    if _openai_key:
        try:
            _client = OpenAI(api_key=_openai_key)
            _client_type = "openai"
            logger.info("ai_helper: configured OpenAI SDK client")
        except Exception as e:
            logger.warning("ai_helper: failed to create OpenAI client: %s", e)


def generate_ai_recommendation(code_snippet: str) -> str:
    """Return an AI-generated recommendation for a small code snippet.

    Supports OpenRouter (preferred) and standard OpenAI SDK usage. If no client is
    configured, returns None.
    """
    # If fake AI mode is enabled, return a deterministic, local recommendation.
    if os.getenv("FAKE_AI", "false").lower() in ("1", "true", "yes"):
        return _fake_recommendation(code_snippet)

    # If we neither have an SDK client nor OpenRouter HTTP configured, skip.
    if _client is None and _client_type != "openrouter":
        logger.debug("ai_helper: no client configured, skipping AI recommendation")
        return None

    prompt = f"""You are a security expert. Analyze the following code snippet and:
1. Identify any security vulnerabilities present.
2. Explain the risk clearly and concisely.
3. Provide a concrete, secure fix or mitigation.

Code snippet:
{code_snippet}
"""

    try:
        if _client_type == "openrouter":
            # Default to a stable free-tier model; override via OPENROUTER_MODEL env var
            model = os.getenv("OPENROUTER_MODEL", "google/gemma-3-27b-it:free")
            headers = {
                "Authorization": f"Bearer {_OPENROUTER_KEY}",
                "Content-Type": "application/json",
            }
            referer = os.getenv("OPENROUTER_SITE_URL")
            title = os.getenv("OPENROUTER_SITE_NAME")
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
            url = _OPENROUTER_BASE.rstrip('/') + "/chat/completions"
            logger.debug("ai_helper: POST %s model=%s", url, model)

            # Retry with exponential backoff for rate-limit (429) errors.
            # On persistent 429, fall back to a lighter free-tier model.
            _FALLBACK_MODELS = [
                "google/gemma-3-12b-it:free",
                "google/gemma-3-4b-it:free",
            ]
            max_attempts = 3
            resp = None
            for attempt in range(max_attempts):
                current_model = model if attempt == 0 else _FALLBACK_MODELS[min(attempt - 1, len(_FALLBACK_MODELS) - 1)]
                payload["model"] = current_model
                logger.debug("ai_helper: attempt %d/%d model=%s", attempt + 1, max_attempts, current_model)
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 429:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "ai_helper: rate-limited (429) on model=%s, waiting %ds before retry",
                        current_model, wait,
                    )
                    import time
                    time.sleep(wait)
                    continue
                break  # success or non-429 error

            if not resp.ok:
                logger.error(
                    "ai_helper: OpenRouter returned HTTP %s: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                resp.raise_for_status()
            response = resp.json()
        else:
            model = os.getenv("OPENAI_MODEL", "gpt-4")
            logger.debug("ai_helper: calling OpenAI model=%s", model)
            response = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

        # Extract text from the response; different SDKs may vary slightly.
        try:
            # OpenRouter REST returns choices -> message -> content
            out = response['choices'][0]['message']['content']
        except Exception:
            # Fallback for SDK-like object responses
            try:
                out = response.choices[0].message.content
            except Exception:
                out = getattr(response, 'text', None) or getattr(response, 'content', None) or None

        if out:
            logger.debug("ai_helper: received response length=%d", len(out))
        else:
            logger.warning("ai_helper: received empty response from LLM")
        return out

    except Exception as e:
        logger.exception("ai_helper: exception during LLM call: %s", e)
        msg = str(e).lower()
        # Detect rate-limiting and optionally fall back to fake recommendations
        is_rate_limit = (
            "rate limit" in msg or "rate_limit" in msg or "ratelimit" in msg
            or (
                _openai_pkg is not None
                and getattr(_openai_pkg, 'RateLimitError', None)
                and isinstance(e, getattr(_openai_pkg, 'RateLimitError'))
            )
        )
        if is_rate_limit:
            logger.warning("ai_helper: LLM rate-limited: %s", e)
            if os.getenv("FAKE_AI", "false").lower() in ("1", "true", "yes"):
                return _fake_recommendation(code_snippet)
        return None


def is_ai_available() -> bool:
    """Return True when an AI client is configured and USE_AI is enabled."""
    # If fake AI explicitly enabled, report available even without a client.
    if os.getenv("FAKE_AI", "false").lower() in ("1", "true", "yes"):
        return True
    # If OpenRouter HTTP mode is configured, consider AI available.
    if _client_type == "openrouter":
        use_ai = os.getenv("USE_AI", "true").lower()
        return use_ai in ("1", "true", "yes")
    if _client is None:
        return False
    use_ai = os.getenv("USE_AI", "true").lower()
    return use_ai in ("1", "true", "yes")


def _fake_recommendation(code_snippet: str) -> str:
    """Return a simple deterministic recommendation for development/testing.

    This helps test UI and persistence without calling an LLM.
    """
    s = code_snippet.lower()
    if "eval" + "(" in s:
        return (
            "Avoid using eval" + "(). If you need to evaluate expressions, prefer parsing "
            "and using safe evaluators like ast.literal_eval or restrict to a whitelist."
        )
    if "exec" + "(" in s:
        return (
            "Avoid exec" + "() on untrusted input. Refactor to functions or use safer "
            "abstractions; validate and sanitize any dynamic code before execution."
        )
    if "input" + "(" in s:
        return (
            "Validate and sanitize input" + "() results before use. Consider using "
            "strict parsing and limiting characters/length."
        )
    if "os.system(" in s:
        return (
            "Avoid os.system() with user-controlled input. Use subprocess with a list "
            "of arguments and avoid shell=True to prevent command injection."
        )
    if "pickle.loads(" in s:
        return (
            "Never unpickle data from untrusted sources. Use safer serialization "
            "formats like JSON or MessagePack instead."
        )
    if "subprocess.popen(" in s:
        return (
            "Use subprocess.run() with a list of arguments instead of a shell string. "
            "Avoid shell=True and validate all inputs to prevent command injection."
        )
    return "No obvious security issue detected; follow secure coding practices and validate all inputs."
