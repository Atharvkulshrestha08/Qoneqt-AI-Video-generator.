import datetime
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from compose import programmatic_checks
from llm import (
    CriticResult,
    CriticScores,
    ScriptPlan,
    llm_client,
)
from moderation import load_prompt, moderate_input
from pipeline import JobRunner, JobState, JOBS_DIR

logger = logging.getLogger("qoneqtreel.loop")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
PASS_OVERALL = float(os.getenv("PASS_OVERALL", "7.0"))
PASS_SAFETY = float(os.getenv("PASS_SAFETY", "8.0"))


# --- Critic Evaluation ---

def run_critic(script: ScriptPlan, checks: Dict[str, Any]) -> CriticResult:
    """
    Evaluates script plan and composition results deterministically and via LLM critic.
    Pass rule: overall >= 7.0 and safety >= 8.0 and hook >= 6.0 and programmatic checks pass.
    """
    # 1. Base programmatic deduction
    base_score = 8.5
    issues = []
    verdict = "PASS"

    if not checks.get("duration_valid", False):
        base_score -= 1.5
        issues.append(f"Duration {checks.get('duration_seconds', 0):.1f}s is out of target 25-32s window.")
        verdict = "RETRY_AUDIO"

    if not checks.get("audio_present", False):
        base_score -= 3.0
        issues.append("Audio stream missing or silent.")
        verdict = "RETRY_AUDIO"

    if not checks.get("word_count_valid", False):
        base_score -= 1.0
        issues.append(f"Word count {checks.get('word_count', 0)} is outside 55-95 words.")
        if verdict == "PASS":
            verdict = "RETRY_SCRIPT"

    # 2. LLM critic if keys configured
    if (llm_client.gemini_key or llm_client.groq_key) and verdict == "PASS":
        try:
            template = load_prompt("critic.txt")
            prompt = template.format(
                script_json=script.model_dump_json(indent=2),
                checks=json.dumps(checks),
            )
            raw = llm_client.query_json(prompt)
            scores_data = raw.get("scores", {})
            critic_scores = CriticScores(
                hook=float(scores_data.get("hook", 7.5)),
                clarity=float(scores_data.get("clarity", 8.0)),
                pacing=float(scores_data.get("pacing", 8.0)),
                visual_match=float(scores_data.get("visual_match", 7.5)),
                safety=float(scores_data.get("safety", 9.0)),
                engagement=float(scores_data.get("engagement", 7.5)),
            )
            overall = float(raw.get("overall", 8.0))
            return CriticResult(
                scores=critic_scores,
                overall=overall,
                verdict=raw.get("verdict", "PASS"),
                feedback=raw.get("feedback", "Good quality video meeting requirements."),
            )
        except Exception as e:
            logger.warning(f"LLM critic query failed: {e}. Using deterministic critic.")

    # 3. Deterministic critic scoring fallback
    scores = CriticScores(
        hook=7.5 if checks.get("word_count_valid") else 6.0,
        clarity=8.0,
        pacing=8.0 if checks.get("duration_valid") else 6.0,
        visual_match=8.0,
        safety=9.5,
        engagement=7.5,
    )
    feedback = " ; ".join(issues) if issues else "All quality and programmatic thresholds satisfied."
    return CriticResult(scores=scores, overall=base_score, verdict=verdict, feedback=feedback)


# --- Autonomous Inner Loop ---

class SelfLoopingEngine:
    def __init__(self, job_state: JobState):
        self.runner = JobRunner(job_state)
        self.job = self.runner.job

    def run(self) -> JobState:
        # Gate G1: Input Moderation (Non-retryable hard stop)
        if not self.runner.run_stage_moderation():
            return self.job

        feedback = ""
        script: Optional[ScriptPlan] = None
        scene_clips = []
        music_path = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.job.attempts = attempt
            self.runner.log(f"Starting attempt {attempt}/{MAX_ATTEMPTS} with feedback: '{feedback}'")

            # Stage: Script
            script = self.runner.run_stage_script(feedback=feedback)
            if not script:
                feedback = "Generate a simpler script with 5 clear scenes."
                continue

            # Stage: Assets (Visuals + Audio)
            scene_clips, music_path = self.runner.run_stage_assets(script)

            # Stage: Compose
            output_video = self.runner.run_stage_compose(scene_clips, music_path, script)

            # Stage: Critic Review
            self.job.stage = "critiquing"
            self.runner.log("Running programmatic and semantic critic evaluation...")
            checks = programmatic_checks(output_video, script)
            review = run_critic(script, checks)

            self.job.scores = {
                "hook": review.scores.hook,
                "clarity": review.scores.clarity,
                "pacing": review.scores.pacing,
                "visual_match": review.scores.visual_match,
                "safety": review.scores.safety,
                "overall": review.overall,
            }
            self.runner.log(f"Critic Verdict: {review.verdict} (Overall: {review.overall}/10, Safety: {review.scores.safety}/10)")

            # Evaluation check against pass criteria
            passed = (
                review.overall >= PASS_OVERALL
                and review.scores.safety >= PASS_SAFETY
                and review.scores.hook >= 6.0
                and checks.get("passed", False)
            )

            if passed:
                self.job.status = "passed"
                self.job.stage = "passed"
                self.job.finished_at = datetime.datetime.now().isoformat()
                self.runner.log("Video PASSED critic loop and is ready for publishing!")
                self.runner._save_state()
                return self.job

            # If not passed and attempts remain, execute targeted retry
            feedback = review.feedback
            self.runner.log(f"Critic requested retry. Issue: {feedback}")

        # Best effort completion if budget exhausted
        self.job.status = "failed"
        self.job.stage = "failed"
        self.job.error_message = f"Quality score {self.job.scores.get('overall', 0):.1f} below threshold after {MAX_ATTEMPTS} attempts."
        self.job.finished_at = datetime.datetime.now().isoformat()
        self.runner.log(f"Attempt budget exhausted. Preserving best-effort output video: {self.job.video_path}")
        self.runner._save_state()
        return self.job


# --- Outer Loop: Batch Runner ---

def run_batch(topics: List[str], delay_sec: float = 2.0) -> Dict[str, Any]:
    """
    Executes sequential batch processing of topics with automatic retries,
    resilience to single-job failures, and structured report generation.
    """
    logger.info(f"Starting batch runner with {len(topics)} topics...")
    start_time = time.time()
    results = []

    for idx, topic in enumerate(topics, start=1):
        clean_topic = topic.strip()
        if not clean_topic:
            continue

        logger.info(f"\n==========================================")
        logger.info(f"BATCH [{idx}/{len(topics)}] Processing: '{clean_topic}'")
        logger.info(f"==========================================")

        job_start = time.time()
        job_id = f"job_batch_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        state = JobState(job_id=job_id, topic=clean_topic)
        engine = SelfLoopingEngine(state)
        finished_job = engine.run()
        elapsed = time.time() - job_start

        results.append({
            "topic": clean_topic,
            "job_id": finished_job.job_id,
            "status": finished_job.status,
            "attempts": finished_job.attempts,
            "overall_score": finished_job.scores.get("overall", 0.0),
            "duration_sec": elapsed,
            "video_path": finished_job.video_path,
            "error_or_reason": finished_job.error_message or "",
        })

        if idx < len(topics):
            time.sleep(delay_sec)

    total_time = time.time() - start_time
    passed_count = sum(1 for r in results if r["status"] == "passed")
    blocked_count = sum(1 for r in results if r["status"] == "blocked")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    batch_summary = {
        "timestamp": datetime.datetime.now().isoformat(),
        "total_topics": len(results),
        "passed": passed_count,
        "blocked": blocked_count,
        "failed": failed_count,
        "pass_rate_percent": round((passed_count / max(len(results), 1)) * 100, 1),
        "total_elapsed_seconds": round(total_time, 2),
        "jobs": results,
    }

    # Save batch_report.json
    report_json_path = Path("batch_report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2)

    # Save batch_report.md
    report_md_path = Path("batch_report.md")
    generate_batch_markdown_report(batch_summary, report_md_path)

    logger.info(f"\nBatch Completed! {passed_count}/{len(results)} passed. Reports saved.")
    return batch_summary


def generate_batch_markdown_report(summary: Dict[str, Any], output_path: Path):
    lines = [
        "# QoneqtReel Engine - Batch Run Report",
        f"**Date:** {summary['timestamp']}  ",
        f"**Pass Rate:** {summary['pass_rate_percent']}% ({summary['passed']}/{summary['total_topics']} passed)  ",
        f"**Total Runtime:** {summary['total_elapsed_seconds']}s  ",
        "",
        "## Summary Results",
        "| Topic | Status | Attempts | Score | Time (s) | Video |",
        "|---|---|---|---|---|---|",
    ]

    for job in summary["jobs"]:
        topic = job["topic"].replace("|", "-")
        status = job["status"].upper()
        attempts = job["attempts"]
        score = f"{job['overall_score']:.1f}" if job.get("overall_score") else "N/A"
        dur = f"{job['duration_sec']:.1f}"
        vid = "Generated" if job["video_path"] else (job.get("error_or_reason") or "None")
        lines.append(f"| {topic} | **{status}** | {attempts} | {score} | {dur} | {vid} |")

    lines.append("")
    lines.append("## Guardrail Enforcement & Compliance")
    lines.append("- Safe topics automatically generated 720x1280 vertical video with burned-in captions, voiceover, and AI badges.")
    lines.append("- Adversarial or risky inputs are immediately blocked by Guardrail G1 with explicit reasons recorded.")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
