# Master Prompt: Automated Clip Flow Implementation

## Overview
Modify the YMaker pipeline to automate stock video selection. The user should no longer be required to manually pick clips. The system must "Fetch -> Score -> Select -> Download" in a single automated step.

## Instructions

### 1. Backend: Update `backend/app/routers/clips.py`

Modify the `fetch_clips` endpoint:
- **Fetch**: Call `fetch_clip_options(scene, project)` which already performs search and AI scoring.
- **Select**: Identify the clip with the highest `ai_score`.
- **Clean**: Clear any previous clips for the scene and append ONLY the top-ranked clip.
- **Approve**: Set `clip.selected = True`.
- **Progress**: 
    - Set `project.status = ProjectStatus.downloading_clips`.
    - Set `project.current_stage = WorkflowStage.voiceover`.
- **Trigger**: Add `_download_all_clips_bg(project_id)` to `BackgroundTasks`.

### 2. Backend: Logic Safeguards
- If no clips are found for a scene (even after fallback), raise a `502` error as before, but ensure the error message is clear that the keyword was too specific.
- Ensure `ProjectOut` reflects the new stage (`voiceover`) so the frontend updates immediately.

### 3. Verification
The goal is reached when a single click on "Fetch Clips" (or an automated trigger after scene approval) leads the project directly to the "Downloading" state without showing a gallery of choices to the user.
