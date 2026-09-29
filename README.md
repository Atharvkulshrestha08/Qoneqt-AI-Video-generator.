# QoneqtReel Engine 🎬⚡

**An LLM-powered, self-looping video pipeline for the Qoneqt Global Feed.**  
Built for the Qoneqt x CTRL FREAK Hackathon.

## Overview
QoneqtReel Engine turns any topic, idea, or trend into a ready-to-publish 30-second vertical video (9:16, 720x1280, 30fps) with AI voiceover, dynamic background music, burned-in high-contrast captions, and an AI disclosure watermark.

It runs fully autonomously with a closed-loop quality critic and targeted retries.

---

## 5 Mandatory Guardrails
1. **Input Moderation:** Blocks hate, sexual content, violence, self-harm, illegal activities, and misinformation before generation.
2. **Script Moderation:** Inspects generated script for safety, brand logos, or risky claims.
3. **No Real People / Deepfakes:** Strict bans on real-person likenesses, names, or cloned voices.
4. **Copyright-Clean Assets:** 100% original synthesised ambient pads or CC0 assets, with AI-generated or free-licensed visuals.
5. **AI Disclosure & Fact Safety:** Persistent "AI-generated" watermark badge and mandatory caption disclaimers.

---

## Quickstart

### 1. Requirements
- Python 3.11+
- FFmpeg (automatically detected via system path or bundled fallback)

### 2. Setup
```bash
cp .env.example .env
# Edit .env and supply GEMINI_API_KEY (or GROQ_API_KEY)
pip install -r requirements.txt
```

### 3. Run Locally
```bash
# Start API & Web UI
uvicorn api:app --reload --port 7860
```
Visit `http://localhost:7860` to access the web UI.

### 4. Run Batch Mode CLI
```bash
python scripts/run_batch.py samples/topics.txt
```

---

## Project Structure
- `api.py`: FastAPI server for job management and download endpoints
- `pipeline.py`: Single job end-to-end orchestration
- `loop.py`: Inner critic loop & outer batch runner
- `llm.py`: Multi-provider LLM caller (Gemini with Groq fallback)
- `moderation.py`: Input and script safety guardrails
- `media.py`: Visuals generation (Pollinations -> Pexels -> Pillow), TTS (edge-tts -> gTTS), and music synthesis
- `compose.py`: FFmpeg vertical video assembly with Ken Burns, captions, ducking, and badges
- `prompts/`: System prompt templates for LLM tasks
- `samples/`: Test topics and adversarial evaluation sets
