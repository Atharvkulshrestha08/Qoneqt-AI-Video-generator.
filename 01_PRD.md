# PRD: QoneqtReel Engine
**An LLM-powered, self-looping video pipeline for the Qoneqt Global Feed**
Hackathon: Qoneqt x CTRL FREAK | Team size: 3 | Deadline: **30 Sep 2026, 11:59 PM**

---

## 1. Overview
QoneqtReel Engine turns a **topic / prompt / idea / trend** into a **ready-to-publish 30-second vertical video** for the Qoneqt Global Feed, with no human in the loop. It is a repeatable pipeline, not a one-off generation: feed it a queue of topics and it produces a queue of finished, quality-checked videos.

**Judging reality:** the organisers judge what is built and shipped, not the concept. Reliability and a real published video matter more than fancy features.

## 2. Problem
Qoneqt is a community-first social platform. Its Global Feed needs a steady supply of engaging video, and making it manually does not scale.

## 3. Goals and Non-Goals
**Goals**
- G1. One topic in, one publish-ready MP4 out, end to end.
- G2. Batch mode: N topics processed automatically with an automated quality loop (generate, critique, retry, export).
- G3. Zero-cost stack (free tiers only).
- G4. Safe by design: 5 guardrails, AI-disclosure label, copyright-free assets.
- G5. All four deliverables shipped before the deadline.

**Non-Goals**
- Auto-publishing to Qoneqt (no public API; upload is manual via Create).
- Photorealistic text-to-video models (paid, slow, unreliable). We assemble instead.
- User accounts, payments, or analytics dashboards.

## 4. Users
- **Primary:** Qoneqt content/community team wanting bulk feed content.
- **Secondary:** Hackathon judges running a live demo.

## 5. Output Specification
| Property | Value |
|---|---|
| Aspect ratio | 9:16 vertical (reel-style) |
| Resolution | 720x1280 |
| Duration | ~30 s (target 25-32 s) |
| Container / codec | MP4, H.264 video, AAC audio |
| Frame rate | 30 fps |
| Max size | 500 MB (expected 5-20 MB) |
| Audio | AI voiceover + soft royalty-free/generated background music (ducked under voice) |
| Captions | Burned-in, large, high contrast, inside safe zone |
| Disclosure | Visible "AI-generated" badge/watermark, plus text in post caption |

## 6. Pipeline (functional flow)
```
INPUT (topic/prompt/idea/trend)
  -> [G1] Input moderation
  -> LLM: hook + script + scene plan (strict JSON)
  -> [G2] Script moderation + fact-safety check
  -> Visual generation (per scene): image gen -> stock fallback -> text-card fallback
  -> TTS voiceover (per scene or full script)
  -> Music (generated/CC0)
  -> Compose (FFmpeg): motion, captions, voice+music mix, AI badge
  -> Critic (LLM + programmatic checks)
  -> PASS -> export MP4 + metadata (caption, hashtags)
  -> FAIL -> targeted retry (see Loop Engineering doc)
```

## 7. Functional Requirements
**P0 (must ship tonight)**
- FR1. Web UI + REST API: submit a topic, watch status, download MP4.
- FR2. LLM script generator returns strict JSON (hook, scenes, narration, captions, visual prompts, hashtags, post caption).
- FR3. Per-scene visuals with a fallback ladder, so a scene never fails empty.
- FR4. TTS voiceover (free, no key needed if possible).
- FR5. Background music that is copyright-free.
- FR6. FFmpeg composition to the output spec above, with captions and AI badge.
- FR7. Guardrails G1-G5 (Section 9) active on every run.
- FR8. Batch mode: submit a list of topics; process sequentially with automatic retries.
- FR9. Post-ready metadata (caption, hashtags, suggested Qoneqt network) shown next to the video.
- FR10. Live deployment reachable by a public URL.

**P1 (if time allows)**
- Critic loop with scoring and targeted regeneration.
- "Trend mode": paste a trend or let the LLM expand a trend keyword into 3 angles.
- Job history page and log viewer.

**P2 (only if everything else is done)**
- Auto-fetch trending topics; multiple voice/style presets; multilingual (Hindi/English).

## 8. Architecture and Stack (recommended, all free-tier)
| Layer | Choice | Fallback |
|---|---|---|
| Backend | Python 3.11, FastAPI | Flask |
| Frontend | Single HTML page (vanilla JS), served by FastAPI | Streamlit |
| LLM | Google Gemini API (free tier) | Groq (Llama 3.x free tier) |
| Images | Pollinations.ai (no key) | Pexels API photos, then generated text-card via Pillow |
| TTS | edge-tts (no key) | gTTS |
| Music | Synthesised ambient pad via FFmpeg/NumPy (100% original) | Pixabay/CC0 track committed to repo |
| Assembly | FFmpeg (zoompan/Ken Burns, drawtext or ASS captions, amix + sidechain ducking) | MoviePy |
| Queue | In-process worker thread + JSON job files (no Redis) | asyncio queue |
| Deploy | Docker on Hugging Face Spaces (or Render free tier) | Railway |

Note: FFmpeg must be installed in the Docker image.

## 9. Safety Guardrails (the 5)
1. **Input moderation:** block hateful, sexual, violent, self-harm, illegal or targeted-harassment prompts before any generation.
2. **Script moderation:** re-check LLM output for the same categories.
3. **No real people / deepfakes:** no cloned voices, no real-person likeness, no real named individuals in visual prompts.
4. **Copyright-clean assets:** original/generated music, generated or free-licence visuals, no brand logos or IP characters.
5. **AI disclosure + fact safety:** visible "AI-generated" badge in-video and in caption; for news/health/finance topics, avoid unverifiable claims and add a soft disclaimer.

Blocked jobs return a clear reason and are logged, never silently dropped.

## 10. API Surface
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/jobs` | Create a job `{topic, style?, trend?}` |
| POST | `/api/batch` | Create many jobs `{topics: []}` |
| GET | `/api/jobs/{id}` | Status, stage, attempts, scores, result URLs |
| GET | `/api/jobs` | List jobs |
| GET | `/api/jobs/{id}/video` | Download MP4 |
| GET | `/api/health` | Liveness check |

## 11. Data Model (JSON file per job)
```
job_id, topic, status (queued|running|passed|failed|blocked),
stage, attempts, script{...}, scenes[{img, audio, status}],
scores{hook, clarity, safety, visual_match, overall},
video_path, caption, hashtags, logs[], created_at, finished_at
```

## 12. Success Metrics
- Batch of 5 diverse topics: at least 4/5 produce a passing video without manual help.
- Average time per video under 4 minutes on free tier.
- 0 guardrail bypasses on a set of 5 adversarial test prompts.
- At least 1 video published on Qoneqt.

## 13. Deliverables Checklist (submission)
- [ ] Public GitHub repo with README (setup, architecture, guardrails, demo steps)
- [ ] Live deployment URL (working, not localhost)
- [ ] Demo video (screen recording: input -> pipeline -> output -> Qoneqt post)
- [ ] At least one generated video published on Qoneqt (Global Feed; test whether Qlips vs Global Feed)
- [ ] Qoneqt post link recorded

## 14. Risks and Mitigations
| Risk | Mitigation |
|---|---|
| Deadline is tonight | Build P0 first; publish a video early; polish later |
| Free image API slow/down | Fallback ladder ending in guaranteed text-card |
| Free-tier rate limits | Retry with backoff; switch LLM provider via env var |
| FFmpeg missing on host | Docker image with FFmpeg baked in; test locally first |
| Qoneqt has no API | Manual upload; documented as known limitation |
| Feed crops video oddly | Do one test upload early and adjust safe zones |
| Free host sleeps / slow start | Warm it up before the demo; keep a pre-rendered sample video |

## 15. Tonight's Plan (3 people)
| Person | Owns |
|---|---|
| A: Brain | LLM prompts, JSON schema, moderation, critic, loop logic |
| B: Media | Image fetching, TTS, music, fallbacks |
| C: Build/Ship | FFmpeg compose, FastAPI + UI, Docker, deploy, GitHub, README |

**Suggested timeline (work backwards from 11:59 PM):** end-to-end single video working, then publish on Qoneqt immediately, then deploy, then batch and loop, then README, then demo video, with 60 minutes of buffer for submission.

## 16. Open Questions
- Does a video appear in Global Feed or Qlips when posted via Create? (Test once.)
- Exact submission form/link and required fields.
- Judging weights (unknown; optimise for working end-to-end).
