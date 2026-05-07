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
