# MakeVideo

An AI-powered video production pipeline that transforms raw ideas into polished video content. Built with a FastAPI backend and Next.js frontend, supporting both stock-video compositions and AI-generated image stories.

## Features

- **AI Script Generation** — Generate production-ready YouTube video scripts from a rough idea using local (Ollama) or cloud (Gemini, OpenAI, OpenRouter) models.
- **Scene Breakdown** — Automatically divide scripts into visually searchable stock-video scenes or detailed image generation prompts.
- **Hybrid Stock Media Integration** — Search and select clips from Pexels, Pixabay, Coverr, and Mixkit.
- **Image Story / Cartoon Mode** — Generate cinematic prompts for AI image generators and build videos from uploaded or downloaded images.
- **AI-Powered Auto-Selection** — Let AI choose the best clips for each scene based on descriptive keywords.
- **Professional Voiceovers** — Generate high-quality voiceovers using NVIDIA NIM (Magpie), Edge-TTS, or Riva.
- **Video Rendering** — Composite clips, audio, and subtitles into a finished MP4 using MoviePy 2.x.
- **Whisper Transcription** — Automatic, accurate subtitle generation via OpenAI Whisper.
- **Dynamic Configuration** — In-app settings to switch between AI providers and stock media sources.

## Architecture

```
MakeVideo/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py           # App entry point & middleware
│   │   ├── config.py         # Pydantic Settings & configuration
│   │   ├── database.py       # SQLAlchemy engine & session setup
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── storage.py        # File storage utilities
│   │   ├── routers/         # API route handlers
│   │   │   ├── projects.py   # Project CRUD
│   │   │   ├── scripts.py    # Script generation
│   │   │   ├── scenes.py     # Scene management
│   │   │   ├── image_scenes.py # Image-based scene & upload handling
│   │   │   ├── clips.py      # Stock media fetching (Pexels, Pixabay, etc.)
│   │   │   ├── voice.py      # Voiceover generation
│   │   │   ├── render.py     # Video rendering orchestration
│   │   │   ├── ai.py         # General AI utility endpoints
│   │   │   ├── categories.py # Project category management
│   │   │   ├── settings.py   # Global app settings management
│   │   │   └── logs.py       # Frontend log collection
│   │   └── services/
│   │       ├── ai.py         # AI service (Ollama, Gemini, OpenRouter, etc.)
│   │       ├── voice.py      # TTS integration (NVIDIA NIM, Edge-TTS)
│   │       ├── clips.py      # Multi-provider stock media integration
│   │       └── rendering.py  # MoviePy video composition logic
│   ├── storage/              # Generated media & logs
│   │   ├── logs/             # Structured JSON logs
│   │   └── project_{id}/     # Per-project assets
│   │       ├── clips/        # Downloaded stock video clips
│   │       ├── images/       # Uploaded/Generated scene images
│   │       ├── voiceovers/   # Generated audio files
│   │       ├── subtitles/    # SRT subtitle files
│   │       └── renders/      # Final video output
│   └── makevideo.db        # SQLite database
│
└── frontend/                 # Next.js frontend
    ├── app/
    │   ├── page.tsx          # Home page (project list)
    │   ├── projects/[id]/    # Project detail page (Workflow manager)
    │   └── settings/         # App configuration UI
    ├── components/
    │   ├── ui.tsx            # Reusable shadcn-like components
    │   ├── StepSidebar.tsx   # Workflow progress sidebar
    │   └── stages/           # Video production stages
    │       ├── ScriptStage.tsx
    │       ├── ScenesStage.tsx
    │       ├── ClipsStage.tsx
    │       ├── ImageScenesStage.tsx # For "Image Story" workflow
    │       ├── VoiceStage.tsx
    │       └── RenderStage.tsx
    └── lib/
        ├── api.ts            # Axios-based API client
        └── types.ts          # Shared TypeScript interfaces
```

## Workflow

The video production follows a 5-stage pipeline:

```
Script → Scenes → Media (Clips/Images) → Voiceover → Render
```

1. **Script** — Enter an idea; AI generates a complete video script.
2. **Scenes** — Script is broken into visual scenes with descriptions and keywords.
3. **Media** — Depending on format:
   - **Video**: Stock clips are searched/selected from Pexels, Pixabay, etc.
   - **Image Story**: Detailed prompts are generated for image creation; images are uploaded or fetched via URL.
4. **Voiceover** — Professional AI voiceover is generated for each scene.
5. **Render** — Final MP4 is composited with media, audio, and subtitles.

## Tech Stack

### Backend
- **FastAPI** — High-performance web framework.
- **SQLAlchemy 2.0** — Modern ORM for SQLite.
- **MoviePy 2.1+** — Advanced video composition.
- **OpenAI Whisper** — High-accuracy subtitle transcription.
- **NVIDIA NIM / Edge-TTS** — Professional voice generation.
- **Pydantic Settings** — Environment-driven configuration.
- **Python-JSON-Logger** — Structured logging for observability.

### Frontend
- **Next.js 15.1** — React framework with App Router.
- **TypeScript** — For robust, type-safe development.
- **Tailwind CSS 4.0** — Utility-first styling.
- **Framer Motion** — Fluid UI transitions and animations.
- **Lucide React** — Consistent iconography.

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Ollama (optional, for local AI)

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
```

#### Environment Variables (`backend/.env`)

```env
# LLM Provider: "ollama", "openai", "openrouter", "vertex", "nvidia"
LLM_PROVIDER=ollama

# Ollama Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# OpenRouter (Great for diverse models)
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# Stock Media Providers
# Options: "pexels", "pixabay", "coverr", "mixkit", "free", "hybrid"
CLIP_PROVIDER=hybrid
PEXELS_API_KEY=your-key
PIXABAY_API_KEY=your-key

# NVIDIA NIM (for Magpie TTS)
NVIDIA_API_KEY=your-nvidia-api-key
```

### Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

1. **Start Backend**:
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000)

## API Endpoints Summary

### Projects & Global
- `GET /projects` — List all projects
- `POST /projects` — Create project (Video or Image Story)
- `GET /categories` — List available project types
- `GET /settings` — Get current AI/Provider configuration
- `PUT /settings` — Update global settings

### Pipeline Stages
- **Script**: `POST .../script/generate`, `PUT .../script`, `POST .../script/approve`
- **Scenes**: `POST .../scenes/generate`, `PUT .../scenes/{id}`, `POST .../scenes/approve`
- **Media**:
  - **Stock Clips**: `POST .../clips/fetch`, `POST .../clips/auto-select`, `POST .../clips/{scene_id}/select/{clip_id}`, `POST .../clips/approve`
  - **Image Story**: `POST .../image-scenes/generate-prompts`, `POST .../image-scenes/{id}/upload-image`, `POST .../image-scenes/{id}/upload-image-by-url`, `POST .../image-scenes/approve-images`
- **Voiceover**: `POST .../voiceover/generate`, `POST .../voiceover/generate-multivoice`, `POST .../voiceover/approve`, `GET .../voices`
- **Render**: `POST .../render/start`, `POST .../render/start-image-story`, `GET .../render`

## Supported Video Formats

- **Shorts (9:16)** — Vertical (1080×1920), optimized for TikTok/Reels.
- **Standard (16:9)** — Landscape (1920×1080), for YouTube/TV.
- **Image Story** — Cinematic video built from static AI-generated or uploaded images.

## License

MIT
