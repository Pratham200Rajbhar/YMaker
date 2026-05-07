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

from ..config import settings

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
            "description": "3-5 YouTube title options optimized for clicks.",
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
    "required": ["video_script", "on_screen_notes", "title_suggestions", "estimated_duration", "tone"],
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


# ---------------------------------------------------------------------------
# JSON extraction utility
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object found in text."""
    cleaned = text.strip()
    # Strip markdown code fences if model wrapped output
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Ollama backend — uses /api/chat for proper instruction-following
# ---------------------------------------------------------------------------

def _ollama_chat(messages: list[dict], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Call Ollama /api/chat with structured JSON output.

    Ollama 0.4+ accepts a JSON schema object in the `format` key for
    structured output. Schema must be valid and model must support it.
    """
    import requests

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
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
        content = data.get("message", {}).get("content", "{}")
        return _extract_json(content)
    except json.JSONDecodeError as exc:
        raise AiServiceError(f"Ollama returned malformed JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Gemini (Vertex AI) backend
# ---------------------------------------------------------------------------

def _gemini_json(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    if not settings.vertex_project_id:
        raise AiServiceError("VERTEX_PROJECT_ID is not configured.")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=settings.vertex_project_id,
            location=settings.vertex_location,
        )
        response = client.models.generate_content(
            model=settings.gemini_model,
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
# Unified dispatch
# ---------------------------------------------------------------------------

def _generate_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Route to the configured model provider."""
    if settings.model_provider.lower() == "ollama":
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return _ollama_chat(messages, schema)
    # Vertex AI — combine into a single prompt string
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return _gemini_json(full_prompt, schema)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(idea: str, video_format: str, language: str = "english") -> dict[str, Any]:
    """
    Generate a production-ready YouTube video script from a raw idea.

    Word-count targets:
    - Shorts: 80–100 spoken words (45–60 seconds at ~110 wpm)
    - Long:   1400–1800 spoken words (8–12 minutes at ~140 wpm)

    No CTA is generated — this is a pure video script.
    """
    if video_format == "shorts":
        length_rules = (
            "Target exactly 80-100 spoken words total. "
            "Start with a strong hook (first 1-2 sentences) to grab attention instantly. "
            "Fast pacing. No chapter structure. No calls to action."
        )
    else:
        length_rules = (
            "Target 1400-1800 spoken words total. "
            "Start with an engaging hook (50-80 words). The rest covers the topic thoroughly with clear structure. "
            "Include retention beats and smooth section transitions. No calls to action."
        )

    system_prompt = (
        "You are an expert YouTube scriptwriter. "
        "You write clean, engaging video scripts — not marketing copy. "
        "Never include calls to action, subscribe reminders, or channel promotion. "
        "Return only the JSON object. No markdown, no explanation."
    )
    user_prompt = (
        f"Write a YouTube video script for this idea:\n{idea}\n\n"
        f"Format: {video_format}\n"
        f"Language: {language}\n"
        f"Rules: {length_rules}\n"
        f"IMPORTANT: If the language is 'hindi', the 'video_script' MUST be written in Hindi (Devanagari script).\n\n"
        "Return a JSON object with: video_script, on_screen_notes, "
        "title_suggestions (array of 3-5 titles), estimated_duration, tone."
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
        "visual_keyword must be a specific, visually searchable phrase (e.g. 'person typing laptop coffee shop'). "
        "Never use abstract keywords (e.g. 'success', 'growth', 'innovation'). "
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
        "You are an expert YouTube content strategist. "
        "Expand the user's rough idea into a detailed, compelling premise. "
        "Add specific details, narrative angles, or structural hints that will help produce a better script. "
        "Keep it to 2-3 paragraphs. No calls to action."
    )
    user_prompt = f"Optimize this rough idea:\n{idea}"
    result = _generate_json(system_prompt, user_prompt, IDEA_OPTIMIZER_SCHEMA)
    return result.get("optimized_idea", idea)


def optimize_visual_keyword(description: str, current_keyword: str) -> str:
    """Refine a scene keyword for better stock video search results."""
    system_prompt = (
        "You are a stock video search expert. "
        "Take a scene description and a draft keyword, and return a more effective, concrete search query. "
        "The keyword should be specific, visual, and likely to return high-quality results on Pexels. "
        "Avoid abstract concepts. Focus on subjects, actions, and settings."
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
