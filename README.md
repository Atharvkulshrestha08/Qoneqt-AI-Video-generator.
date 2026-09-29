# QoneqtReel Engine 🎬

> **AI-powered autonomous video pipeline for the Qoneqt Global Feed.**  
> Built for the **Qoneqt × CTRL FREAK Hackathon** — and built to production standard.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production_Ready-brightgreen?style=for-the-badge)

</div>

---

## What Is This?

**QoneqtReel Engine** turns any topic — a question, a trend, a news headline, an idea — into a complete, publish-ready **30-second vertical video reel** with zero human involvement after the initial prompt.

Type `"Why do cats purr?"` and get back a `.mp4` with:
- ✅ An AI-written 5-scene script with a viral hook
- ✅ AI-generated cinematic images for every scene (Pollinations `flux` model)
- ✅ Natural-voice TTS narration (Microsoft Edge TTS, Indian accent)
- ✅ Animated Ken Burns effect on all visuals
- ✅ Auto-synced burned-in captions
- ✅ Original ambient background music (synthesized, copyright-clean)
- ✅ Safe-zone framing, progress bar, AI-disclosure badge
- ✅ Content safety guardrails at every stage

This is **not a wrapper around someone else's API**. Every stage — script generation, image sourcing, TTS, audio synthesis, video composition — is built ground-up with production-level fallback ladders, retry logic, and quality gates.

---

## Architecture

```
INPUT TOPIC
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  GUARDRAIL G1 — Input Moderation                            │
│  Keyword rules + LLM classifier → blocks harmful topics     │
└──────────────────────────┬──────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SCRIPT ENGINE (llm.py)                                     │
│  Gemini 3-flash → writes 5-scene JSON script plan           │
│  Fallback: Groq Llama 3.3 → Topic-aware template            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  GUARDRAIL G2+G3 — Script Safety Review                     │
│  Blocks hate, real-person likeness, unverifiable claims     │
└──────────────────────────┬──────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  MEDIA ENGINE (media.py)                  Per-scene:        │
│  Visual Ladder:                                             │
│    1. Pollinations AI (flux model)  → Best quality          │
│    2. Pexels Stock Photos           → If key available      │
│    3. Wikimedia Commons             → Free photography      │
│    4. Pillow Gradient Card          → Guaranteed fallback   │
│  Audio Ladder:                                              │
│    1. Edge-TTS (Neural, en-IN)      → Natural voice         │
│    2. gTTS                          → Simple fallback       │
│    3. Silent Audio                  → Never crashes         │
│  Music: NumPy ambient pad synthesizer (C minor, copyright-free) │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  COMPOSE ENGINE (compose.py + FFmpeg)                       │
│  Ken Burns pan/zoom → captions burn-in → audio ducking      │
│  Progress bar overlay → AI badge → final 720×1280 MP4       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CRITIC LOOP (loop.py)                                      │
│  Scores: hook / clarity / pacing / visual_match / safety    │
│  Overall ≥ 7.0 + Safety ≥ 8.0 → PASS                       │
│  Otherwise → targeted retry (script / visuals / audio)      │
│  Max 3 attempts before graceful fail                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                  📹 FINAL REEL .MP4
```

---

## Key Features

### 🤖 Multi-Provider LLM with Smart Fallbacks
- Primary: **Google Gemini** (gemini-3-flash-preview, gemini-flash-lite-latest)
- Fallback: **Groq** (Llama 3.3 70B Versatile)
- Last resort: **Topic-aware deterministic generator** (8 content categories, never generic)
- JSON output with `json-repair` for zero parse failures

### 🖼️ 4-Tier Visual Ladder
Every scene tries each tier in order — the video *always* gets an image, never crashes:
1. **Pollinations AI `flux`** — photorealistic AI generation
2. **Pexels** — professional stock photography (if API key provided)
3. **Wikimedia Commons** — high-resolution free photographs
4. **Pillow gradient card** — offline guaranteed fallback

### 🛡️ 3-Layer Content Safety
- **G1** — Input topic classification (LLM + keyword regex)
- **G2** — Script content review (hate, real-person, unverifiable claims)
- **G3** — Final quality gate via LLM critic

### ⚡ Autonomous Self-Improvement Loop
The critic scores every output. If it doesn't meet the quality bar, it retries with the specific feedback:
- Low hook score → `RETRY_SCRIPT` (rewrites with critic feedback)
- Audio issues → `RETRY_AUDIO`
- Visual mismatch → `RETRY_VISUALS`

### 🌐 REST API + Web Studio
- Full async REST API (FastAPI)
- Real-time job status polling
- Built-in web UI at `localhost:7860`
- Batch processing CLI (`python loop.py batch topics.txt`)

---

## Tech Stack

| Component | Technology |
|---|---|
| API Server | FastAPI + Uvicorn |
| AI / LLM | Google Gemini API (`google-genai` SDK) |
| LLM Fallback | Groq (Llama 3.3 70B) |
| Image Gen | Pollinations AI (flux model, no API key needed) |
| Stock Images | Pexels API, Wikimedia Commons |
| TTS | Microsoft Edge-TTS (Neural voices) |
| Music | NumPy synthesizer (original ambient pad) |
| Video Compose | FFmpeg via `imageio-ffmpeg` |
| Image Processing | Pillow |
| Data Validation | Pydantic v2 |
| JSON Repair | `json-repair` library |
| Containerization | Docker + docker-compose |
| Testing | pytest |

---

## Quickstart

### Prerequisites
- Python 3.11+
- A free [Google Gemini API key](https://aistudio.google.com/apikey)

### 1. Clone & Install

```bash
git clone https://github.com/Atharvkulshrestha08/Qoneqt-AI-Video-generator.git
cd Qoneqt-AI-Video-generator
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in your API key:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here   # Get free at aistudio.google.com/apikey
GROQ_API_KEY=                          # Optional: get free at console.groq.com
PEXELS_API_KEY=                        # Optional: higher quality stock photos
```

### 3. Run the Server

```bash
python -m uvicorn api:app --reload --port 7860
```

Open **http://localhost:7860** in your browser.

### 4. Generate Your First Video

Enter any topic in the web UI and hit **Generate**. Example topics:
- `"Why do black holes not let light escape?"`
- `"The real story behind Diwali"`
- `"How UPI changed India in 8 years"`
- `"Why sleep deprivation is worse than you think"`
- `"The hidden economy of street food in Mumbai"`

### 5. Or Use the CLI

```bash
# Single video
python pipeline.py "How GPS satellites know exactly where you are"

# Batch from file
python loop.py batch samples/topics.txt

# Batch with trend context
python loop.py batch samples/topics.txt --trend "viral India content"
```

---

## Docker Deployment

```bash
# Build
docker build -t qoneqtreel .

# Run
docker run -p 7860:7860 \
  -e GEMINI_API_KEY=your_key \
  qoneqtreel
```

---

## API Reference

### POST `/api/jobs`
Start a new video generation job.

```json
{
  "topic": "Why does the moon affect ocean tides?",
  "style": "energetic explainer",
  "trend": ""
}
```

**Response:**
```json
{
  "job_id": "job_1717000000_abc123",
  "status": "queued"
}
```

### GET `/api/jobs/{job_id}`
Poll job status and retrieve results.

```json
{
  "job_id": "job_1717000000_abc123",
  "status": "passed",
  "stage": "passed",
  "video_path": "jobs/job_1717000000_abc123/final_reel.mp4",
  "caption": "The hidden science of ocean tides...",
  "hashtags": ["#Science", "#OceanFacts"],
  "scores": {
    "hook": 8.5,
    "clarity": 9.0,
    "safety": 9.5,
    "overall": 8.8
  }
}
```

### GET `/api/jobs/{job_id}/video`
Stream the final `.mp4` file.

### GET `/api/health`
Health check endpoint.

---

## Output Specification

| Property | Value |
|---|---|
| Resolution | 720 × 1280 px (9:16 vertical) |
| Duration | 28–32 seconds |
| Frame Rate | 30 FPS |
| Audio | Stereo, 44.1kHz, narration + ambient pad |
| Format | H.264 MP4 |
| Narration | ~70 words, Microsoft Neural TTS |
| Captions | Burned-in, safe-zone compliant |
| Watermark | Subtle bottom-right badge |

---

## Project Structure

```
qoneqtreel/
├── api.py              # FastAPI REST endpoints + Web UI router
├── pipeline.py         # Core job orchestration (moderation → script → media → compose)
├── llm.py              # LLM providers, Pydantic schemas, fallback generator
├── media.py            # Visual ladder, TTS ladder, ambient music synthesizer
├── compose.py          # FFmpeg video assembly, Ken Burns, captions, ducking
├── loop.py             # Critic scoring, retry logic, batch runner
├── moderation.py       # Content safety guardrails (G1, G2, G3)
├── prompts/
│   ├── script_generator.txt   # Main LLM script prompt
│   ├── critic.txt             # Quality critic prompt
│   ├── moderate_input.txt     # Input safety prompt
│   ├── moderate_script.txt    # Script safety prompt
│   └── trend_expander.txt     # Trend angle expansion
├── samples/
│   ├── topics.txt             # Sample safe topics for testing
│   └── adversarial.txt        # Sample blocked topics for guardrail testing
├── static/
│   └── index.html             # Web Studio UI
├── tests/                     # pytest test suite
├── jobs/                      # Runtime job artifacts (gitignored)
├── Dockerfile                 # Production container with FFmpeg
├── requirements.txt
└── .env.example
```

---

## Content Safety

The engine operates a **zero-escape policy** on harmful content:

| Guardrail | Stage | What It Blocks |
|---|---|---|
| **G1** | Input | Hate speech, weapons, fake news, deepfakes, explicit content, self-harm |
| **G2** | Script | Real-person likenesses, brand names, unverifiable health/finance claims, copyrighted characters |
| **G3** | Quality | Low hook score, duration violations, missing audio, word count violations |

All guardrails run in parallel: LLM classifier + deterministic keyword regex. If the LLM is down, the regex still fires.

---

## Hackathon Context

This project was built for the **Qoneqt × CTRL FREAK AI Hackathon**.

**Challenge:** Build an AI system that can automatically generate short-form video content for the Qoneqt social platform's Global Feed.

**Our answer:** A fully autonomous, self-critiquing, self-correcting video pipeline that requires zero human intervention per video — while maintaining strict content safety standards suitable for a real social platform.

**What makes this different from a simple API wrapper:**
- Every component has a graceful degradation path — the system never crashes, it degrades to a lower-quality tier
- The critic loop is inspired by RLHF: the model reviews its own output and improves it
- The content safety system is dual-layer (LLM + regex) so guardrails survive API outages
- All media assets are either generated (AI images, synthesized music) or license-clear (Wikimedia, Edge-TTS)
- The ambient music is synthesized entirely from NumPy — not sampled from any existing track

---

## Roadmap

- [ ] Add Pexels video clip support for scene backgrounds
- [ ] Subtitle translation (Hindi, Tamil, Telugu)
- [ ] Direct Qoneqt API upload integration
- [ ] Thumbnail auto-generation
- [ ] Trend detection via Twitter/X API integration
- [ ] A/B testing two script variants per topic

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Atharv Kulshrestha**  
Built with 🔥 for the Qoneqt × CTRL FREAK Hackathon

---

<div align="center">

*This is not a demo. This is not a proof-of-concept.*  
*This is a production-grade AI video pipeline.*

**[Try it → http://localhost:7860](http://localhost:7860)**

</div>
