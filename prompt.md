# Master Prompt — ScriptForge

Build a complete full-stack web application called **ScriptForge**.

ScriptForge is an AI-powered YouTube content production tool where a user submits a raw idea and moves through a **human-reviewed 5-stage workflow** to create a finished video:

**Idea → Script → Scene Breakdown → Stock Clip Selection → Voiceover → Final Video**

The application must be fully functional, production-style, modular, and runnable locally.

---

## Core Product Goal

The user should be able to:

1. Enter a rough YouTube idea.
2. Choose either **Shorts** or **Long Video** format.
3. Generate a structured YouTube script using **Vertex AI Gemini**.
4. Review and edit the script manually.
5. Generate scene breakdowns from the approved script.
6. Review and edit the scenes manually.
7. Fetch stock video options for each scene from **Pexels**.
8. Manually select one clip per scene.
9. Generate an AI voiceover.
10. Review and approve the voiceover.
11. Render a final video using stock clips, voiceover, and subtitles.
12. Preview and download the final MP4.

This product must behave like a guided creator workflow, not an instant black-box generator.

---

## Hard Constraints

Use these exact implementation decisions:

- **Frontend:** Next.js 14 with App Router
- **Styling:** Tailwind CSS
- **Backend:** FastAPI
- **Language:** Python 3.11+ for backend, TypeScript for frontend
- **Database:** SQLite only
- **ORM:** SQLAlchemy
- **LLM:** Vertex AI Gemini 2.5 Pro
- **Voiceover:** Edge-TTS
- **Subtitles:** Whisper
- **Stock videos:** Pexels Video API
- **Video rendering:** MoviePy + FFmpeg
- **No authentication**
- **No login system**
- **No user accounts**
- **No Docker**
- Must run locally with normal dev commands

Do not replace SQLite with PostgreSQL.
Do not replace Gemini with OpenAI.
Do not skip the human review gates.
Do not build only mock UI — build a real working app.

---

## Product Behavior

The application must enforce a strict approval-based workflow.

### Human Review Rule

Each stage must stop and wait for explicit approval before moving forward.

Required approval gates:

- Script must be approved before scenes are generated
- Scenes must be approved before clips are fetched and finalized
- Clips must be approved before voiceover moves forward
- Voiceover must be approved before final rendering starts

No auto-advancing.

---

## App Structure

The project should be split into:

- `backend/`
- `frontend/`

The backend should be modular and clean.
The frontend should use reusable components and typed API calls.

---

## Database Design

Use SQLite to persist all data locally.

Store all of the following:

- Projects
- Raw user ideas
- Video format
- Current workflow stage
- Script versions
- Script fields
- Scene records
- Clip options per scene
- Selected clips
- Voiceover file path
- Subtitle file path
- Render file path
- Render status
- Error states

The data model should include at minimum:

- **Project**
- **Script**
- **Scene**
- **Clip**
- **Render**

The project record should track the current active layer and overall status.

---

## Pages

### Home Page

The home page should include:

- Large idea textarea
- Format selector with:
  - Shorts
  - Long Video
- Create Project button
- Recent Projects list below

Each recent project card should show:

- Project title
- Format badge
- Current step
- Status
- Created date

Clicking a project should open its workflow page.

---

## Workflow Page

Create a dedicated project page for each project.

The workflow page must include:

- Left sidebar with 5 visible steps
- Main content area showing the current active stage
- Clear completed, active, and pending states
- Persistent project information
- Real-time refresh after each action

The sidebar should show these steps:

1. Script
2. Scenes
3. Clips
4. Voiceover
5. Final Video

---

## Step 1 — Script Generation

Use **Vertex AI Gemini** to generate a YouTube script from the raw idea.

The script must include:

- Hook
- Body
- CTA
- On-screen notes
- Title suggestions
- Estimated duration
- Tone

### Script Logic

If the user selected **Shorts**:
- Target 45–60 seconds
- Strong hook in first 3 seconds
- Fast pacing
- No long chapter structure

If the user selected **Long Video**:
- Target 8–12 minutes
- Structured sections
- Retention beats across the script
- More developed body

### Structured Output Requirement

Use structured JSON output from Gemini because Vertex AI supports schema-controlled structured output and JSON generation [web:47][web:48][web:61].

The UI for the script stage must include:

- Editable hook field
- Editable body field
- Editable CTA field
- Title suggestion chips
- Tone display
- Estimated duration display
- Save edits button
- Regenerate button
- Approve and continue button

The user must be able to edit before approval.

---

## Step 2 — Scene Breakdown

After the script is approved, generate scenes using Gemini.

Each scene must include:

- Scene index
- Description
- Visual keyword
- Duration in seconds
- Voiceover text for that scene

### Scene Rules

For **Shorts**:
- 4 to 8 scenes
- Short scene durations
- Punchy visual progression

For **Long Video**:
- 15 to 30 scenes
- Clear pacing
- Balanced timing for visuals and speech

Keywords must be concrete and visually searchable.
Avoid abstract keywords.

The scene review UI must include:

- Scene cards
- Editable description
- Editable keyword
- Editable duration
- Editable voiceover text
- Approve all scenes button

Scenes must not trigger clip fetching until approved.

---

## Step 3 — Stock Clip Selection

After scene approval, fetch stock video options for each scene using **Pexels**.

Use orientation filtering correctly:
- Use **portrait** orientation for Shorts
- Use **landscape** orientation for Long Video

Pexels video search supports orientation filtering and returns metadata for multiple video files and sizes [web:52][web:55][web:57].

For each scene:
- Search by the scene keyword
- Fetch top clip options
- Store clip metadata
- Show preview cards in UI
- Allow the user to choose exactly one clip per scene

The clips interface must include:

- Scene title
- Keyword label
- Clip thumbnails or video previews
- Resolution information
- Selected state styling
- Approval button

Before moving forward:
- Validate that each scene has one selected clip
- Download selected clips locally

---

## Step 4 — Voiceover

After clips are approved, generate a voiceover from the approved script using **Edge-TTS**.

Requirements:
- Support a few voice presets
- Save audio file locally
- Show native audio player
- Allow regeneration with another voice
- Require manual approval

The user must be able to listen before approving.

---

## Step 5 — Final Video Render

After voiceover approval, render the final video using **MoviePy**.

MoviePy should handle:
- Clip loading
- Clip trimming
- Clip ordering
- Resizing and cropping
- Audio composition
- Subtitle overlays
- MP4 export

MoviePy supports compositing, text overlays, concatenation, and final video export, which makes it appropriate for this build [web:25][web:64][web:65].

### Render Rules

For **Shorts**:
- Render vertical 1080x1920
- 9:16 aspect ratio

For **Long Video**:
- Render horizontal 1920x1080
- 16:9 aspect ratio

The final render should:
- Use selected scene clips in order
- Trim each clip to the approved duration
- Apply the generated voiceover
- Generate subtitles using Whisper
- Overlay subtitles onto the video
- Export MP4 locally
- Save render status in database

The final step UI must include:
- Render button
- Rendering progress state
- Polling status display
- Final preview player
- Download MP4 button
- Success state
- Error state with retry option

---

## Backend Requirements

Build a FastAPI backend with a clean modular structure.

The backend should include:

- app initialization
- CORS setup for local frontend
- SQLite database initialization
- SQLAlchemy models
- Pydantic schemas
- REST API endpoints
- static file serving for outputs
- service modules for each pipeline stage

The backend must support:

### Project endpoints
- create project
- list projects
- get project detail

### Script endpoints
- generate script
- update script
- regenerate script
- approve script

### Scene endpoints
- generate scenes
- update scene
- approve scenes

### Clip endpoints
- fetch clips
- select clip
- approve clips

### Voice endpoints
- generate voiceover
- approve voiceover

### Render endpoints
- start render
- poll render status
- download final video

Use background rendering behavior for video generation so the frontend can poll status.

Generated audio, subtitles, downloaded clips, and final videos must be saved locally and served through the backend.

---

## Frontend Requirements

Build a polished frontend with:

- Next.js 14 App Router
- Tailwind CSS
- TypeScript
- reusable UI components
- typed API layer
- responsive layouts
- clean loading and error states

The frontend should include:

### Reusable UI
- Step sidebar
- Status badges
- Loading skeletons
- Review cards
- Buttons with clear hierarchy
- Empty states
- Toast or inline feedback states

### Script stage UI
- Editing interface
- suggestion chips
- regenerate flow
- approval flow

### Scene stage UI
- scene card grid
- inline editing
- duration editing
- approval action

### Clip stage UI
- multiple preview cards per scene
- selection state
- re-search or refresh option
- approval action

### Voice stage UI
- audio player
- voice selector
- regeneration
- approval action

### Final stage UI
- render trigger
- progress state
- final preview
- download action

---

## UX Expectations

The product should feel simple but premium.

Design style:
- dark theme
- red accent
- clean spacing
- sharp hierarchy
- minimal clutter
- modern SaaS feel for creators

Behavior expectations:
- every action should feel explicit
- users should always understand what stage they are in
- AI output should always be editable before approval
- generated content should be shown inline, not hidden in popups
- approval buttons should be obvious and stage-based

---

## Quality Expectations

The implementation must be:
- complete
- modular
- readable
- practical
- MVP-ready
- easy to extend later with auth, cloud storage, Stripe, analytics, and queues

Do not produce a half-implemented scaffold.
Do not produce vague placeholders.
Build all major flows end-to-end.

---

## Non-Negotiables

- Use **SQLite**
- Use **FastAPI**
- Use **Next.js**
- Use **Vertex AI Gemini**
- Use **Pexels**
- Use **MoviePy**
- Use **Edge-TTS**
- Use **Whisper**
- Use **human approval at every stage**
- Build both backend and frontend
- Keep the system local-first and simple

---

## Final Instruction

Generate the full implementation for this application as a clean, production-style full-stack project with working backend and frontend, respecting all constraints above.