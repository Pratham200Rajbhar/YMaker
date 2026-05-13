"""
AI service — generates scripts and scenes using either Ollama or Vertex AI Gemini.

Key design decisions:
- Ollama uses /api/chat (instruction-following) not /api/generate (raw completion).
- JSON schema is passed via Ollama's `format` key — NOT duplicated in the prompt.
- Retries up to 3 times with an error-correction follow-up on malformed JSON.
- CTA is intentionally excluded: this tool produces video scripts, not marketing copy.
"""

import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select


from ..database import SessionLocal
from ..models import Settings

logger = logging.getLogger(__name__)


class AiServiceError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# JSON Schemas — define expected structure for structured outputs
# ---------------------------------------------------------------------------

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "video_script": {
            "type": "string",
            "description": "The full spoken script for the video, including the opening hook and the main body content.",
        },
        "on_screen_notes": {
            "type": "string",
            "description": "Director notes for on-screen text, B-roll hints, or visual cues.",
        },
        "title_suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exactly 5 YouTube title options optimized for clicks.",
        },
        "description": {
            "type": "string",
            "description": (
                "SEO-optimized YouTube video description. The first two lines are keyword-dense "
                "and under 125 characters combined, followed by bullet points summarizing the video, "
                "followed by relevant hashtags."
            ),
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "15 to 20 YouTube search tags mixing broad and specific terms with no hash symbols.",
        },
        "chapters": {
            "type": "array",
            "items": {"type": "string"},
            "description": 'Timestamped chapter strings in the format "00:00 Chapter Name"; empty for shorts.',
        },
        "hook_type": {
            "type": "string",
            "enum": ["shock", "question", "story", "listicle", "counter-intuitive", "challenge"],
            "description": "Classification of the opening hook style.",
        },
        "estimated_duration": {
            "type": "string",
            "description": "Estimated spoken duration, e.g. '55 seconds' or '9 minutes'.",
        },
        "tone": {
            "type": "string",
            "description": "The tone/style of the script, e.g. 'energetic', 'educational', 'conversational'.",
        },
    },
    "required": [
        "video_script",
        "on_screen_notes",
        "title_suggestions",
        "description",
        "tags",
        "chapters",
        "hook_type",
        "estimated_duration",
        "tone",
    ],
}

SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer"},
                    "description": {"type": "string"},
                    "visual_keyword": {
                        "type": "string",
                        "description": "Concrete, searchable stock video keyword. Never abstract.",
                    },
                    "voiceover_text": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                },
                "required": ["scene_index", "description", "visual_keyword", "voiceover_text", "duration_seconds"],
            },
        }
    },
    "required": ["scenes"],
}

IDEA_OPTIMIZER_SCHEMA = {
    "type": "object",
    "properties": {
        "optimized_idea": {
            "type": "string",
            "description": "A more detailed, descriptive version of the original idea.",
        },
    },
    "required": ["optimized_idea"],
}

KEYWORD_OPTIMIZER_SCHEMA = {
    "type": "object",
    "properties": {
        "optimized_keyword": {
            "type": "string",
            "description": "A concrete, searchable stock video keyword phrase.",
        },
    },
    "required": ["optimized_keyword"],
}

CLIP_SCORER_SCHEMA = {
    "type": "object",
    "properties": {
        "scored_clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clip_id": {"type": "string"},
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reason": {"type": "string"},
                },
                "required": ["clip_id", "score", "reason"],
            },
        }
    },
    "required": ["scored_clips"],
}


def _schema_to_example(schema: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal example dict from a JSON schema so weak models don't parrot schema keywords."""
    example: dict[str, Any] = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        prop = properties.get(key, {})
        ptype = prop.get("type")
        if ptype == "string":
            desc = prop.get("description", "")
            example[key] = f"<string value for {key}: {desc}>"
        elif ptype == "array":
            item_type = prop.get("items", {}).get("type")
            if item_type == "object":
                item_props = prop.get("items", {}).get("properties", {})
                item_required = prop.get("items", {}).get("required", [])
                item_example: dict[str, Any] = {}
                for ik in item_required:
                    ip = item_props.get(ik, {})
                    it = ip.get("type")
                    if it == "string":
                        item_example[ik] = f"<value for {ik}>"
                    elif it == "number":
                        item_example[ik] = 1.0
                    elif it == "integer":
                        item_example[ik] = 1
                    else:
                        item_example[ik] = None
                example[key] = [item_example]
            else:
                example[key] = ["<example item>"]
        elif ptype == "number":
            example[key] = 1.0
        elif ptype == "integer":
            example[key] = 1
        elif ptype == "boolean":
            example[key] = True
        else:
            example[key] = None
    return example


# ---------------------------------------------------------------------------
# JSON extraction utility
# ---------------------------------------------------------------------------

def _escape_newlines_in_json(text: str) -> str:
    """
    Escape raw newlines that appear inside JSON string values.
    Handles escaped quotes (\\") correctly so they don't toggle string state.
    """
    result = []
    in_string = False
    i = 0
    while i < len(text):
        char = text[i]
        
        # Handle escaped characters
        if char == '\\' and i + 1 < len(text):
            result.append(text[i:i+2])
            i += 2
            continue
            
        # Toggle string state on unescaped quotes
        if char == '"':
            in_string = not in_string
            result.append(char)
        # Escape literal newlines if inside a string
        elif in_string and char == '\n':
            result.append('\\n')
        elif in_string and char == '\r':
            result.append('\\r')
        else:
            result.append(char)
        i += 1
    return "".join(result)


def _pre_clean_json(text: str) -> str:
    """Aggressively pre-clean severely malformed JSON, aware of string boundaries."""
    # 1. First, handle the most common non-structural fixes that are safe
    # Collapse multiple colons:  "key" : : : value -> "key" : value
    text = re.sub(r':(?:\s*:\s*)+', ':', text)
    
    # 2. Balance unclosed quotes first so string-aware logic works
    in_string = False
    escape = False
    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
    if in_string:
        text += '"'

    # 3. String-aware cleaning
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        char = text[i]
        
        if escape:
            result.append(char)
            escape = False
            i += 1
            continue
        
        if char == '\\':
            result.append(char)
            escape = True
            i += 1
            continue
            
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
            
        if in_string:
            result.append(char)
            i += 1
            continue
            
        # Outside of strings, we can do structural cleanup
        if char == ',':
            # Peek ahead to remove trailing commas before } or ] or end of text
            next_chars = text[i+1:].lstrip()
            if not next_chars or next_chars[0] in ('}', ']'):
                i += (len(text[i+1:]) - len(next_chars)) + 1
                continue
                
        result.append(char)
        i += 1
    
    text = "".join(result)

    # 4. Balance unclosed braces/brackets using a stack (string-aware)
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    _closing = {"{": "}", "[": "]"}
    for opener in reversed(stack):
        text += _closing[opener]

    return text


def _extract_json(text: str | None) -> dict[str, Any]:
    """Extract and parse the first JSON object found in text with multiple recovery strategies."""
    if text is None:
        return {}

    # 1. Remove thinking tags (OpenRouter reasoning models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)

    cleaned = text.strip()

    # 2. Remove markdown code blocks if the model wrapped the whole thing
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

    # 3. Find the first '{' to start the JSON object
    start = cleaned.find("{")
    if start == -1:
        logger.error("No opening '{' found in AI response.")
        return {}
    
    # 4. Pre-clean everything from the first {
    cleaned = _pre_clean_json(cleaned[start:])

    # 5. Attempt parsing with progressive fixes
    attempts = [
        ("raw", lambda x: x),
        ("escaped-newlines", lambda x: _escape_newlines_in_json(x)),
        ("brute-force-braces", lambda x: _pre_clean_json(x + "}")),
        ("brute-force-array-end", lambda x: _pre_clean_json(x + "]}"))
    ]

    for name, fix_fn in attempts:
        try:
            candidate = fix_fn(cleaned)
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 6. Progressive substring attempt: if it's an array, try to find the last complete object
    if '"scenes"' in cleaned or '[' in cleaned:
        # Try to find the last complete object in the array
        last_obj_end = cleaned.rfind("}")
        if last_obj_end != -1:
            try:
                # Find the start of the scenes array to preserve structure
                scenes_start = cleaned.find("[")
                if scenes_start != -1:
                    partial = cleaned[:last_obj_end + 1] + "]}"
                    candidate = _pre_clean_json(partial)
                    return json.loads(candidate)
            except:
                pass

    # 7. Targeted Fallbacks for simple schemas
    if '"optimized_idea"' in cleaned:
        match = re.search(r'"optimized_idea"\s*:\s*"(.*?)"', cleaned, re.DOTALL)
        if match: return {"optimized_idea": match.group(1)}
    
    if '"optimized_keyword"' in cleaned:
        match = re.search(r'"optimized_keyword"\s*:\s*"(.*?)"', cleaned, re.DOTALL)
        if match: return {"optimized_keyword": match.group(1)}

    logger.error(f"Final JSON parsing failure. Snippet: {cleaned[:200]}...")
    return {}


# ---------------------------------------------------------------------------
# Ollama backend — uses /api/chat for proper instruction-following
# ---------------------------------------------------------------------------

def _ollama_chat(messages: list[dict], schema: dict[str, Any], ai_settings: dict[str, Any]) -> dict[str, Any]:
    """
    Call Ollama /api/chat with structured JSON output.
    """
    import requests

    base_url = ai_settings.get("ollama_base_url", "http://localhost:11434").rstrip("/")
    url = f"{base_url}/api/chat"
    model = ai_settings.get("ollama_model") or ""
    if not model:
        raise AiServiceError("Ollama model is not configured in settings. Please configure it in the UI settings page.")
    payload = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 4096,
        },
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AiServiceError(f"Ollama connection error: {exc}") from exc

    try:
        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            # Handle cases where model might have failed or returned empty
            logger.error(f"Ollama returned empty content. Full response: {data}")
            return {}
        return _extract_json(content)
    except json.JSONDecodeError as exc:
        raise AiServiceError(f"Ollama returned malformed JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# OpenAI backend (and compatible ones like OpenRouter)
# ---------------------------------------------------------------------------

def _openai_chat(messages: list[dict], schema: dict[str, Any], ai_settings: dict[str, Any], provider: str = "openai", max_tokens: int = 4096) -> dict[str, Any]:
    """
    Call OpenAI-compatible chat API with one retry only for transient network errors.
    Empty content or JSON parsing failures raise immediately with a clear message.
    """
    import requests

    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = ai_settings.get("openrouter_api_key")
        model = ai_settings.get("openrouter_model", "anthropic/claude-3.5-sonnet")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/MakeVideo",
            "X-Title": "MakeVideo",
            "Content-Type": "application/json",
        }
    elif provider == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        api_key = ai_settings.get("nvidia_api_key")
        model = ai_settings.get("nvidia_model") or ""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        url = "https://api.openai.com/v1/chat/completions"
        api_key = ai_settings.get("openai_api_key")
        model = ai_settings.get("openai_model") or ""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    if not api_key:
        raise AiServiceError(f"API key for {provider} is not configured in settings.")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    # Start with JSON mode enabled
    payload["response_format"] = {"type": "json_object"}

    max_retries = 2
    retry_delay = 3
    json_mode_removed = False

    for attempt in range(max_retries):
        try:
            logger.info(f"AI request {attempt + 1}/{max_retries} for {provider} ({model})")
            response = requests.post(url, json=payload, headers=headers)

            # 1. JSON mode unsupported — remove it and retry once immediately
            if response.status_code in (400, 422) and "response_format" in payload and not json_mode_removed:
                error_text = response.text.lower()
                if "response_format" in error_text or "json_object" in error_text or "unsupported" in error_text:
                    logger.warning(f"{provider.capitalize()} doesn't support json_object mode, falling back.")
                    del payload["response_format"]
                    json_mode_removed = True
                    continue

            # 2. Transient network errors — retry once
            is_provider_error = response.status_code == 400 and "Provider returned error" in response.text
            if response.status_code >= 500 or is_provider_error or response.status_code == 429:
                if attempt < max_retries - 1:
                    logger.warning(f"Transient error ({response.status_code}) from {provider}, retrying in {retry_delay}s...")
                    continue

            # 3. Non-OK response — raise immediately with details
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                except Exception:
                    error_msg = response.text[:500]
                raise AiServiceError(f"{provider.capitalize()} API error ({response.status_code}): {error_msg}")

            # 4. Parse response
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if not content:
                # Log full response for debugging empty content
                logger.error(f"{provider.capitalize()} returned empty content. Full response: {data}")
                raise AiServiceError(f"{provider.capitalize()} returned empty content. This might be due to safety filters or model failure.")

            result = _extract_json(content)
            if not result:
                # Log snippet of failed content
                snippet = content[:500].replace('\n', ' ')
                raise AiServiceError(
                    f"{provider.capitalize()} returned content that could not be parsed as JSON. "
                    f"Raw content snippet: {snippet}..."
                )

            # Reject responses that parrot back the JSON schema definition
            if result.get("type") == "object" and "properties" in result:
                actual = {k: v for k, v in result.items() if k not in ("type", "properties", "required", "items")}
                if actual:
                    logger.warning("Model returned schema wrapper; extracting actual data keys.")
                    result = actual
                else:
                    raise AiServiceError(
                        f"{provider.capitalize()} returned a JSON schema definition instead of data. "
                        f"Try using a different model."
                    )

            return result

        except requests.RequestException as exc:
            if attempt < max_retries - 1:
                logger.warning(f"Connection error: {exc}, retrying in {retry_delay}s...")
                continue
            raise AiServiceError(f"{provider.capitalize()} connection error: {exc}") from exc

    raise AiServiceError(f"{provider.capitalize()} failed after {max_retries} attempts.")


# ---------------------------------------------------------------------------
# Gemini (Vertex AI) backend
# ---------------------------------------------------------------------------

def _gemini_json(prompt: str, schema: dict[str, Any], ai_settings: dict[str, Any]) -> dict[str, Any]:
    project_id = ai_settings.get("vertex_project_id")
    if not project_id:
        raise AiServiceError("Vertex Project ID is not configured in settings.")
    model = ai_settings.get("gemini_model") or ""
    if not model:
        raise AiServiceError("Gemini model is not configured in settings. Please configure it in the UI settings page.")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=ai_settings.get("vertex_location", "us-central1"),
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.7,
            ),
        )
        return _extract_json(response.text or "{}")
    except Exception as exc:
        raise AiServiceError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Settings Loader
# ---------------------------------------------------------------------------

def _get_ai_settings() -> dict[str, Any]:
    """Fetch current AI settings from the database, falling back to .env defaults."""
    from ..config import settings as env_settings

    with SessionLocal() as db:
        s = db.scalar(select(Settings))
        if not s:
            s = Settings()
            db.add(s)
            db.commit()
            db.refresh(s)

        return {
            "provider": s.llm_provider or env_settings.llm_provider,
            "ollama_base_url": s.ollama_base_url or env_settings.ollama_base_url,
            "ollama_model": s.ollama_model or env_settings.ollama_model,
            "openai_api_key": s.openai_api_key or env_settings.openai_api_key,
            "openai_model": s.openai_model or env_settings.openai_model,
            "openrouter_api_key": s.openrouter_api_key or env_settings.openrouter_api_key,
            "openrouter_model": s.openrouter_model or env_settings.openrouter_model,
            "vertex_project_id": s.vertex_project_id or env_settings.vertex_project_id,
            "vertex_location": s.vertex_location or env_settings.vertex_location,
            "gemini_model": s.gemini_model or env_settings.gemini_model,
            "nvidia_api_key": s.nvidia_api_key or env_settings.nvidia_api_key,
            "nvidia_model": s.nvidia_model or env_settings.nvidia_model,
        }


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------

def _generate_text(system_prompt: str, user_prompt: str) -> str:
    """Generate plain text from the configured AI provider without JSON schema enforcement."""
    ai_settings = _get_ai_settings()
    provider = ai_settings.get("provider", "ollama").lower()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if provider == "ollama":
        import requests
        base_url = ai_settings.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"
        model = ai_settings.get("ollama_model") or ""
        if not model:
            raise AiServiceError("Ollama model is not configured in settings. Please configure it in the UI settings page.")
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 4096},
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                raise AiServiceError("Ollama returned empty content.")
            return content.strip()
        except requests.RequestException as exc:
            raise AiServiceError(f"Ollama connection error: {exc}") from exc

    if provider in ("openai", "openrouter", "nvidia"):
        if provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            api_key = ai_settings.get("openrouter_api_key")
            model = ai_settings.get("openrouter_model") or ""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/MakeVideo",
                "X-Title": "MakeVideo",
                "Content-Type": "application/json",
            }
        elif provider == "nvidia":
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            api_key = ai_settings.get("nvidia_api_key")
            model = ai_settings.get("nvidia_model") or ""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        else:
            url = "https://api.openai.com/v1/chat/completions"
            api_key = ai_settings.get("openai_api_key")
            model = ai_settings.get("openai_model") or ""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

        if not api_key:
            raise AiServiceError(f"API key for {provider} is not configured in settings.")
        if not model:
            raise AiServiceError(f"Model for {provider} is not configured in settings. Please configure it in the UI settings page.")

        payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 4096}
        import requests
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise AiServiceError(f"{provider.capitalize()} returned empty content.")
            return content.strip()
        except requests.RequestException as exc:
            raise AiServiceError(f"{provider.capitalize()} connection error: {exc}") from exc

    if provider == "vertex":
        project_id = ai_settings.get("vertex_project_id")
        if not project_id:
            raise AiServiceError("Vertex Project ID is not configured in settings.")
        model = ai_settings.get("gemini_model") or ""
        if not model:
            raise AiServiceError("Gemini model is not configured in settings. Please configure it in the UI settings page.")
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(vertexai=True, project=project_id, location=ai_settings.get("vertex_location", "us-central1"))
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            text = (response.text or "").strip()
            if not text:
                raise AiServiceError("Gemini returned empty content.")
            return text
        except Exception as exc:
            raise AiServiceError(str(exc)) from exc

    raise AiServiceError(f"Unsupported AI provider: {provider}")


def generate_text(system_prompt: str, user_prompt: str) -> str:
    """Public wrapper for plain text generation."""
    return _generate_text(system_prompt, user_prompt)


def _generate_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
    max_tokens: int = 4096
) -> dict[str, Any]:
    """Route to the configured model provider."""
    ai_settings = _get_ai_settings()
    provider = ai_settings.get("provider", "ollama").lower()

    if provider != "ollama":
        # Show a simple example instead of the raw JSON schema so weak models
        # don't parrot back schema keywords like "type", "properties", etc.
        example = _schema_to_example(schema)
        instruction = (
            "\n\nCRITICAL: You MUST return a single valid JSON object. "
            "Do not include any thinking tags, markdown code blocks, or preamble. "
            "Return ONLY the JSON data, not schema definitions. "
            "Your response must look exactly like this example (replace placeholder values with real data):\n"
            f"{json.dumps(example, indent=2)}"
        )
        system_prompt += instruction

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        if provider == "ollama":
            return _ollama_chat(messages, schema, ai_settings)

        if provider == "openai":
            return _openai_chat(messages, schema, ai_settings, provider="openai", max_tokens=max_tokens)

        if provider == "openrouter":
            return _openai_chat(messages, schema, ai_settings, provider="openrouter", max_tokens=max_tokens)

        if provider == "nvidia":
            return _openai_chat(messages, schema, ai_settings, provider="nvidia", max_tokens=max_tokens)

        if provider == "vertex":
            # Vertex AI — combine into a single prompt string
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            return _gemini_json(full_prompt, schema, ai_settings)

        raise AiServiceError(f"Unsupported AI provider: {provider}")
    except AiServiceError:
        raise
    except Exception as exc:
        logger.error("Unexpected error in _generate_json with provider %s: %s", provider, exc)
        raise AiServiceError(f"AI provider {provider} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(idea: str, video_format: str, language: str = "english", video_length: str = "auto") -> dict[str, Any]:
    """
    Generate a production-ready YouTube video script from a raw idea.

    Presets:
    - auto: AI decides best length
    - short: ~60 seconds (80-120 words)
    - medium: 3-5 minutes (450-700 words)
    - long: 10+ minutes (1400-1800 words)
    """
    # Validate input
    if not idea or len(idea.strip()) < 5:
        raise AiServiceError("Idea is too short to generate a script")

    if video_format == "shorts":
        # Shorts are always short-form, ignore length preset if it's too long
        length_rules = (
            "Target exactly 80-120 spoken words total. "
            "Start with a strong hook (first 1-2 sentences) to grab attention instantly. "
            "Fast pacing. No chapter structure. No calls to action."
        )
    else:
        # Long-form presets
        if video_length == "short":
            length_rules = "Target 120-200 spoken words (~1-2 mins). Brief and punchy overview."
        elif video_length == "medium":
            length_rules = "Target 450-700 spoken words (~3-5 mins). Detailed exploration with good depth."
        elif video_length == "long":
            length_rules = "Target 1400-1800 spoken words (~10-12 mins). Comprehensive, deep-dive coverage."
        else: # auto
            length_rules = (
                "Analyze the idea complexity and decide the optimal length. "
                "Target anywhere from 300 to 1500 words. "
                "More complex ideas get more words. If the idea is simple, keep it concise."
            )
        
        length_rules += (
            " Start with an engaging hook. The rest covers the topic thoroughly with clear structure. "
            "Include retention beats and smooth section transitions. No calls to action."
        )

    system_prompt = (
        "You are an elite YouTube scriptwriter who has written for channels with over 1 million subscribers. "
        "Scripts must feel like a real creator talking naturally, not a blog post being read aloud. "
        "You deeply understand YouTube retention mechanics: pattern interrupts, open loops, curiosity gaps, "
        "and re-engagement beats every 60 to 90 seconds in long videos. "
        "The first sentence of every script must be a hard-hitting statement, a counter-intuitive claim, "
        "or a shocking question that makes the viewer stop scrolling within 3 seconds. "
        "The script must never start with 'In this video', 'Today we', 'Welcome back', or 'Have you ever'. "
        "Include inline pacing cues like [PAUSE], [CUT TO B-ROLL], and [ZOOM IN] at natural edit points; "
        "these are director notes for the editor embedded directly in the script text. "
        "For long videos, section transitions must use retention phrases like 'But here is where it gets interesting' "
        "or 'Now this is the part most people miss'. "
        "No calls to action, subscribe reminders, or channel promotion anywhere in the output. "
        "Return only the JSON object. No markdown, no explanation."
    )
    user_prompt = (
        f"Write a YouTube video script for this idea:\n{idea}\n\n"
        f"Format: {video_format}\n"
        f"Language: {language}\n"
        f"Rules: {length_rules}\n"
        "Return all fields in one single JSON response.\n"
        "Return exactly 5 title_suggestions.\n"
        "If language is 'hindi', video_script MUST be in Hindi using Devanagari script, "
        "but description, tags, and chapters MUST remain in English for SEO.\n\n"
        "Return a JSON object with: video_script, on_screen_notes, title_suggestions, "
        "description, tags, chapters, hook_type, estimated_duration, tone."
    )
    return _generate_json(system_prompt, user_prompt, SCRIPT_SCHEMA)


def generate_scenes(script_text: str, video_format: str, language: str = "english") -> list[dict[str, Any]]:
    """
    Break an approved script into stock-video scenes.

    Scene counts:
    - Shorts: 4–8 punchy scenes
    - Long:   15–30 well-paced scenes

    Voiceover word-count targets per scene:
    - Shorts: 10–25 words
    - Long:   40–60 words
    """
    # Validate input
    if not script_text or len(script_text.strip()) < 10:
        raise AiServiceError("Script text is too short to generate scenes")

    if video_format == "shorts":
        count_rule = "Create exactly 4 to 8 scenes."
    elif video_format == "image_story":
        count_rule = "Create 10 to 15 scenes."
    else:
        count_rule = "Create 15 to 30 scenes."

    if video_format == "image_story":
        system_prompt = (
            "You are a master storyboard artist and cinematic director. "
            "Break scripts into evocative, highly descriptive scenes specifically for AI image generation. "
            "The 'description' field for each scene must be rich with narrative detail, capturing character emotions, "
            "specific environment features, and atmospheric cues. "
            "visual_keyword should be a concise summary of the core subject. "
            "Ensure every scene feels like a distinct beat in a visual story. "
            "Return only the JSON object. No markdown, no explanation."
        )
    else:
        system_prompt = (
            "You are a YouTube video director. "
            "Break scripts into concrete, searchable stock-video scenes. "
            "visual_keyword must always be 3 to 6 words, concrete, and specific: subject plus action plus setting. "
            "Avoid specific trademarks or copyrighted names (e.g. DOOM, Mario, Cyberpunk) in visual_keyword. "
            "Instead, use descriptive phrases that capture the vibe: 'retro 16-bit pixel art character jumping', 'futuristic neon city street rainy night', 'gamer hands on mechanical keyboard close up'. "
            "Never use abstract words in visual_keyword: success, growth, innovation, concept, idea, future, hope, journey, path, vision. "
            "Adjacent scenes must have different keywords; no two consecutive scenes may use the same keyword or very similar keywords. "
            "voiceover_text for each scene must map exactly to the corresponding portion of the approved script, word for word. "
            "Return only the JSON object. No markdown, no explanation."
        )
    user_prompt = (
        f"Break this script into scenes.\nFormat: {video_format}\nRules: {count_rule}\n\n"
        f"Script:\n{script_text}\n\n"
        f"Language: {language}\n"
        "CRITICAL: visual_keyword MUST always be in English, even if the script is in another language.\n"
        "scene_index, description, visual_keyword, voiceover_text, duration_seconds."
    )
    result = _generate_json(system_prompt, user_prompt, SCENES_SCHEMA)
    scenes = result.get("scenes", [])
    if not scenes:
        raise AiServiceError("AI returned an empty scenes list. Please try regenerating.")
    return scenes


def optimize_idea(idea: str) -> str:
    """Expand a rough idea into a detailed premise."""
    system_prompt = (
        "You are an elite YouTube Content Strategist. Your task is to transform a raw, basic idea into a "
        "comprehensive, high-quality production premise that serves as a perfect blueprint for a scriptwriter. "
        "Expand the idea by adding: 1) A unique high-retention narrative angle, 2) Specific technical details or "
        "concrete examples, and 3) A clear structural framing. "
        "The output must be pure content—dense, professional, and ready for production. "
        "Do NOT include conversational filler, introductory phrases (like 'Here is...'), or meta-commentary. "
        "IMPORTANT: Do not use double quote characters (\\\") inside the optimized_idea text. "
        "If you need to quote something, use single quotes (')."
    )
    user_prompt = f"Optimize this rough idea:\n{idea}"
    result = _generate_json(system_prompt, user_prompt, IDEA_OPTIMIZER_SCHEMA)
    return result.get("optimized_idea", idea)


def optimize_visual_keyword(description: str, current_keyword: str) -> str:
    """Refine a scene keyword for better stock video search results."""
    system_prompt = (
        "You are a master stock video curator. Transform a scene description into a high-converting Pexels search query. "
        "The keyword MUST be concrete, visual, and specific. Use a 'Subject + Action + Environment' formula. "
        "Avoid ALL abstract terms: growth, success, concept, idea, connection, future, innovation, happiness. "
        "Focus on tangible elements that search engines can actually index. "
        "Return ONLY the optimized keyword string. "
        "IMPORTANT: Do not use double quote characters (\\\") inside the keyword text. "
        "If you need to quote something, use single quotes (')."
    )
    user_prompt = f"Scene Description: {description}\nCurrent Keyword: {current_keyword}\n\nOptimize the keyword for a stock video search."
    result = _generate_json(system_prompt, user_prompt, KEYWORD_OPTIMIZER_SCHEMA)
    return result.get("optimized_keyword", current_keyword)


def score_clips_for_scene(scene_description: str, scene_keyword: str, clips: list[dict]) -> list[dict]:
    """
    Score candidate clips for a single scene by visual relevance.
    Input clips contain {clip_id, name, source, duration, thumbnail}.
    """
    system_prompt = (
        "You are an expert video editor scoring B-roll stock footage for visual relevance. "
        "Score each clip 0.0–1.0 based on how well its name, tags, and source metadata match the scene. "
        "Score criteria: "
        "1.0 = exact subject+action+setting match. "
        "0.7 = correct subject, similar action. "
        "0.4 = related domain but vague. "
        "0.1 = generic/unrelated. "
        "Penalize clips with generic names like 'untitled', 'video', single words. "
        "Boost clips whose name contains words from the visual keyword. "
        "Return ONLY a JSON object with a scored_clips array."
    )
    user_prompt = (
        f"Scene description:\n{scene_description}\n\n"
        f"Visual keyword:\n{scene_keyword}\n\n"
        f"Clip candidates:\n{json.dumps(clips, indent=2)}"
    )
    result = _generate_json(system_prompt, user_prompt, CLIP_SCORER_SCHEMA)
    scored = result.get("scored_clips", [])
    return sorted(scored, key=lambda item: float(item.get("score", 0.0)), reverse=True)
