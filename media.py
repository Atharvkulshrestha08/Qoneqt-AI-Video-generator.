import asyncio
import logging
import math
import os
import urllib.parse
import wave
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

logger = logging.getLogger("qoneqtreel.media")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

TARGET_WIDTH = int(os.getenv("VIDEO_WIDTH", "720"))
TARGET_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1280"))
DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-IN-NeerjaNeural")


# --- 1. Visual Ladder ---

def generate_pillow_text_card(
    caption: str,
    output_path: Path,
    scene_id: int = 1,
    topic: str = "",
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
) -> Path:
    """
    Tier 3 Fallback: Creates an aesthetic, modern 9:16 vertical card with smooth gradient
    and centered high-contrast typography. Guaranteed to always succeed offline.
    """
    # Create smooth dark gradient background based on scene_id
    base_colors = [
        ((15, 23, 42), (88, 28, 135)),   # Navy to Deep Purple
        ((24, 24, 27), (14, 116, 144)),  # Charcoal to Teal
        ((19, 15, 38), (190, 24, 93)),   # Plum to Rose
        ((15, 23, 42), (30, 64, 175)),   # Slate to Deep Blue
        ((20, 20, 20), (217, 119, 6)),   # Dark to Warm Amber
    ]
    c1, c2 = base_colors[(scene_id - 1) % len(base_colors)]

    # Generate vertical gradient
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        factor = y / float(height)
        r = int(c1[0] * (1 - factor) + c2[0] * factor)
        g = int(c1[1] * (1 - factor) + c2[1] * factor)
        b = int(c1[2] * (1 - factor) + c2[2] * factor)
        arr[y, :] = [r, g, b]

    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)

    # Accent decorative box
    margin = 50
    draw.rounded_rectangle(
        [(margin, margin + 80), (width - margin, height - margin - 80)],
        radius=24,
        outline=(255, 255, 255, 60),
        width=2,
    )

    # Header pill
    tag_text = f"SCENE {scene_id} • INSIGHT"
    draw.text((width // 2, margin + 120), tag_text, fill=(200, 220, 255), anchor="mm")

    # Wrap caption text
    words = caption.split()
    lines = []
    curr = []
    for w in words:
        curr.append(w)
        if len(" ".join(curr)) > 22:
            curr.pop()
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    y_start = height // 2 - (len(lines) * 35)
    for i, line in enumerate(lines):
        # Shadow
        draw.text((width // 2 + 2, y_start + i * 70 + 2), line, fill=(0, 0, 0), anchor="mm")
        # Text
        draw.text((width // 2, y_start + i * 70), line, fill=(255, 255, 255), anchor="mm")

    img.save(str(output_path), "JPEG", quality=90)
    return output_path


def fetch_pollinations_image(prompt: str, output_path: Path, seed: int = 42) -> bool:
    """Tier 1: Fetches free AI image from Pollinations.ai using the Sana model."""
    try:
        clean_prompt = prompt.replace("?", "").replace("&", " and ").replace("\"", "").replace("'", "")[:220].strip()
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?model=sana&width={TARGET_WIDTH}&height={TARGET_HEIGHT}&nologo=true&seed={seed}"
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            # Resize and crop to exact vertical 720x1280
            with Image.open(output_path) as im:
                im = im.convert("RGB")
                im_resized = resize_and_crop_center(im, TARGET_WIDTH, TARGET_HEIGHT)
                im_resized.save(str(output_path), "JPEG", quality=92)
            logger.info(f"Pollinations Sana AI image generated: {output_path.name}")
            return True
        else:
            logger.warning(f"Pollinations response status {resp.status_code}, length {len(resp.content)}")
    except Exception as e:
        logger.warning(f"Pollinations fetch failed for '{prompt[:30]}...': {e}")
    return False


def resize_and_crop_center(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crops and resizes any image to fill vertical 9:16 frame without distortion."""
    src_w, src_h = img.size
    target_ratio = target_w / float(target_h)
    src_ratio = src_w / float(src_h)

    if src_ratio > target_ratio:
        # Source is wider: crop sides
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        # Source is taller: crop top/bottom
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))

    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


def fetch_wikimedia_image(query: str, output_path: Path) -> bool:
    """Tier 3: Fetches royalty-free photographic images from Wikimedia Commons."""
    try:
        clean_q = query.replace("overview", "").replace("concept", "").strip()
        search_terms = f"{clean_q} filetype:bitmap"
        api_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(search_terms)}&gsrnamespace=6&prop=imageinfo&iiprop=url&iiurlwidth=960&format=json&gsrlimit=5"
        r = requests.get(api_url, headers={"User-Agent": "QoneqtReel/1.0 (social-video-pipeline)"}, timeout=15)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            for pid, page in pages.items():
                infos = page.get("imageinfo", [])
                if infos:
                    # Prefer 960px thumbnail for speed & vertical quality, fallback to full url
                    img_url = infos[0].get("thumburl") or infos[0].get("url", "")
                    clean_ext = img_url.split("?")[0].lower()
                    if clean_ext.endswith((".jpg", ".jpeg", ".png", ".webp")):
                        img_resp = requests.get(img_url, headers={"User-Agent": "QoneqtReel/1.0"}, timeout=20)
                        if img_resp.status_code == 200 and len(img_resp.content) > 10000:
                            with open(output_path, "wb") as f:
                                f.write(img_resp.content)
                            with Image.open(output_path) as im:
                                im = im.convert("RGB")
                                fitted = resize_and_crop_center(im, TARGET_WIDTH, TARGET_HEIGHT)
                                fitted.save(str(output_path), "JPEG", quality=92)
                            logger.info(f"Wikimedia photographic asset retrieved: {output_path.name} (from '{clean_q}')")
                            return True
    except Exception as e:
        logger.warning(f"Wikimedia search failed for '{query}': {e}")
    return False


def fetch_pexels_image(query: str, output_path: Path) -> bool:
    """Tier 2: Fetches portrait photo from Pexels API if key is present."""
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not pexels_key:
        return False

    try:
        headers = {"Authorization": pexels_key}
        params = {"query": query, "orientation": "portrait", "per_page": 1}
        resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get("photos", [])
            if photos:
                img_url = photos[0]["src"]["large"]
                img_resp = requests.get(img_url, timeout=20)
                if img_resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(img_resp.content)
                    with Image.open(output_path) as im:
                        im = im.convert("RGB")
                        fitted = resize_and_crop_center(im, TARGET_WIDTH, TARGET_HEIGHT)
                        fitted.save(str(output_path), "JPEG", quality=92)
                    logger.info(f"Pexels stock image fetched: {output_path.name}")
                    return True
    except Exception as e:
        logger.warning(f"Pexels search failed for '{query}': {e}")
    return False


def get_scene_visual(
    visual_prompt: str,
    stock_query: str,
    caption_text: str,
    output_path: Path,
    scene_id: int,
    seed: int = 42,
) -> Tuple[Path, str]:
    """
    Fallback ladder for visual generation:
    1. Pollinations AI (Sana model)
    2. Pexels Stock Photography (if key available)
    3. Wikimedia Commons High-Res Photography
    4. Pillow Gradient Card (Guaranteed Offline)
    Returns (Path, source_tier)
    """
    # Tier 1: Pollinations Sana AI
    if fetch_pollinations_image(visual_prompt, output_path, seed=seed):
        return output_path, "pollinations_ai"

    # Tier 2: Pexels API
    if stock_query and fetch_pexels_image(stock_query, output_path):
        return output_path, "pexels"

    # Tier 3: Wikimedia Commons Real Photography
    search_q = stock_query or caption_text
    if search_q and fetch_wikimedia_image(search_q, output_path):
        return output_path, "wikimedia_photo"

    # Tier 4: Pillow Card (Guaranteed)
    logger.info(f"Falling back to Pillow gradient card for Scene {scene_id}")
    generate_pillow_text_card(caption_text, output_path, scene_id=scene_id)
    return output_path, "pillow_card"


# --- 2. TTS Ladder ---

async def _synthesize_edge_tts(text: str, output_path: Path, voice: str = DEFAULT_VOICE) -> bool:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
    return output_path.exists() and output_path.stat().st_size > 1000


def _synthesize_gtts(text: str, output_path: Path) -> bool:
    from gtts import gTTS

    tts = gTTS(text=text, lang="en", tld="co.in")
    tts.save(str(output_path))
    return output_path.exists() and output_path.stat().st_size > 1000


def _generate_silent_audio(output_path: Path, duration_sec: float = 6.0) -> bool:
    sample_rate = 24000
    n_samples = int(sample_rate * duration_sec)
    data = np.zeros(n_samples, dtype=np.int16)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())
    return True


def get_audio_duration(file_path: Path) -> float:
    """Calculates duration in seconds of audio file."""
    try:
        # Check if wave file
        with wave.open(str(file_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        pass

    # Use ffprobe via imageio_ffmpeg
    import subprocess
    import imageio_ffmpeg

    try:
        ffprobe_exe = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run(
            [ffprobe_exe, "-i", str(file_path)],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        import re

        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            hours, mins, secs = m.groups()
            return int(hours) * 3600 + int(mins) * 60 + float(secs)
    except Exception as e:
        logger.warning(f"Could not probe audio duration for {file_path}: {e}")

    return 6.0  # safe default fallback


def synthesize_narration(text: str, output_path: Path) -> Tuple[Path, str, float]:
    """
    TTS Ladder: edge-tts -> gTTS -> Silent Audio.
    Returns (Path, provider_used, duration_seconds)
    """
    # Tier 1: edge-tts
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(_synthesize_edge_tts(text, output_path))
        loop.close()
        if success:
            dur = get_audio_duration(output_path)
            return output_path, "edge_tts", dur
    except Exception as e:
        logger.warning(f"edge-tts failed: {e}. Falling back to gTTS...")

    # Tier 2: gTTS
    try:
        if _synthesize_gtts(text, output_path):
            dur = get_audio_duration(output_path)
            return output_path, "gtts", dur
    except Exception as e:
        logger.warning(f"gTTS failed: {e}. Falling back to silent audio...")

    # Tier 3: Silent Audio
    _generate_silent_audio(output_path, duration_sec=6.0)
    return output_path, "silent_degraded", 6.0


# --- 3. Music Synthesis (Original Ambient Pad via NumPy) ---

def synthesize_ambient_pad(output_path: Path, duration_sec: float = 32.0) -> Path:
    """
    Synthesizes an original, copyright-clean, relaxing ambient pad.
    Combines warm minor-9th chord fundamentals (e.g. C, G, D, Eb) with subtle LFO shimmer
    and smooth exponential fade-in and fade-out envelopes.
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)

    # Ambient chord frequencies (Hz) in C minor add9
    freqs = [130.81, 196.00, 293.66, 311.13, 392.00]  # C3, G3, D4, Eb4, G4

    pad = np.zeros(n_samples, dtype=np.float32)
    for i, f in enumerate(freqs):
        # Subtle slow chorus/detune
        lfo = 1.0 + 0.003 * np.sin(2 * np.pi * 0.2 * t + (i * 1.2))
        pad += (1.0 / len(freqs)) * np.sin(2 * np.pi * (f * lfo) * t)

    # Add gentle pink-noise texture for warm tape/lo-fi feel
    noise = np.random.normal(0, 0.015, n_samples).astype(np.float32)
    pad = pad + noise

    # Smooth attack (2 sec) and release (3 sec) envelope
    attack_samples = int(2.0 * sample_rate)
    release_samples = int(3.0 * sample_rate)

    env = np.ones(n_samples, dtype=np.float32)
    env[:attack_samples] = np.linspace(0, 1, attack_samples)
    env[-release_samples:] = np.linspace(1, 0, release_samples)

    pad = pad * env

    # Normalize volume to gentle background level (-18 dB RMS)
    max_val = np.max(np.abs(pad))
    if max_val > 0:
        pad = (pad / max_val) * 0.22

    int_data = (pad * 32767).astype(np.int16)

    # Stereo interleaving
    stereo_data = np.empty((n_samples * 2,), dtype=np.int16)
    stereo_data[0::2] = int_data
    stereo_data[1::2] = int_data

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo_data.tobytes())

    logger.info(f"Synthesized original ambient music: {output_path.name} ({duration_sec}s)")
    return output_path
