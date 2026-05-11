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

CLIP_SELECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "selections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "integer"},
                    "selected_clip_id": {"type": "integer"},
                },
                "required": ["scene_id", "selected_clip_id"],
            },
        }
    },
    "required": ["selections"],
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


# ---------------------------------------------------------------------------
# JSON extraction utility
# ---------------------------------------------------------------------------

def _extract_json(text: str | None) -> dict[str, Any]:
    """Extract and parse the first JSON object found in text."""
    if text is None:
        return {}
    
    # Remove thinking tags if present (common in OpenRouter reasoning models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    
    cleaned = text.strip()
    # Strip markdown code fences if model wrapped output
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    
    # Find the first { and the last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # One last attempt: try to fix common trailing comma issue or small errors
        try:
            # Simple cleanup for trailing commas in arrays/objects
            cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
            return json.loads(cleaned)
        except Exception:
            logger.error(f"Failed to parse JSON from: {text[:200]}...")
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
    payload = {
        "model": ai_settings.get("ollama_model", "llama3"),
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 4096,
        },
    }
    try:
        response = requests.post(url, json=payload, timeout=180)
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

def _openai_chat(messages: list[dict], schema: dict[str, Any], ai_settings: dict[str, Any], provider: str = "openai") -> dict[str, Any]:
    """
    Call OpenAI-compatible chat API with robust retries and JSON mode fallback.
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
    else:
        url = "https://api.openai.com/v1/chat/completions"
        api_key = ai_settings.get("openai_api_key")
        model = ai_settings.get("openai_model", "gpt-4o")
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
    }

    if provider == "openrouter":
        payload["reasoning"] = {"enabled": False}

    # Start with JSON mode enabled
    payload["response_format"] = {"type": "json_object"}

    max_retries = 3
    retry_delay = 2
    timeout = 300  # Increased to 5 minutes for "too much step" tasks

    for attempt in range(max_retries):
        try:
            logger.info(f"AI Attempt {attempt + 1}/{max_retries} for {provider} ({model})")
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            
            # 1. Handle JSON mode support issues (400/422)
            if response.status_code in (400, 422) and "response_format" in payload:
                error_text = response.text.lower()
                if "response_format" in error_text or "json_object" in error_text or "unsupported" in error_text:
                    logger.warning(f"{provider.capitalize()} doesn't support json_object mode, falling back.")
                    del payload["response_format"]
                    continue  # Retry immediately without JSON mode

            # 2. Handle transient errors (5xx) or OpenRouter provider errors
            if response.status_code >= 500 or (response.status_code == 400 and "Provider returned error" in response.text):
                if attempt < max_retries - 1:
                    logger.warning(f"Transient error ({response.status_code}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
            
            # 3. Raise for other status codes
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                except Exception:
                    error_msg = response.text
                raise AiServiceError(f"{provider.capitalize()} API error: {error_msg}")

            # 4. Successful response
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            if not content or content == "{}":
                 if attempt < max_retries - 1:
                    logger.warning("Empty content from AI, retrying...")
                    continue
            
            result = _extract_json(content)
            if not result and attempt < max_retries - 1:
                logger.warning(f"Failed to extract JSON from {provider} response, retrying...")
                continue
                
            return result

        except requests.RequestException as exc:
            if attempt < max_retries - 1:
                logger.warning(f"Connection error: {exc}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
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
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=ai_settings.get("vertex_location", "us-central1"),
        )
        response = client.models.generate_content(
            model=ai_settings.get("gemini_model", "gemini-1.5-pro"),
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
    """Fetch current AI settings from the database."""
    with SessionLocal() as db:
        s = db.scalar(select(Settings))
        if not s:
            s = Settings()
            db.add(s)
            db.commit()
            db.refresh(s)
        
        return {
            "provider": s.llm_provider,
            "ollama_base_url": s.ollama_base_url,
            "ollama_model": s.ollama_model,
            "openai_api_key": s.openai_api_key,
            "openai_model": s.openai_model,
            "openrouter_api_key": s.openrouter_api_key,
            "openrouter_model": s.openrouter_model,
            "vertex_project_id": s.vertex_project_id,
            "vertex_location": s.vertex_location,
            "gemini_model": s.gemini_model,
        }


# ---------------------------------------------------------------------------
# Unified dispatch
# ---------------------------------------------------------------------------

def _generate_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Route to the configured model provider."""
    ai_settings = _get_ai_settings()
    provider = ai_settings.get("provider", "ollama").lower()

    if provider != "ollama":
        # For non-Ollama providers, we must reinforce the JSON schema in the system prompt
        # since we don't pass the schema object natively in the same way.
        schema_text = json.dumps(schema, indent=2)
        instruction = (
            f"\n\nCRITICAL: You MUST return a valid JSON object. "
            f"Do not include any thinking tags, markdown code blocks, or preamble. "
            f"The response must be a single JSON object matching this schema:\n{schema_text}"
        )
        # Append to the system prompt
        system_prompt += instruction

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if provider == "ollama":
        return _ollama_chat(messages, schema, ai_settings)
    
    if provider == "openai":
        return _openai_chat(messages, schema, ai_settings, provider="openai")
    
    if provider == "openrouter":
        return _openai_chat(messages, schema, ai_settings, provider="openrouter")
    
    if provider == "vertex":
        # Vertex AI — combine into a single prompt string
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        return _gemini_json(full_prompt, schema, ai_settings)

    raise AiServiceError(f"Unsupported AI provider: {provider}")


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
    if video_format == "shorts":
        count_rule = "Create exactly 4 to 8 scenes."
    else:
        count_rule = "Create 15 to 30 scenes."

    system_prompt = (
        "You are a YouTube video director. "
        "Break scripts into concrete, searchable stock-video scenes. "
        "visual_keyword must always be 3 to 6 words, concrete, and specific: subject plus action plus setting. "
        "Never use abstract words in visual_keyword: success, growth, innovation, concept, idea, future, hope, journey, path, vision. "
        "Adjacent scenes must have different keywords; no two consecutive scenes may use the same keyword or very similar keywords. "
        "voiceover_text for each scene must map exactly to the corresponding portion of the approved script, word for word. "
        "Return only the JSON object. No markdown, no explanation."
    )
    user_prompt = (
        f"Break this script into scenes.\nFormat: {video_format}\nRules: {count_rule}\n\n"
        f"Script:\n{script_text}\n\n"
        f"Language: {language}\n"
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
        "Do NOT include conversational filler, introductory phrases (like 'Here is...'), or meta-commentary."
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
        "Return ONLY the optimized keyword string."
    )
    user_prompt = f"Scene Description: {description}\nCurrent Keyword: {current_keyword}\n\nOptimize the keyword for a stock video search."
    result = _generate_json(system_prompt, user_prompt, KEYWORD_OPTIMIZER_SCHEMA)
    return result.get("optimized_keyword", current_keyword)


def select_best_clips(scenes_data: list[dict]) -> list[dict]:
    """
    Pick the best clip for each scene from a list of candidates.
    Input: list of {scene_id, description, candidates: [{clip_id, name}]}
    Output: list of {scene_id, selected_clip_id}
    """
    system_prompt = (
        "You are an expert video editor. "
        "For each scene, choose the ONE clip from the candidates that best matches the scene description. "
        "The candidates have descriptive names (slugs) from Pexels. "
        "Return ONLY a JSON object with a 'selections' array."
    )
    user_prompt = f"Scenes and their clip candidates:\n{json.dumps(scenes_data, indent=2)}"
    result = _generate_json(system_prompt, user_prompt, CLIP_SELECTOR_SCHEMA)
    return result.get("selections", [])


def score_clips_for_scene(scene_description: str, scene_keyword: str, clips: list[dict]) -> list[dict]:
    """
    Score candidate clips for a single scene by visual relevance.
    Input clips contain {clip_id, name, source, duration}.
    Output is sorted by score descending.
    """
    system_prompt = (
        "You are an expert video editor scoring stock video candidates for visual relevance to a scene. "
        "Score each clip from 0.0 to 1.0 based on how specifically it matches the scene description and keyword. "
        "Favor concrete subject/action/setting matches over generic mood matches. "
        "Return ONLY a JSON object with a scored_clips array."
    )
    user_prompt = (
        f"Scene description:\n{scene_description}\n\n"
        f"Scene visual keyword:\n{scene_keyword}\n\n"
        f"Clip candidates:\n{json.dumps(clips, indent=2)}"
    )
    result = _generate_json(system_prompt, user_prompt, CLIP_SCORER_SCHEMA)
    scored = result.get("scored_clips", [])
    return sorted(scored, key=lambda item: float(item.get("score", 0.0)), reverse=True)
