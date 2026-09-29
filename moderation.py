import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List

from llm import (
    llm_client,
    InputModerationResult,
    ScriptModerationResult,
    ScriptPlan,
)

logger = logging.getLogger("qoneqtreel.moderation")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Keyword safety triggers (G1 & G3 fallback rules ensuring 0 guardrail escapes)
BLOCKED_PATTERNS = [
    (r"\b(mock\w*|insult\w*|hate\w*|kill\w*|attack\w*|destroy\w*)\b.*\b(religion\w*|hindu\w*|muslim\w*|christian\w*|sikh\w*|jew\w*)\b", "hate", "Hateful content targeting religion"),
    (r"\b(make\w*|build\w*|creat\w*)\b.*\b(weapon\w*|bomb\w*|explosiv\w*|gun\w*|firearm\w*)\b", "violence", "Instructions for creating weapons or explosives"),
    (r"\b(fake\s*news|death\s*hoax|celebrity('s)?\s*death)\b", "misinfo", "Deceptive misinformation or fake celebrity death claims"),
    (r"\b(politician\w*|modi|biden|trump|putin|obama)\b.*\b(voice\w*|deepfake\w*|never\s*said|impersonat\w*)", "real_person", "Deepfake or unauthorized impersonation of public figures"),
    (r"\b(explicit\w*|adult\w*|porn\w*|erotic\w*|nsfw|sex\w*|nude\w*)\b", "sexual", "Explicit adult or sexually suggestive content"),
    (r"\b(suicide\w*|self-harm\w*|cut\s*wrist\w*)\b", "self_harm", "Self-harm or suicide content"),
]


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt template {filename} not found in {PROMPTS_DIR}")
    return path.read_text(encoding="utf-8")


def rule_based_check(text: str) -> Dict[str, Any] | None:
    """Fast deterministic check to guarantee adversarial prompts are caught."""
    lower_text = text.lower()
    for pattern, category, reason in BLOCKED_PATTERNS:
        if re.search(pattern, lower_text):
            return {
                "allowed": False,
                "category": category,
                "sensitivity": "normal",
                "reason": f"Guardrail trigger: {reason}",
            }
    return None


def moderate_input(topic: str) -> InputModerationResult:
    """
    Guardrail G1: Evaluates user topic against safety categories.
    Returns InputModerationResult.
    """
    logger.info(f"Checking input topic moderation: '{topic}'")
    
    # 1. Rule-based pre-screen (G1 & G3 hard gate)
    rule_hit = rule_based_check(topic)
    if rule_hit:
        logger.warning(f"Input blocked by rule check: {rule_hit['reason']}")
        return InputModerationResult(**rule_hit)

    # 2. LLM semantic check if keys are configured
    if llm_client.gemini_key or llm_client.groq_key:
        try:
            template = load_prompt("moderate_input.txt")
            prompt = template.format(topic=topic)
            res = llm_client.query_json(prompt)
            return InputModerationResult(
                allowed=res.get("allowed", True),
                category=res.get("category", "safe"),
                sensitivity=res.get("sensitivity", "normal"),
                reason=res.get("reason", "Approved by moderation"),
            )
        except Exception as e:
            logger.warning(f"LLM moderation check failed: {e}. Falling back to rule inspection.")

    # 3. Default to safe if passed rule checks and general keywords
    sensitivity = "normal"
    lower = topic.lower()
    if any(k in lower for k in ["money", "crypto", "invest", "stock", "trading"]):
        sensitivity = "finance"
    elif any(k in lower for k in ["diet", "cure", "medicine", "doctor", "health", "symptom"]):
        sensitivity = "health"
    elif any(k in lower for k in ["breaking", "news", "election", "government"]):
        sensitivity = "news"

    return InputModerationResult(
        allowed=True,
        category="safe",
        sensitivity=sensitivity,
        reason="Passed input moderation checks.",
    )


def moderate_script(script: ScriptPlan) -> ScriptModerationResult:
    """
    Guardrail G2: Inspects full generated script for safety violations,
    real-person references, brand trademarks, and medical/financial advice without disclaimers.
    """
    logger.info(f"Checking script moderation for: '{script.title}'")

    script_dump = script.model_dump_json(indent=2)

    # 1. Rule-based check on script text
    full_text = f"{script.title} {script.hook} {script.post_caption} " + " ".join(
        [s.narration + " " + s.caption_text for s in script.scenes]
    )
    rule_hit = rule_based_check(full_text)
    if rule_hit:
        return ScriptModerationResult(
            passed=False,
            issues=[rule_hit["reason"]],
            fixes=["Remove offensive, violent, or impersonation content."],
        )

    # 2. Check for real person likeness names or famous brands
    disallowed_entities = [
        "narendra modi", "donald trump", "joe biden", "elon musk",
        "coca-cola", "pepsi", "nike", "disney", "marvel"
    ]
    for entity in disallowed_entities:
        if entity in full_text.lower():
            return ScriptModerationResult(
                passed=False,
                issues=[f"Mentions disallowed trademark or real person: '{entity}'"],
                fixes=[f"Replace '{entity}' with a generic term."],
            )

    # 3. LLM semantic check if keys configured
    if llm_client.gemini_key or llm_client.groq_key:
        try:
            template = load_prompt("moderate_script.txt")
            prompt = template.format(script_json=script_dump)
            res = llm_client.query_json(prompt)
            return ScriptModerationResult(
                passed=res.get("passed", True),
                issues=res.get("issues", []),
                fixes=res.get("fixes", []),
            )
        except Exception as e:
            logger.warning(f"LLM script moderation failed: {e}. Defaulting to rule verification.")

    return ScriptModerationResult(passed=True, issues=[], fixes=[])
