import os
import sys
import logging
from pathlib import Path

# Add the backend directory to sys.path
sys.path.append(str(Path(__file__).parent))

from app.database import SessionLocal, init_db
from app.models import Project, ProjectStatus, WorkflowStage, Scene, Render, Clip
from app.services import ai, clips, voice, rendering
from app.schemas import VoiceGenerate
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_full_pipeline")

def test_pipeline():
    logger.info("Starting Full Pipeline Test")
    
    # 1. Initialize DB
    init_db()
    db = SessionLocal()
    
    try:
        # 2. Create Project
        project = Project(
            title="Test Space Travel",
            idea="A short video about traveling to Mars and the future of humanity.",
            video_format="shorts",
            language="english",
            current_stage=WorkflowStage.script.value,
            status=ProjectStatus.draft.value
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"Created Project: {project.id}")

        # 3. Generate Script
        logger.info("Step 1: Generating Script...")
        script_data = ai.generate_script(project.idea, project.video_format, project.language)
        project.video_script = script_data["video_script"]
        project.current_stage = WorkflowStage.scenes.value
        db.commit()
        logger.info("Script generated successfully.")

        # 4. Generate Scenes
        logger.info("Step 2: Generating Scenes...")
        scenes_data = ai.generate_scenes(project.video_script, project.video_format, project.language)
        for idx, s_data in enumerate(scenes_data):
            scene = Scene(
                project_id=project.id,
                scene_index=idx,
                description=s_data["description"],
                visual_keyword=s_data["visual_keyword"],
                duration_seconds=s_data["duration_seconds"],
                voiceover_text=s_data["voiceover_text"],
                approved=True
            )
            db.add(scene)
        project.current_stage = WorkflowStage.clips.value
        db.commit()
        db.refresh(project)
        logger.info(f"Generated {len(project.scenes)} scenes.")

        # 5. Select Clips (Simulated)
        logger.info("Step 3: Selecting Clips...")
        for scene in project.scenes:
            # We skip actual Pexels search in this test and just mock a clip if needed
            # or we can call clips.search_and_download_for_scene if pexels_api_key is set
            if settings.pexels_api_key:
                logger.info(f"Searching clips for scene {scene.scene_index}...")
                clip_options = clips.fetch_clip_options(scene, project)
                if clip_options:
                    # Just pick the first one for simplicity in the test
                    best = clip_options[0]
                    clip = Clip(
                        scene_id=scene.id,
                        pexels_id=best["pexels_id"],
                        url=best["url"],
                        preview_url=best["preview_url"],
                        image_url=best["image_url"],
                        width=best["width"],
                        height=best["height"],
                        duration=best["duration"],
                        selected=True
                    )
                    db.add(clip)
                    db.flush()
                    
                    logger.info(f"Downloading clip for scene {scene.scene_index}...")
                    clip.local_path = clips.download_selected_clip(project.id, clip)
                else:
                    logger.warning(f"No clips found for scene {scene.scene_index}")
            else:
                logger.warning(f"PEXELS_API_KEY not set, skipping clip selection for scene {scene.scene_index}")
        
        project.current_stage = WorkflowStage.voiceover.value
        db.commit()
        logger.info("Clip selection stage complete.")

        # 6. Generate Voiceover
        if settings.nvidia_api_key:
            logger.info("Step 4: Generating Voiceover via NVIDIA NIM...")
            voice.generate_voiceover(project, "Magpie-Multilingual.HI-IN.Aria", db)
            project.render.voiceover_approved = True
            project.current_stage = WorkflowStage.render.value
            db.commit()
            logger.info("Voiceover generated and approved.")
        else:
            logger.warning("NVIDIA_API_KEY not set, skipping voiceover generation.")

        # 7. Render Project
        if project.current_stage == WorkflowStage.render.value:
            logger.info("Step 5: Starting Render...")
            rendering.render_project(project.id)
            db.refresh(project)
            if project.render.render_status == "completed":
                logger.info(f"Pipeline Test Successful! Video at: {project.render.render_path}")
            else:
                logger.error(f"Render failed: {project.render.error_message}")
        else:
            logger.warning("Pipeline did not reach render stage.")

    except Exception as e:
        logger.error(f"Pipeline Test Failed: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    test_pipeline()
