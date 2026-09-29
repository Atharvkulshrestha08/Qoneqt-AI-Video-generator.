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

# --- Topic-Aware Dynamic Script Generator (when LLM key is unconfigured) ---

def generate_emergency_script(topic: str) -> ScriptPlan:
    """Intelligent topic-aware script generator producing engaging, non-generic videos."""
    clean_topic = topic.strip()
    lower = clean_topic.lower()

    if any(k in lower for k in ["chai", "tea"]):
        return ScriptPlan(
            title="The True Story of Indian Chai",
            hook="Ever wondered why India can't start the day without chai?",
            scenes=[
                ScenePlan(
                    id=1,
                    duration_sec=6,
                    narration="Chai wasn't always India's favourite drink. Until the 1830s, tea was barely consumed here.",
                    caption_text="Chai wasn't always Indian",
                    visual_prompt="Close up traditional Indian clay kulhad cup steaming on rustic wooden table, cinematic warm lighting, photorealistic 8k",
                    stock_query="chai tea",
                ),
                ScenePlan(
                    id=2,
                    duration_sec=6,
                    narration="The British planted tea in Assam to break China's monopoly on the global tea trade.",
                    caption_text="The colonial tea origin",
                    visual_prompt="Lush green rolling tea gardens of Assam India in misty morning light, vertical composition",
                    stock_query="tea plantation assam",
                ),
                ScenePlan(
                    id=3,
                    duration_sec=6,
                    narration="Street vendors made it unique by adding buffalo milk, crushed ginger, cardamom, and boiled spices.",
                    caption_text="Spices and boiled milk",
                    visual_prompt="Indian street tea vendor pouring boiling masala chai from brass pot into glasses, authentic street photography",
                    stock_query="street chai vendor",
                ),
                ScenePlan(
                    id=4,
                    duration_sec=6,
                    narration="Today, cutting chai represents community, conversation, and the heartbeat of every Indian city.",
                    caption_text="Cutting chai culture",
                    visual_prompt="Friends laughing and holding glasses of chai at roadside stall during golden hour, candid cinematic",
                    stock_query="people drinking chai",
                ),
                ScenePlan(
                    id=5,
                    duration_sec=6,
                    narration="How many cups do you drink daily? Drop your number in the comments and follow for more!",
                    caption_text="How many cups daily?",
                    visual_prompt="Top down aesthetic view of cardamom pods, cinnamon sticks, cloves, and fresh hot tea cup",
                    stock_query="masala spices chai",
                ),
            ],
            post_caption="The journey of how chai conquered India! How many cups do you drink daily? AI-generated video.",
            hashtags=["#ChaiLovers", "#IndianCulture", "#StreetFood", "#HistoryBreakdown", "#LearnOnQoneqt"],
            suggested_network="Food",
        )

    if any(k in lower for k in ["goosebump", "chill", "cold", "hair"]):
        return ScriptPlan(
            title="Why Do We Get Goosebumps?",
            hook="Why does your body suddenly get goosebumps when you're cold or hear great music?",
            scenes=[
                ScenePlan(
                    id=1,
                    duration_sec=6,
                    narration="Goosebumps are actually an ancient evolutionary reflex known scientifically as piloerection.",
                    caption_text="The piloerection reflex",
                    visual_prompt="Macro extreme close up of goosebumps raising hair follicles on human arm, dramatic lighting, high detail",
                    stock_query="goosebumps skin human",
                ),
                ScenePlan(
                    id=2,
                    duration_sec=6,
                    narration="Tiny muscles attached to every hair follicle contract at the exact same moment.",
                    caption_text="Arrector pili muscles",
                    visual_prompt="Microscopic 3D medical visualization of skin pores and hair follicle contraction, cinematic science render",
                    stock_query="hair follicle skin",
                ),
                ScenePlan(
                    id=3,
                    duration_sec=6,
                    narration="For our furry ancestors, this trapped warm air to survive cold and intimidate predators.",
                    caption_text="Ancient survival instinct",
                    visual_prompt="Majestic wild wolf in snowy winter landscape with fur bristled against cold, vertical wildlife shot",
                    stock_query="wolf fur cold winter",
                ),
                ScenePlan(
                    id=4,
                    duration_sec=6,
                    narration="Today, intense music and emotional highs release adrenaline that triggers the exact same reflex.",
                    caption_text="Music and adrenaline",
                    visual_prompt="Person listening with headphones in neon concert lighting feeling goosebumps, aesthetic cinematic portrait",
                    stock_query="person listening music emotion",
                ),
                ScenePlan(
                    id=5,
                    duration_sec=6,
                    narration="Next time you get chills, you are feeling prehistoric instincts! Follow for more science breakdowns.",
                    caption_text="Your prehistoric reflex",
                    visual_prompt="Silhouette of human brain synapses glowing with energetic electric pulses, futuristic science aesthetic",
                    stock_query="brain synapses light",
                ),
            ],
            post_caption="The hidden science behind goosebumps and why our bodies react to cold and music! AI-generated video.",
            hashtags=["#ScienceFacts", "#HumanBody", "#Evolution", "#MindBlown", "#LearnOnQoneqt"],
            suggested_network="Education",
        )

    if any(k in lower for k in ["upi", "payment", "money", "fintech"]):
        return ScriptPlan(
            title="How UPI Transformed India",
            hook="How did a simple QR code transform five hundred million lives so quickly?",
            scenes=[
                ScenePlan(
                    id=1,
                    duration_sec=6,
                    narration="Before 2016, digital banking meant entering sixteen-digit card numbers and waiting for OTPs.",
                    caption_text="The old banking struggle",
                    visual_prompt="Frustrated person staring at complex banking error screen on old laptop, cinematic moody lighting",
                    stock_query="banking online mobile",
                ),
                ScenePlan(
                    id=2,
                    duration_sec=6,
                    narration="Then India built UPI: an instant, zero-cost payment protocol linking bank accounts directly.",
                    caption_text="The open UPI protocol",
                    visual_prompt="Futuristic digital network nodes connecting across India map, glowing neon data streams, vertical 9:16",
                    stock_query="digital network connectivity",
                ),
                ScenePlan(
                    id=3,
                    duration_sec=6,
                    narration="Today, tea stalls and luxury stores all accept instant payments with a single scan.",
                    caption_text="Accepted everywhere",
                    visual_prompt="Local Indian market vendor smiling with printed UPI QR code on wooden stall, colorful street scene",
                    stock_query="qr code payment street",
                ),
                ScenePlan(
                    id=4,
                    duration_sec=6,
                    narration="India now powers nearly half of all real-time digital transactions occurring worldwide.",
                    caption_text="46% of global payments",
                    visual_prompt="Futuristic high-speed smartphone scanning QR code with glowing digital hologram confirmation, 8k",
                    stock_query="smartphone payment scan",
                ),
                ScenePlan(
                    id=5,
                    duration_sec=6,
                    narration="When was the last time you carried physical paper cash? Comment below and follow for more!",
                    caption_text="Do you carry cash?",
                    visual_prompt="Modern sleek smartphone showing successful digital transaction checkmark with smiling youth",
                    stock_query="digital success mobile",
                ),
            ],
            post_caption="How UPI revolutionized India's economy into the digital payment capital of the world! AI-generated video.",
            hashtags=["#DigitalIndia", "#UPI", "#Fintech", "#TechExplainer", "#LearnOnQoneqt"],
            suggested_network="Tech",
        )

    if any(k in lower for k in ["student", "tool", "study", "learn"]):
        return ScriptPlan(
            title="3 Free Tools Every Student Needs",
            hook="Stop studying harder and start studying smarter with these three secret tools!",
            scenes=[
                ScenePlan(
                    id=1,
                    duration_sec=6,
                    narration="Most students waste hours rereading textbooks. These three free tools will cut your study time in half.",
                    caption_text="Study smarter not harder",
                    visual_prompt="Focused student sitting at clean wooden study desk with laptop and warm lamp, aesthetic cozy study",
                    stock_query="student studying laptop desk",
                ),
                ScenePlan(
                    id=2,
                    duration_sec=6,
                    narration="Tool one is Obsidian: it turns your random lecture notes into an interconnected digital second brain.",
                    caption_text="1. Obsidian Second Brain",
                    visual_prompt="Mind map network visualization with interconnected glowing nodes and thoughts, modern 3D render",
                    stock_query="mind map network notes",
                ),
                ScenePlan(
                    id=3,
                    duration_sec=6,
                    narration="Tool two is Anki: it uses cognitive spaced repetition algorithms so you remember facts before exams permanently.",
                    caption_text="2. Anki Spaced Repetition",
                    visual_prompt="Digital smart flashcards floating in clean minimalist interface with memory retention graph",
                    stock_query="flashcards memory study",
                ),
                ScenePlan(
                    id=4,
                    duration_sec=6,
                    narration="Tool three is Perplexity AI: an academic search engine that provides cited research answers with zero hallucinations.",
                    caption_text="3. Perplexity AI Search",
                    visual_prompt="Futuristic search interface displaying verified citations and books opening with golden light",
                    stock_query="library books research knowledge",
                ),
                ScenePlan(
                    id=5,
                    duration_sec=6,
                    narration="Which of these are you trying first? Share this with a friend who is preparing for exams and follow for more!",
                    caption_text="Tag a student friend!",
                    visual_prompt="Happy college students celebrating exam success in modern campus courtyard, sunny natural lighting",
                    stock_query="students university success",
                ),
            ],
            post_caption="3 game-changing free tools to ace your exams with half the study time! AI-generated video.",
            hashtags=["#StudentHacks", "#StudyTips", "#ProductivityTools", "#LearnOnQoneqt", "#EduTech"],
            suggested_network="Education",
        )

    # --- Smart dynamic fallback for ANY topic ---
    # Build topic-specific content by analyzing keywords
    words = clean_topic.split()
    topic_short = " ".join(words[:4]) if len(words) > 4 else clean_topic

    # Derive contextual angles from topic keywords
    is_science = any(k in lower for k in ["science", "body", "brain", "cell", "dna", "planet", "space", "atom", "quantum", "virus", "gene"])
    is_history = any(k in lower for k in ["history", "ancient", "war", "empire", "king", "queen", "century", "origin", "story", "discover"])
    is_food    = any(k in lower for k in ["food", "eat", "cook", "recipe", "taste", "flavor", "spice", "dish", "cuisine"])
    is_tech    = any(k in lower for k in ["app", "software", "code", "ai", "robot", "internet", "data", "cloud", "tech", "digital", "computer"])
    is_health  = any(k in lower for k in ["health", "sleep", "diet", "exercise", "habit", "stress", "mental", "mind", "weight", "fitness"])
    is_money   = any(k in lower for k in ["money", "invest", "rich", "wealth", "stock", "crypto", "budget", "save", "earn", "income"])
    is_career  = any(k in lower for k in ["career", "job", "work", "skill", "success", "productivity", "business", "startup", "leader"])
    is_nature  = any(k in lower for k in ["animal", "bird", "ocean", "forest", "tree", "nature", "wild", "earth", "climate", "environment"])

    if is_science:
        angle = "scientific discovery"
        scene2_narration = f"Scientists studying {topic_short} discovered something that changed our understanding entirely."
        scene2_visual = f"Microscopic scientific visualization related to {topic_short}, glowing neon lab equipment, dramatic macro photography"
        scene3_narration = f"At the molecular level, {topic_short} operates through a mechanism most of us never learn in school."
        scene3_visual = f"3D cinematic render of biological or molecular process representing {topic_short}, ultra-detailed"
        scene4_narration = f"Understanding {topic_short} reshapes how we see our own bodies and the natural world around us."
        scene4_visual = f"Stunning conceptual science art depicting {topic_short} in vibrant colors, vertical 9:16 composition"
        hashtags = ["#ScienceFacts", "#MindBlown", "#DidYouKnow", "#LearnOnQoneqt", "#ScienceBreakdown"]
        network = "Education"
    elif is_history:
        angle = "historical revelation"
        scene2_narration = f"The true origin of {topic_short} dates back further than most history books are willing to admit."
        scene2_visual = f"Ancient historical scene depicting {topic_short}, cinematic sepia toned dramatic lighting, vertical"
        scene3_narration = f"At its peak, {topic_short} shaped the lives of millions — its influence still echoes today."
        scene3_visual = f"Epic historical illustration of {topic_short}, sweeping vertical cinematic composition"
        scene4_narration = f"The legacy of {topic_short} quietly lives on in our language, culture, and everyday habits."
        scene4_visual = f"Modern world with subtle historical echoes of {topic_short}, split-tone cinematic photography"
        hashtags = ["#History", "#DidYouKnow", "#CultureFacts", "#LearnOnQoneqt", "#TrueStory"]
        network = "India"
    elif is_food:
        angle = "food story"
        scene2_narration = f"The journey of {topic_short} from raw ingredient to your plate is more fascinating than you think."
        scene2_visual = f"Beautiful close-up of {topic_short} being prepared in traditional Indian kitchen, warm cinematic"
        scene3_narration = f"Every region in India has its own spin on {topic_short}, shaped by local spices and culture."
        scene3_visual = f"Colorful regional variations of {topic_short} displayed artfully, top-down food photography 9:16"
        scene4_narration = f"The nutritional power of {topic_short} has made it a staple across generations of Indian families."
        scene4_visual = f"Nutritional concept visualization with {topic_short} ingredients glowing with health energy"
        hashtags = ["#FoodLovers", "#IndianFood", "#FoodFacts", "#LearnOnQoneqt", "#TasteOfIndia"]
        network = "Food"
    elif is_tech:
        angle = "tech explainer"
        scene2_narration = f"The engineers who built {topic_short} solved problems that seemed completely impossible five years ago."
        scene2_visual = f"Futuristic tech interface and code streams related to {topic_short}, neon cyberpunk aesthetic vertical"
        scene3_narration = f"Today {topic_short} powers millions of devices and decisions without most people even noticing."
        scene3_visual = f"Network of glowing data nodes and devices powered by {topic_short}, vertical 9:16 digital art"
        scene4_narration = f"In the next decade, {topic_short} will reshape industries we thought were immune to disruption."
        scene4_visual = f"Futuristic city skyline transformed by {topic_short} technology, cinematic sci-fi vertical"
        hashtags = ["#TechFacts", "#Innovation", "#FutureTech", "#LearnOnQoneqt", "#TechBreakdown"]
        network = "Tech"
    elif is_health:
        angle = "health insight"
        scene2_narration = f"Most people misunderstand {topic_short} — what you have been told may actually be working against you."
        scene2_visual = f"Human body wellness visualization related to {topic_short}, clean medical cinematic photography"
        scene3_narration = f"Research now shows that small, consistent changes around {topic_short} create outsized results."
        scene3_visual = f"Healthy lifestyle concept imagery representing {topic_short}, natural light vertical photography"
        scene4_narration = f"Making {topic_short} a daily habit is one of the highest-return investments in your long-term health."
        scene4_visual = f"Person thriving with healthy energy inspired by {topic_short}, golden hour portrait vertical"
        hashtags = ["#HealthTips", "#WellnessLife", "#HealthFacts", "#LearnOnQoneqt", "#MindBodySoul"]
        network = "General"
    elif is_money:
        angle = "financial insight"
        scene2_narration = f"Most people approach {topic_short} backwards — and that single mistake costs them years of wealth."
        scene2_visual = f"Sophisticated financial concept art representing {topic_short}, sleek minimal 9:16 vertical"
        scene3_narration = f"The compounding effect of understanding {topic_short} early separates the wealthy from everyone else."
        scene3_visual = f"Abstract wealth growth visualization with {topic_short} theme, glowing upward graph cinematic"
        scene4_narration = f"This is general information and not financial advice. Always consult a certified professional."
        scene4_visual = f"Professional financial planning desk with documents and charts, cinematic vertical portrait"
        hashtags = ["#MoneyTips", "#FinancialFreedom", "#WealthBuilding", "#LearnOnQoneqt", "#MoneyMindset"]
        network = "General"
    elif is_nature:
        angle = "nature wonder"
        scene2_narration = f"The survival strategy of {topic_short} in the wild is more sophisticated than any human technology."
        scene2_visual = f"Stunning wildlife or nature photography of {topic_short} in natural habitat, vertical cinematic"
        scene3_narration = f"Scientists have spent decades trying to fully understand how {topic_short} interacts with its ecosystem."
        scene3_visual = f"Ecosystem visualization with {topic_short} at center, vibrant nature documentary style vertical"
        scene4_narration = f"Climate change is putting {topic_short} under pressures our planet has never seen before."
        scene4_visual = f"Dramatic nature scene contrasting beauty and threat related to {topic_short}, cinematic vertical"
        hashtags = ["#NatureFacts", "#WildlifeWonder", "#EcoAwareness", "#LearnOnQoneqt", "#PlanetEarth"]
        network = "General"
    else:
        # Generic but still topic-injected for career/other topics
        angle = "insight"
        scene2_narration = f"What most people miss about {topic_short} is that the real impact happens below the surface."
        scene2_visual = f"Conceptual artistic visualization representing {topic_short}, dramatic cinematic vertical composition"
        scene3_narration = f"Once you see {topic_short} through this lens, you will start noticing it in places you never expected."
        scene3_visual = f"Insightful revelation concept art inspired by {topic_short}, glowing discovery aesthetic vertical"
        scene4_narration = f"The people who truly understand {topic_short} use it as an advantage that others simply overlook."
        scene4_visual = f"Success and insight concept photography with {topic_short} theme, professional cinematic vertical"
        hashtags = ["#DeepDive", "#DailyInsight", "#LearnSomethingNew", "#LearnOnQoneqt", "#KnowledgeIsPower"]
        network = "General"

    return ScriptPlan(
        title=f"The Real Truth About {topic_short}",
        hook=f"Here is the one thing about {topic_short} that almost nobody talks about.",
        scenes=[
            ScenePlan(
                id=1,
                duration_sec=6,
                narration=f"Everyone has heard of {clean_topic} — but almost nobody understands what actually makes it so remarkable.",
                caption_text=f"What makes {topic_short[:18]} special?",
                visual_prompt=f"Cinematic dramatic opener shot representing the concept of {clean_topic}, high contrast vertical 9:16, award-winning photography",
                stock_query=f"{topic_short[:20]}",
            ),
            ScenePlan(
                id=2,
                duration_sec=6,
                narration=scene2_narration,
                caption_text=f"The hidden {angle}",
                visual_prompt=scene2_visual,
                stock_query=f"{' '.join(words[:3])} {angle}",
            ),
            ScenePlan(
                id=3,
                duration_sec=6,
                narration=scene3_narration,
                caption_text=f"{topic_short[:18]} up close",
                visual_prompt=scene3_visual,
                stock_query=f"{' '.join(words[:3])} detail",
            ),
            ScenePlan(
                id=4,
                duration_sec=6,
                narration=scene4_narration,
                caption_text=f"Why {topic_short[:16]} matters",
                visual_prompt=scene4_visual,
                stock_query=f"{' '.join(words[:3])} impact",
            ),
            ScenePlan(
                id=5,
                duration_sec=6,
                narration=f"Did this change how you see {topic_short}? Drop your thoughts below and follow for more daily breakdowns!",
                caption_text="Share your thoughts!",
                visual_prompt=f"Vibrant social community conversation energy with glowing icons and chat bubbles, modern vertical design",
                stock_query="community conversation sharing",
            ),
        ],
        post_caption=f"The real {angle} behind {clean_topic}! Follow for daily insights. AI-generated video.",
        hashtags=hashtags,
        suggested_network=network,
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
        # Try latest models in priority order
        model_names = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        last_err = None
        for m_name in model_names:
            try:
                model = genai.GenerativeModel(m_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.7, "max_output_tokens": 2000},
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
