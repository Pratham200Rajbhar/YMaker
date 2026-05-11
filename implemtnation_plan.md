# Implementation Plan: Automated Clip Selection

## Goal
Streamline the video production pipeline by automating the "Clips" stage. The system will now automatically fetch, score, and select the best clip for each scene, moving directly to the voiceover/download phase without requiring user intervention.

## Proposed Changes

### Backend Logic

#### [MODIFY] [clips.py](file:///disk2/Projects/IdeaBuilder/backend/app/routers/clips.py)
- **Refactor `fetch_clips`**:
    - Integrate the AI scoring logic directly into the fetch process.
    - Instead of saving multiple candidates, the endpoint will now identify the single best clip (highest AI score) for each scene.
    - It will mark that clip as `selected=True` and save only that one (or discard others).
    - It will immediately trigger the `_download_all_clips_bg` background task.
    - It will advance the `current_stage` to `voiceover` and `status` to `downloading_clips`.
- **Remove Manual Selection Endpoints**:
    - Endpoints like `/{scene_id}/select/{clip_id}` and `/auto-select` will become redundant but can be kept for internal API compatibility or removed if the UI is fully updated.

### Workflow Transition
1. **Script** (Manual Approval)
2. **Scenes** (Manual Approval)
3. **Automated Step**: `fetch_clips` now handles:
   - Search (4 sources)
   - Scoring (AI)
   - Selection (Best Match)
   - Background Download
4. **Voiceover** (Next interaction point)

## Verification Plan
1. **Automated Test**: Trigger a clip fetch for a project. Verify that the project status immediately changes to `downloading_clips` and only one clip exists per scene in the database.
2. **UI Check**: Ensure the "Production Flow" component reflects the jump from "Scenes" to "Voiceover" once fetching starts.
