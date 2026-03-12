"""
renderer.py — Reel rendering logic for ReelForge pipeline.
Visual / timing logic ported from Viral-Reel-Script.py.
TTS: Chatterbox (edge-tts removed — not available on VM).
Called per-job so one failure never blocks others.
"""

import os
import re
import asyncio
import textwrap
import random
import json
import logging
import subprocess

from moviepy import (
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ColorClip,
    vfx,
    afx,
)

log = logging.getLogger("renderer")

# =========================================
# CONFIG  —  resolved from env so they work on the VM
# =========================================

STOCK_FOLDER   = os.environ.get("STOCK_FOLDER",   "stock")
MUSIC_FILE     = os.environ.get("MUSIC_FILE",     "music.mp3")
OUTPUT_FOLDER  = os.environ.get("OUTPUT_FOLDER",  "output")
FONT_PATH      = os.environ.get("FONT_PATH",      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_GEORGIA   = os.environ.get("FONT_GEORGIA",   "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf")
FONT_GEORGIA_I = os.environ.get("FONT_GEORGIA_I", "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf")

PAGE_NAME = os.environ.get("PAGE_NAME", "Silenor")

VIDEO_W       = 1080
VIDEO_H       = 1920
FONT_SIZE     = 88
SIDE_MARGIN   = 100
TEXT_WIDTH    = VIDEO_W - (SIDE_MARGIN * 2)
TEXT_BOTTOM_Y = VIDEO_H - 500

SILENCE_BUFFER = 0.5
OUTRO_HOLD     = 2.5
OUTRO_FADE_IN  = 0.7
OUTRO_FADE_OUT = 0.8

# Words that trigger yellow highlight for emphasis
POWER_WORDS = {
    "silence", "power", "powerful", "respect", "weak", "weakness",
    "discipline", "stop", "never", "always", "dominate", "control",
    "strength", "winner", "loser", "fear", "dangerous", "brutal",
    "truth", "lies", "fake", "real", "rich", "poor", "free", "trap",
    "mind", "focus", "king", "slave", "elite", "average", "mediocre",
    "obsessed", "obsession", "money", "success", "failure", "quit",
    "calm", "chaos", "war", "peace", "hunger", "satisfy",
}

MAX_RETRY = int(os.environ.get("RENDER_MAX_RETRY", "3"))


# =========================================
# CHATTERBOX TTS  —  model loaded once, reused for all reels
# =========================================

_tts_model = None


def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        import torch
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info(f"[tts] Loading Chatterbox model on {device}...")
        _tts_model = ChatterboxTTS.from_pretrained(device=device)
        log.info("[tts] Model loaded and cached in memory.")
    return _tts_model


async def _generate_voice(text: str, filename: str):
    import torchaudio as ta

    model        = _get_tts_model()
    exaggeration = float(os.environ.get("TTS_EXAGGERATION", "0.5"))
    cfg_weight   = float(os.environ.get("TTS_CFG_WEIGHT",   "0.3"))
    ref_clip     = os.environ.get("TTS_VOICE_REF", "").strip()

    kwargs = dict(exaggeration=exaggeration, cfg_weight=cfg_weight)
    if ref_clip and os.path.exists(ref_clip):
        kwargs["audio_prompt_path"] = ref_clip
        log.info(f"[tts] Cloning voice from: {ref_clip}")
    else:
        log.info("[tts] No voice ref — using default Chatterbox voice.")

    wav      = model.generate(text, **kwargs)
    wav_file = filename.replace(".mp3", ".wav")
    ta.save(wav_file, wav, model.sr)

    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_file,
         "-codec:a", "libmp3lame", "-qscale:a", "2", filename],
        check=True, capture_output=True,
    )

    try:
        os.remove(wav_file)
    except OSError:
        pass


# =========================================
# HELPER  —  make a TextClip with \n\n bottom padding
# =========================================

def make_text_clip(text, font, font_size, color, method="label",
                   stroke_color=None, stroke_width=0, size=None):
    """Matches the helper in Viral-Reel-Script exactly (padding + kwargs)."""
    padded = text + "\n\n"
    kwargs = dict(
        text=padded,
        font=font,
        font_size=font_size,
        color=color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        method=method,
    )
    if size is not None:
        kwargs["size"] = size
    return TextClip(**kwargs)


def contains_power_word(line: str) -> bool:
    words = re.findall(r"\w+", line.lower())
    return any(w in POWER_WORDS for w in words)


# =========================================
# OUTRO CLIPS  —  full explicit layout from Viral-Reel-Script
# =========================================

def build_outro_clips(voice_duration: float, total_duration: float) -> list:
    outro_start = voice_duration + SILENCE_BUFFER
    outro_dur   = total_duration - outro_start
    clips       = []

    # Dark vignette overlay
    vignette = (
        ColorClip((VIDEO_W, VIDEO_H), color=(0, 0, 0), duration=outro_dur)
        .with_opacity(0.70)
        .with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(vignette)

    ANCHOR       = VIDEO_H // 2
    LINE_W       = 380
    LINE_H       = 2
    LINE_ABOVE_Y = ANCHOR - 70
    NAME_Y       = ANCHOR - 50
    LINE_BELOW_Y = ANCHOR + 30
    TAGLINE_Y    = ANCHOR + 50

    # Horizontal rule above name
    line_above = (
        ColorClip((LINE_W, LINE_H), color=(255, 255, 255), duration=outro_dur)
        .with_position(("center", LINE_ABOVE_Y))
        .with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(line_above)

    # Page name  (spaced capitals)
    spaced_name = "  ".join(PAGE_NAME.upper())
    name_clip = (
        make_text_clip(spaced_name, FONT_GEORGIA, 74, "white", method="label")
        .with_position(("center", NAME_Y))
        .with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(name_clip)

    # Horizontal rule below name
    line_below = (
        ColorClip((LINE_W, LINE_H), color=(255, 255, 255), duration=outro_dur)
        .with_position(("center", LINE_BELOW_Y))
        .with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(line_below)

    # Tagline  (italic, slightly delayed fade-in)
    tagline_clip = (
        make_text_clip(
            "philosophy for the modern mind",
            FONT_GEORGIA_I, 32, (210, 210, 210),
            method="label",
        )
        .with_position(("center", TAGLINE_Y))
        .with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([
            vfx.FadeIn(OUTRO_FADE_IN + 0.35),
            vfx.FadeOut(OUTRO_FADE_OUT),
        ])
    )
    clips.append(tagline_clip)

    return clips


# =========================================
# SUBTITLE CLIPS
#   • Hook line  : bigger (118px), top-positioned, fast fade-in
#   • Power words: yellow, slightly larger
#   • Engage line: gold, slightly larger
#   • Normal     : white, standard size
# =========================================

def build_subtitle_clips(lines: list, voice_dur: float, sections: dict) -> list:
    subtitle_clips = []

    # Identify hook / engage anchor text
    hook_line   = None
    engage_line = None
    if sections:
        hook_line   = sections.get("hook",   "").strip().split("\n")[0].strip()
        engage_line = sections.get("engage", "").strip().split("\n")[0].strip()

    # Word-count-proportional durations (with scale correction)
    total_words    = sum(max(len(l.split()), 1) for l in lines)
    line_durations = [
        (max(len(l.split()), 1) / total_words) * voice_dur
        for l in lines
    ]
    scale          = voice_dur / sum(line_durations)
    line_durations = [d * scale for d in line_durations]

    current_time = 0.0

    for i, line in enumerate(lines):
        wrapped = textwrap.fill(line, width=24)

        is_hook   = bool(hook_line   and line.strip().startswith(hook_line[:20]))
        is_engage = bool(engage_line and line.strip().startswith(engage_line[:20]))
        has_power = contains_power_word(line)

        # ── Visual style per line type ──
        if is_hook:
            font_size    = 118
            color        = "white"
            fade_in_dur  = 0.12
            y_override   = 420          # high on screen — scroll-stop zone
        elif is_engage:
            font_size    = 96
            color        = (255, 215, 0)   # gold
            fade_in_dur  = 0.2
            y_override   = None
        elif has_power:
            font_size    = FONT_SIZE + 6
            color        = (255, 230, 50)  # yellow highlight
            fade_in_dur  = 0.3
            y_override   = None
        else:
            font_size    = FONT_SIZE
            color        = "white"
            fade_in_dur  = 0.4
            y_override   = None

        txt = make_text_clip(
            wrapped, FONT_PATH, font_size, color,
            method="caption",
            stroke_color="black",
            stroke_width=5 if not is_hook else 7,
            size=(TEXT_WIDTH, None),
        )

        y_pos = y_override if y_override is not None else max(TEXT_BOTTOM_Y - txt.h, 200)

        txt = (
            txt
            .with_position(("center", y_pos))
            .with_start(current_time)
            .with_duration(line_durations[i])
            .with_effects([vfx.FadeIn(fade_in_dur), vfx.FadeOut(0.3)])
        )
        subtitle_clips.append(txt)
        current_time += line_durations[i]

    return subtitle_clips


# =========================================
# BACKGROUND  —  slow zoom + attention-reset micro-pulses
# =========================================

def build_background(selected_image: str, total_dur: float) -> ImageClip:
    bg = (
        ImageClip(selected_image)
        .with_duration(total_dur)
        .resized(height=VIDEO_H)
    )
    bg = bg.cropped(x_center=bg.w / 2, width=VIDEO_W, height=VIDEO_H)

    def zoom_func(t):
        base   = 1 + 0.012 * t
        pulse  = 0.022 if (5.0  < t < 5.35)  else 0.0   # attention reset ~5 s
        pulse2 = 0.015 if (12.0 < t < 12.3)  else 0.0   # second interrupt mid-video
        return base + pulse + pulse2

    return bg.with_effects([vfx.Resize(zoom_func)])


# =========================================
# PUBLIC API  —  render_reel
# =========================================

def render_reel(reel_name: str, script: str, sections_json: str | None) -> str:
    """
    Renders a single reel and returns the output .mp4 path.
    Raises on failure — caller handles retry / status update.
    """
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    sections = json.loads(sections_json) if sections_json else None

    safe_name   = re.sub(r"[^\w]", "_", reel_name).lower()
    voice_file  = os.path.join(OUTPUT_FOLDER, f"_tmp_voice_{safe_name}.mp3")
    output_path = os.path.join(OUTPUT_FOLDER, f"{safe_name}.mp4")

    log.info(f"[render] Starting: {reel_name}")

    # ── 1. Voice ──────────────────────────────────────────
    log.info("[render] Generating voice (Chatterbox)...")
    asyncio.run(_generate_voice(script, voice_file))
    voice     = AudioFileClip(voice_file)
    voice_dur = voice.duration
    total_dur = voice_dur + SILENCE_BUFFER + OUTRO_HOLD
    log.info(f"[render] voice={voice_dur:.1f}s  total={total_dur:.1f}s")

    # ── 2. Background ────────────────────────────────────
    images = [
        f for f in os.listdir(STOCK_FOLDER)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ]
    if not images:
        raise FileNotFoundError(f"No images found in STOCK_FOLDER={STOCK_FOLDER!r}")

    selected_image = os.path.join(STOCK_FOLDER, random.choice(images))
    log.info(f"[render] Background image: {selected_image}")
    bg = build_background(selected_image, total_dur)

    # Dark overlay — slightly darkens background for subtitle contrast
    overlay = (
        ColorClip((VIDEO_W, VIDEO_H), color=(0, 0, 0), duration=total_dur)
        .with_opacity(0.52)
    )

    # ── 3. Subtitles ─────────────────────────────────────
    log.info("[render] Building subtitle clips...")
    lines          = [l.strip() for l in script.split("\n") if l.strip()]
    subtitle_clips = build_subtitle_clips(lines, voice_dur, sections)

    # ── 4. Outro ─────────────────────────────────────────
    log.info("[render] Building outro...")
    outro_clips = build_outro_clips(voice_dur, total_dur)

    # ── 5. Audio  (voice + music louder for emotional contrast) ──
    music = (
        AudioFileClip(MUSIC_FILE)
        .subclipped(0, total_dur)
        .with_volume_scaled(0.12)
        .with_effects([afx.AudioFadeOut(OUTRO_FADE_OUT + 0.2)])
    )
    voice_faded = voice.with_effects([afx.AudioFadeOut(0.5)])
    final_audio = CompositeAudioClip([voice_faded, music])

    # ── 6. Compose ───────────────────────────────────────
    all_clips = [bg, overlay] + subtitle_clips + outro_clips

    final = (
        CompositeVideoClip(all_clips, size=(VIDEO_W, VIDEO_H))
        .with_audio(final_audio)
        .with_duration(total_dur)
        .with_effects([vfx.FadeOut(OUTRO_FADE_OUT)])
    )

    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",          # faster for daily batch rendering
    )

    # ── 7. Cleanup ───────────────────────────────────────
    try:
        os.remove(voice_file)
    except OSError:
        pass

    log.info(f"[render] Saved: {output_path}")
    return output_path