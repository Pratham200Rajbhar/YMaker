# ScriptForge

An AI-powered video production pipeline that transforms raw ideas into polished video content. Built with a FastAPI backend and Next.js frontend.

## Features

- **AI Script Generation** — Generate production-ready YouTube video scripts from a rough idea
- **Scene Breakdown** — Automatically divide scripts into visually searchable stock-video scenes
- **Stock Media Integration** — Search and select clips from Pexels for each scene
- **AI-Powered Auto-Selection** — Let AI choose the best clips for each scene
- **Voiceover Generation** — Generate professional voiceovers using NVIDIA Magpie TTS
- **Video Rendering** — Composite clips, audio, and subtitles into a finished MP4
- **Whisper Transcription** — Automatic, accurate subtitle generation via OpenAI Whisper

## Architecture

```
IdeaBuilder/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py           # App entry point
│   │   ├── config.py         # Settings & configuration
│   │   ├── database.py       # SQLite database setup
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── storage.py        # File storage utilities
│   │   ├── routers/         # API route handlers
│   │   │   ├── projects.py   # Project CRUD
│   │   │   ├── scripts.py    # Script generation
│   │   │   ├── scenes.py     # Scene management
│   │   │   ├── clips.py      # Pexels clip fetching
│   │   │   ├── voice.py      # Voiceover generation
│   │   │   ├── render.py     # Video rendering
│   │   │   └── ai.py         # AI endpoints
│   │   └── services/
│   │       ├── ai.py         # AI service (Ollama/Gemini)
│   │       ├── voice.py      # NVIDIA TTS integration
│   │       ├── clips.py      # Pexels API integration
│   │       └── rendering.py  # MoviePy video composition
│   ├── storage/              # Generated media files
│   │   └── project_{id}/
│   │       ├── clips/        # Downloaded stock video clips
│   │       ├── voiceovers/   # Generated audio files
│   │       ├── subtitles/    # SRT subtitle files
│   │       └── renders/      # Final video output
│   └── scriptforge.db        # SQLite database
│
└── frontend/                 # Next.js frontend
    ├── app/
    │   ├── page.tsx          # Home page (project list)
    │   ├── projects/[id]/    # Project detail page
    │   └── layout.tsx        # Root layout
    ├── components/
    │   ├── ui.tsx            # Reusable UI components
    │   ├── StepSidebar.tsx   # Workflow progress sidebar
    │   └── stages/           # Video production stages
    │       ├── ScriptStage.tsx
    │       ├── ScenesStage.tsx
    │       ├── ClipsStage.tsx
    │       ├── VoiceStage.tsx
    │       └── RenderStage.tsx
    └── lib/
        ├── api.ts            # API client
        └── types.ts          # TypeScript types
```

## Workflow

The video production follows a 5-stage pipeline:

```
Script → Scenes → Clips → Voiceover → Render
```

1. **Script** — Enter an idea, AI generates a complete video script
2. **Scenes** — Script is broken into searchable, visual scenes
3. **Clips** — Stock video clips are searched and selected for each scene
4. **Voiceover** — Professional AI voiceover is generated
5. **Render** — Final MP4 is composited with clips, audio, and subtitles

## Tech Stack

### Backend
- **FastAPI** — Web framework
- **SQLAlchemy** — ORM with SQLite
- **MoviePy 2.x** — Video composition
- **OpenAI Whisper** — Subtitle transcription
- **Edge-TTS** / **NVIDIA NIM** — Voice generation
- **Pexels API** — Stock video search
- **Ollama** / **Google Gemini** — AI script generation

### Frontend
- **Next.js 16** — React framework
- **TypeScript** — Type safety
- **Tailwind CSS 4** — Styling
- **Framer Motion** — Animations
- **Lucide React** — Icons

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Ollama (for local AI) or Google Cloud credentials (for Gemini)

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Create .env file
cp .env.example .env  # if you have an example, otherwise create manually
```

Create `.env` in the `backend/` directory:

```env
# Model Provider: "ollama" or "vertex"
MODEL_PROVIDER=ollama

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Vertex AI settings (if using Gemini)
VERTEX_PROJECT_ID=your-project-id
VERTEX_LOCATION=us-central1
GEMINI_MODEL=gemini-2.0-flash

# NVIDIA NIM (for Magpie TTS)
NVIDIA_API_KEY=your-nvidia-api-key

# Pexels
PEXELS_API_KEY=your-pexels-api-key

# Pixabay
PIXABAY_API_KEY=your-pixabay-api-key

# Background music
MUSIC_ENABLED=true

# Frontend origin
FRONTEND_ORIGIN=http://localhost:3000
```

### Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Start Frontend

```bash
cd frontend
npm run dev
```

Open http://localhost:3000

## API Endpoints

### Projects
- `GET /projects` — List recent projects
- `POST /projects` — Create new project
- `GET /projects/{id}` — Get project details
- `DELETE /projects/{id}` — Delete project

### Script
- `POST /projects/{id}/script/generate` — Generate script with AI
- `PUT /projects/{id}/script` — Save script changes
- `POST /projects/{id}/script/approve` — Approve script

### Scenes
- `POST /projects/{id}/scenes/generate` — Generate scenes from script
- `PUT /projects/{id}/scenes/{scene_id}` — Update scene
- `POST /projects/{id}/scenes/approve` — Approve all scenes

### Clips
- `POST /projects/{id}/clips/fetch` — Search Pexels for clips
- `POST /projects/{id}/clips/{scene_id}/select/{clip_id}` — Select clip
- `POST /projects/{id}/clips/auto-select` — AI auto-select clips
- `POST /projects/{id}/clips/approve` — Approve clips and download

### Voiceover
- `POST /projects/{id}/voiceover/generate` — Generate voiceover
- `POST /projects/{id}/voiceover/approve` — Approve voiceover

### Render
- `POST /projects/{id}/render/start` — Start video rendering

### AI
- `POST /ai/optimize-idea` — Expand rough idea into detailed premise
- `POST /ai/optimize-keyword` — Refine stock video search keyword

## Supported Video Formats

- **Shorts** — 9:16 vertical (1080×1920), 45-60 seconds
- **Long Form** — 16:9 landscape (1920×1080), 8-12 minutes

## Supported Languages

- English
- Hindi (Devanagari script)

## License

MIT
