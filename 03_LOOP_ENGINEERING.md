# Loop Engineering Document
**How the pipeline runs itself: generate, check, fix, repeat, export, with no human in the loop.**

Also contains **Section 9: everything the human (you) must provide to the AI agent.**

---

## 1. Core Idea
A single generation is fragile. A **loop** makes it reliable:

```
        +-------------------- feedback --------------------+
        v                                                  |
 INPUT -> MODERATE -> SCRIPT -> ASSETS -> COMPOSE -> CRITIC --+--> PASS -> EXPORT
                                                          |
                                                          +--> FAIL (attempts exhausted) -> FALLBACK VIDEO or FLAG
```

Two nested loops:
- **Inner loop (per job):** critic-driven targeted retries until quality passes or the attempt budget is spent.
- **Outer loop (per batch):** a worker pulls the next topic from the queue until it is empty. One bad job never stops the queue.

## 2. Job State Machine
```
queued -> moderating -> scripting -> script_check -> visuals -> audio -> composing -> critiquing
   -> passed  (exported)
   -> retrying (goes back to a specific stage)
   -> blocked (guardrail; terminal; reason logged)
   -> failed  (budget exhausted; best-effort output kept and flagged)
```
Persist state to `jobs/{job_id}.json` after **every** stage transition so a crash can resume.

## 3. Retry Policy
| Level | Rule |
|---|---|
| API call | Timeout 30s (LLM) / 60s (image). Retry up to 3x with exponential backoff (2s, 4s, 8s). |
| Provider | After 3 failures, switch to the next provider in the ladder (Section 5). |
| Stage | Each stage may be re-run at most 2 times. |
| Job | Max **3 full attempts** (`MAX_ATTEMPTS=3`). |
| Batch | Continue to next job on any failure. Never crash the worker. |

## 4. Critic Loop
After composing, run two checks.

**A. Programmatic checks (deterministic, run first)**
- Duration between 25 and 32 s
- Resolution is 720x1280, codec H.264/AAC (`ffprobe`)
- File size under 500 MB and above 200 KB
- Audio present and not silent (mean volume above -35 dB)
- Every scene has an image file with size above 10 KB
- Narration word count 65-80
- Caption text present on all scenes

**B. LLM critic (`prompts/critic.txt`)**
Scores hook, clarity, pacing, visual_match, safety, engagement.

**Pass rule:**
```
PASS if  overall >= 7.0  AND  safety >= 8  AND  hook >= 6  AND  all programmatic checks pass
```

**Targeted retry mapping (do not redo everything):**
| Critic verdict / failing check | Re-run from |
|---|---|
| RETRY_SCRIPT (hook, clarity, pacing low) | Script stage, passing `feedback` into the script prompt |
| RETRY_VISUALS (visual_match low, missing images) | Visuals stage only, using stock queries or simplified prompts |
| RETRY_AUDIO (silent, too long/short) | Audio stage; adjust speech rate or trim/pad |
| Duration out of range | Adjust scene durations and speech rate, then recompose |
| Safety fail | Script stage with strict safety feedback; if it fails again, **block** |
| Any other compose error | Recompose once, then fall back to the simple template |

## 5. Fallback Ladders (a scene must never be empty)
**Visuals:** Pollinations image -> Pexels photo (using `stock_query`) -> Pillow gradient card with the caption text.
**LLM:** Gemini -> Groq -> (last resort) a built-in template script filled with the topic.
**TTS:** edge-tts -> gTTS -> silent track with captions only (flagged `audio_degraded`).
**Music:** synthesised pad -> bundled CC0 track -> none.
**Compose:** full effects (zoompan, ducking) -> simple concat with captions -> static slideshow.

## 6. Guardrail Gates (hard stops inside the loop)
| Gate | Where | On fail |
|---|---|---|
| G1 Input moderation | Before scripting | Status `blocked`, no retry |
| G2 Script moderation | After scripting | Retry script once with fixes; if fail again, `blocked` |
| G3 No real people | Script + visual prompts scan | Strip names / rewrite prompt; if still present, retry |
| G4 Copyright-clean | Asset stage | Only allowed sources; refuse unknown sources |
| G5 AI disclosure + fact-safety | Compose + metadata | Badge always burned in; caption always ends with "AI-generated video."; sensitive topics get a disclaimer |

Blocked jobs are never retried by the outer loop.

## 7. Batch Runner (Outer Loop)
```
load topics (file or API list)
for each topic:
    create job -> run inner loop (max 3 attempts)
    record result (passed / failed / blocked), scores, timings
    sleep 2-5s between jobs (rate-limit friendly)
write batch_report.json + batch_report.md
```
**Batch report includes:** topic, status, attempts used, overall score, time taken, video path, block reason if any.
Use this report in the **demo video** and README to prove repeatability.

Optional scheduler (P1): run the batch every N minutes using a background thread (`BATCH_INTERVAL_MIN`), pulling new topics from `topics_queue.txt`.

## 8. Observability
- Per-job `logs[]` with timestamps and stage names.
- Console log format: `[job_id][stage][attempt] message`.
- UI shows stage progress bar, attempt count, scores, and fallback flags used.
- Save the critic feedback of each attempt (shows the loop "learning" in the demo).

## 8b. Loop Pseudocode
```python
def run_job(job):
    if not moderate_input(job.topic).allowed:
        return block(job)
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        job.attempts = attempt
        script = gen_script(job, feedback)
        if not moderate_script(script).passed:
            feedback = "Fix safety issues: ..."; continue
        assets = build_assets(script)          # fallback ladders inside
        video  = compose(script, assets)
        checks = programmatic_checks(video, script)
        review = critic(script, checks)
        job.scores = review.scores
        if passes(review, checks):
            return finish(job, video)
        feedback = review.feedback
        # targeted re-run based on review.verdict
    return finish_best_effort(job)             # flagged as 'failed', best video kept
```

---

## 9. WHAT YOU (THE HUMAN) MUST PROVIDE TO THE AI AGENT

Give the agent these items. Do this **first**; it unblocks everything.

### 9.1 Accounts and Keys
| # | Item | Where to get it (free) | Required? | Env var |
|---|---|---|---|---|
| 1 | **Gemini API key** | aistudio.google.com -> Get API key | **Yes** | `GEMINI_API_KEY` |
| 2 | **Groq API key** (LLM backup) | console.groq.com -> API Keys | Recommended | `GROQ_API_KEY` |
| 3 | **Pexels API key** (photo fallback) | pexels.com/api | Recommended | `PEXELS_API_KEY` |
| 4 | **GitHub account + empty public repo** | github.com | **Yes** | n/a |
| 5 | **Deployment account** (Hugging Face Spaces or Render) | huggingface.co / render.com | **Yes** | n/a |
| 6 | **Qoneqt accounts** for the team | qoneqt.com | **Yes** | n/a |

Pollinations, edge-tts, gTTS, FFmpeg need **no key**.

### 9.2 `.env` template (give to the agent; never commit real values)
```
LLM_PROVIDER=gemini            # gemini | groq
GEMINI_API_KEY=
GROQ_API_KEY=
PEXELS_API_KEY=
MAX_ATTEMPTS=3
TARGET_DURATION_SEC=30
VIDEO_WIDTH=720
VIDEO_HEIGHT=1280
FPS=30
TTS_VOICE=en-IN-NeerjaNeural   # edge-tts voice
PASS_OVERALL=7.0
PASS_SAFETY=8
BATCH_INTERVAL_MIN=0           # 0 = disabled
```

### 9.3 Decisions to tell the agent
- [ ] Preferred host: Hugging Face Spaces (Docker) **or** Render
- [ ] Voice style: female/male, Indian English accent (default: en-IN)
- [ ] Language: English only for tonight (Hindi is an optional extra)
- [ ] Brand look: colours/logo for the "AI-generated" badge (default: small pill, bottom-right)
- [ ] Team roles: who owns LLM / Media / Build+Deploy (see PRD Section 15)

### 9.4 Qoneqt-specific tasks (only humans can do these)
- [ ] Log in and upload **one test video** to check: does it land in **Global Feed or Qlips**? Is it cropped?
- [ ] Note the best network and hashtags to use (e.g., Viral, India, Food, News).
- [ ] After generation, **publish the final video manually** via Create, and copy the post link.
- [ ] Ask the Qoneqt team/organisers: submission form link, judging criteria, and whether a tag or hashtag is needed.

### 9.5 Files to hand the agent
1. `01_PRD.md`
2. `02_PROMPT_DOCUMENT.md`
3. `03_LOOP_ENGINEERING.md` (this file)
4. The problem statement text
5. Your Qoneqt screenshots (for style reference)

### 9.6 Hand-off message (paste this to the agent to start)
```
Read 01_PRD.md, 02_PROMPT_DOCUMENT.md (Part A is your instruction) and
03_LOOP_ENGINEERING.md. Deadline is tonight 11:59 PM. Start at Step 1 of the build
order. I will supply keys via .env. Stop after Step 6 so we can publish our first
video on Qoneqt, then continue. Ask me only if you are blocked on a secret or account.
```

---

## 10. Final Ship Checklist
- [ ] 1 video generated locally (Step 6)
- [ ] Video published on Qoneqt, link saved
- [ ] Public GitHub repo, no secrets
- [ ] Live URL tested from a different device or network
- [ ] Batch report from 5 topics (screenshot or file)
- [ ] Adversarial prompts blocked (screenshot for demo)
- [ ] Demo video recorded (input -> loop -> output -> Qoneqt post)
- [ ] Submission completed **before 11:30 PM** (leave buffer)
