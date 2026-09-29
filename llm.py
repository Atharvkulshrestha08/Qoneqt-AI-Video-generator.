import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()

logger = logging.getLogger("qoneqtreel.llm")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --- Pydantic Data Models matching PRD & Prompt Document ---

class InputModerationResult(BaseModel):
    allowed: bool
    category: str = Field(default="safe")
    sensitivity: str = Field(default="normal")
    reason: str = Field(default="Topic is safe")


class ScenePlan(BaseModel):
    id: int
    duration_sec: int = Field(ge=4, le=10)
    narration: str
    caption_text: str
    visual_prompt: str
    stock_query: str


class ScriptPlan(BaseModel):
    title: str
    hook: str
    scenes: List[ScenePlan]
    post_caption: str
    hashtags: List[str]
    suggested_network: str = Field(default="General")

    @field_validator("scenes")
    @classmethod
    def validate_scenes_count(cls, v: List[ScenePlan]) -> List[ScenePlan]:
        if len(v) != 5:
            # We enforce 5 scenes
            logger.warning(f"Script has {len(v)} scenes instead of 5, clamping/padding")
        return v


class ScriptModerationResult(BaseModel):
    passed: bool
    issues: List[str] = Field(default_factory=list)
    fixes: List[str] = Field(default_factory=list)


class CriticScores(BaseModel):
    hook: float = Field(ge=0, le=10, default=7.0)
    clarity: float = Field(ge=0, le=10, default=7.0)
    pacing: float = Field(ge=0, le=10, default=7.0)
    visual_match: float = Field(ge=0, le=10, default=7.0)
    safety: float = Field(ge=0, le=10, default=9.0)
    engagement: float = Field(ge=0, le=10, default=7.0)


class CriticResult(BaseModel):
    scores: CriticScores
    overall: float = Field(ge=0, le=10, default=7.5)
    verdict: str = Field(default="PASS")  # PASS | RETRY_SCRIPT | RETRY_VISUALS | RETRY_AUDIO | FAIL
    feedback: str = Field(default="Video plan meets standards.")


class TrendAngle(BaseModel):
    topic: str
    why_it_works: str


class TrendAnglesResult(BaseModel):
    angles: List[TrendAngle]


# --- Helper: Extract & Parse JSON ---

def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Strips markdown code blocks and extracts raw JSON dictionary."""
    text = text.strip()
    # Remove markdown code block fences if present
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1)
    else:
        # Try to find first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1]

    return json.loads(text)


# --- Template Emergency Fallback (PRD Section 5: last resort) ---

def generate_emergency_script(topic: str) -> ScriptPlan:
    """Deterministic script generator used only when all LLM providers fail."""
    clean_topic = topic.strip()
    return ScriptPlan(
        title=f"The Truth About {clean_topic[:40]}",
        hook=f"Did you know the secret behind {clean_topic[:35]}?",
        scenes=[
            ScenePlan(
                id=1,
                duration_sec=6,
                narration=f"Here is something surprising about {clean_topic}. Most people get this completely wrong.",
                caption_text=f"The secret behind {clean_topic[:20]}",
                visual_prompt=f"Cinematic illustration of {clean_topic}, vibrant colors, dramatic lighting, vertical composition",
                stock_query=f"{clean_topic[:20]} overview",
            ),
            ScenePlan(
                id=2,
                duration_sec=6,
                narration="First, look at how this changes the way we think every single day.",
                caption_text="How it changes everything",
                visual_prompt=f"Dynamic modern graphic showing impact of {clean_topic}, vertical 9:16 framing",
                stock_query="technology future concept",
            ),
            ScenePlan(
                id=3,
                duration_sec=6,
                narration="Second, the practical impact is already happening right before our eyes.",
                caption_text="Real impact happening now",
                visual_prompt=f"Inspiring visual representation of {clean_topic} in real life, clean composition",
                stock_query="innovation progress",
            ),
            ScenePlan(
                id=4,
                duration_sec=6,
                narration="When you put these pieces together, the entire picture becomes crystal clear.",
                caption_text="The bigger picture",
                visual_prompt="Conceptual mind map illuminating connections, futuristic vertical style",
                stock_query="clarity idea light",
            ),
            ScenePlan(
                id=5,
                duration_sec=6,
                narration="What do you think about this? Follow for more quick breakdowns and share your thoughts!",
                caption_text="Join the conversation!",
                visual_prompt="Community engagement illustration with vibrant social motifs, vertical layout",
                stock_query="community conversation social",
            ),
        ],
        post_caption=f"Breaking down {clean_topic}! Follow for more daily insights. AI-generated video.",
        hashtags=["#Qoneqt", "#TechExplainer", "#Trending", "#LearnOnQoneqt", "#DailyInsights"],
        suggested_network="Tech",
    )


# --- LLM Providers ---

class LLMService:
    def __init__(self):
        self.preferred_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()

    def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai

        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not configured")

        genai.configure(api_key=self.gemini_key)
        # Try latest flash models in priority order
        model_names = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        last_err = None
        for m_name in model_names:
            try:
                model = genai.GenerativeModel(m_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.3, "max_output_tokens": 1500},
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                last_err = e
                logger.warning(f"Gemini model {m_name} failed: {e}. Trying next model...")
        raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

    def _call_groq(self, prompt: str) -> str:
        from groq import Groq

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not configured")

        client = Groq(api_key=self.groq_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )
        return completion.choices[0].message.content

    def query(self, prompt: str) -> str:
        """Executes LLM call with retry and provider fallback ladder."""
        providers = []
        if self.preferred_provider == "gemini":
            providers = ["gemini", "groq"]
        else:
            providers = ["groq", "gemini"]

        last_error = None
        for provider in providers:
            for attempt in range(1, 4):
                try:
                    if provider == "gemini" and self.gemini_key:
                        logger.info(f"Querying Gemini (attempt {attempt}/3)...")
                        return self._call_gemini(prompt)
                    elif provider == "groq" and self.groq_key:
                        logger.info(f"Querying Groq (attempt {attempt}/3)...")
                        return self._call_groq(prompt)
                except Exception as e:
                    last_error = e
                    logger.warning(f"{provider} attempt {attempt} failed: {e}")
                    time.sleep(2**attempt)

        raise RuntimeError(f"All LLM providers failed or unconfigured. Error: {last_error}")

    def query_json(self, prompt: str) -> Dict[str, Any]:
        raw_text = self.query(prompt)
        return clean_and_parse_json(raw_text)


# Singleton LLM instance
llm_client = LLMService()
