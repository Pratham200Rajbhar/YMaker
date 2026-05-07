import logging
from pathlib import Path
import numpy as np
import soundfile as sf
import riva.client
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
    if not settings.nvidia_api_key:
        raise VoiceServiceError("NVIDIA_API_KEY not configured")

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
            ["function-id", "877104f7-e885-42b9-8de8-f6e4c6303969"],
            ["authorization", f"Bearer {settings.nvidia_api_key}"]
        ]
    )
    tts_client = riva.client.SpeechSynthesisService(auth)

    all_audio_chunks = []
    sample_rate = 22050

    # Sort scenes by index
    scenes = sorted(project.scenes, key=lambda s: s.scene_index)
    
    for scene in scenes:
        if not scene.voiceover_text.strip():
            logger.warning("Scene %d has no voiceover text, skipping", scene.scene_index)
            continue

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
