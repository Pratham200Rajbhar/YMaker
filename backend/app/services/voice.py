import logging

import numpy as np
import soundfile as sf
from sqlalchemy.orm import Session

from ..models import Project, Render
from ..config import settings
from ..storage import ProjectStorage

logger = logging.getLogger(__name__)


class VoiceServiceError(RuntimeError):
    """Raised when voiceover generation fails."""
    pass


def generate_voiceover(project: Project, voice_name: str, db: Session) -> Render:
    """
    Generate voiceover for all scenes using NVIDIA Magpie TTS (NIM API).
    Concatenates the audio for all approved scenes into one file.
    """
    try:
        import riva.client
    except ImportError as exc:
        raise VoiceServiceError("nvidia-riva-client is not installed. Run: pip install nvidia-riva-client") from exc

    if not settings.nvidia_api_key:
        raise VoiceServiceError("NVIDIA_API_KEY not configured in settings")

    # Validate voice_name is not empty
    if not voice_name or not voice_name.strip():
        raise VoiceServiceError("Voice name cannot be empty")

    # Validate project has scenes
    if not project.scenes:
        raise VoiceServiceError("Project has no scenes to generate voiceover for")

    storage = ProjectStorage(project.id)
    render = project.render
    if not render:
        render = Render(project_id=project.id)
        db.add(render)
        db.flush()

    # Setup Riva Client
    auth = riva.client.Auth(
        uri="grpc.nvcf.nvidia.com:443",
        use_ssl=True,
        metadata_args=[
            ["function-id", settings.nvidia_tts_model],
            ["authorization", f"Bearer {settings.nvidia_api_key}"]
        ]
    )
    tts_client = riva.client.SpeechSynthesisService(auth)

    all_audio_chunks = []
    sample_rate = 22050

    # Sort scenes by index
    scenes = sorted(project.scenes, key=lambda s: s.scene_index)
    
    voiced_scenes = [scene for scene in scenes if scene.voiceover_text.strip()]
    if not voiced_scenes:
        raise VoiceServiceError("No scenes have voiceover text to generate audio for")
    
    for index, scene in enumerate(voiced_scenes):
        try:
            logger.info("Generating TTS for scene %d: %s", scene.scene_index, scene.voiceover_text[:50])
            response = tts_client.synthesize(
                text=scene.voiceover_text,
                voice_name=voice_name,
                language_code="hi-IN" if project.language == "hindi" else "en-US",
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
            )
            audio_data = np.frombuffer(response.audio, dtype=np.int16)
            all_audio_chunks.append(audio_data)
            if index < len(voiced_scenes) - 1:
                all_audio_chunks.append(np.zeros(int(sample_rate * 0.150), dtype=np.int16))
        except Exception as e:
            logger.error("Failed to generate TTS for scene %d: %s", scene.scene_index, str(e))
            raise VoiceServiceError(f"TTS generation failed for scene {scene.scene_index}: {e}") from e

    if not all_audio_chunks:
        raise VoiceServiceError("No voiceover text found in any scene")

    # Concatenate all chunks
    final_audio = np.concatenate(all_audio_chunks)
    
    # Save to WAV
    output_path = storage.get_voiceover_path("final_voiceover", ext=".wav")
    sf.write(str(output_path), final_audio, samplerate=sample_rate)
    
    render.voiceover_path = str(output_path)
    render.voice_name = voice_name
    render.voiceover_approved = False
    db.commit()
    
    return render


def generate_multivoice_voiceover(project: Project, voice_config: dict[int, str], default_voice: str, db: Session) -> Render:
    """
    Generate voiceover for all scenes using per-scene voice assignments.
    Falls back to scene.character_voice, then default_voice.
    """
    try:
        import riva.client
    except ImportError as exc:
        raise VoiceServiceError("nvidia-riva-client is not installed. Run: pip install nvidia-riva-client") from exc

    if not settings.nvidia_api_key:
        raise VoiceServiceError("NVIDIA_API_KEY not configured in settings")

    # Validate default_voice
    if not default_voice or not default_voice.strip():
        raise VoiceServiceError("Default voice name cannot be empty")

    # Validate project has scenes
    if not project.scenes:
        raise VoiceServiceError("Project has no scenes to generate voiceover for")

    storage = ProjectStorage(project.id)
    render = project.render
    if not render:
        render = Render(project_id=project.id)
        db.add(render)
        db.flush()

    auth = riva.client.Auth(
        uri="grpc.nvcf.nvidia.com:443",
        use_ssl=True,
        metadata_args=[
            ["function-id", settings.nvidia_tts_model],
            ["authorization", f"Bearer {settings.nvidia_api_key}"]
        ]
    )
    tts_client = riva.client.SpeechSynthesisService(auth)

    all_audio_chunks = []
    sample_rate = 22050

    scenes = sorted(project.scenes, key=lambda s: s.scene_index)
    voiced_scenes = [scene for scene in scenes if scene.voiceover_text.strip()]
    
    if not voiced_scenes:
        raise VoiceServiceError("No scenes have voiceover text to generate audio for")

    for index, scene in enumerate(voiced_scenes):
        scene_voice = voice_config.get(scene.id)
        if not scene_voice:
            scene_voice = scene.character_voice
        if not scene_voice:
            scene_voice = default_voice

        try:
            logger.info("Generating TTS for scene %d with voice %s: %s", scene.scene_index, scene_voice, scene.voiceover_text[:50])
            response = tts_client.synthesize(
                text=scene.voiceover_text,
                voice_name=scene_voice,
                language_code="hi-IN" if project.language == "hindi" else "en-US",
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
            )
            audio_data = np.frombuffer(response.audio, dtype=np.int16)
            all_audio_chunks.append(audio_data)
            if index < len(voiced_scenes) - 1:
                all_audio_chunks.append(np.zeros(int(sample_rate * 0.150), dtype=np.int16))
        except Exception as e:
            logger.error("Failed to generate TTS for scene %d: %s", scene.scene_index, str(e))
            raise VoiceServiceError(f"TTS generation failed for scene {scene.scene_index}: {e}") from e

    if not all_audio_chunks:
        raise VoiceServiceError("No voiceover text found in any scene")

    final_audio = np.concatenate(all_audio_chunks)
    output_path = storage.get_voiceover_path("final_voiceover", ext=".wav")
    sf.write(str(output_path), final_audio, samplerate=sample_rate)

    render.voiceover_path = str(output_path)
    render.voice_name = default_voice
    render.voiceover_approved = False
    db.commit()

    return render
