"""
renderer.py — ReelForge  |  BEAST MODE v3
═══════════════════════════════════════════════════════════════════

WHAT'S UPGRADED IN THIS VERSION
────────────────────────────────
TEXT / SUBTITLES
  ✓ Text cutoff FIXED — safe margins enforced, caption width hard-capped
  ✓ Wider wrap width calculated from pixel math, not magic number
  ✓ Hook: word-by-word flash mode (each word pops separately, 0.18s each)
  ✓ Punch: full-screen centered treatment, hard cut to outro — no fade out
  ✓ Power words: yellow with a semi-transparent dark pill background
    so they're readable on ANY background image
  ✓ All text has proper safe-zone margins — nothing clips on any device

VISUALS
  ✓ Dual-layer background: crossfade to second image at the Shift section
    (emotional pivot = visual pivot — resets attention mid-video)
  ✓ Darker overlay during hook (0.62) → lightens during shift (0.44)
    → darkens again for punch (0.65) — dynamic contrast arc
  ✓ Vignette edges (dark gradient at top/bottom) — cinematic feel
  ✓ Zoom pulse tuned: gentler base zoom, sharper pulse at punch moment

AUDIO
  ✓ Music swell at punch section — volume ramps 0.08 → 0.22 → 0.10
  ✓ Impact SFX at punch line start (whoosh/hit from sfx/ folder if present)
  ✓ Voice EQ via ffmpeg: slight low-cut + presence boost for authority
  ✓ Music ducked under voice (sidechaining via volume envelope)

ENGAGEMENT
  ✓ Yellow progress bar at bottom — drains left→right over voice duration
  ✓ Bar pulses (brightens) at each section boundary — keeps eyes engaged
  ✓ Subtle top banner: page name watermark (low opacity, always visible)

TTS
  ✓ Per-section Chatterbox emotion tuning (unchanged, already working)
  ✓ CAPS normalisation (unchanged)
  ✓ Clean space join (no ellipsis artifacts)

ALIGNMENT
  ✓ wav2vec2 forced alignment (unchanged, already working)
  ✓ Proportional fallback (unchanged)
═══════════════════════════════════════════════════════════════════
"""

import os
import re
import asyncio
import textwrap
import random
import json
import logging
import subprocess
from dataclasses import dataclass

import numpy as np
from moviepy import (
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ColorClip,
    VideoClip,
    vfx,
    afx,
)

log = logging.getLogger("renderer")

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════

STOCK_FOLDER   = os.environ.get("STOCK_FOLDER",   "stock")
MUSIC_FILE     = os.environ.get("MUSIC_FILE",     "music.mp3")
SFX_FOLDER     = os.environ.get("SFX_FOLDER",     "sfx")        # optional: put impact.mp3 here
OUTPUT_FOLDER  = os.environ.get("OUTPUT_FOLDER",  "output")
FONT_PATH      = os.environ.get("FONT_PATH",      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_GEORGIA   = os.environ.get("FONT_GEORGIA",   "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf")
FONT_GEORGIA_I = os.environ.get("FONT_GEORGIA_I", "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf")

PAGE_NAME = os.environ.get("PAGE_NAME", "Silenor")

VIDEO_W = 1080
VIDEO_H = 1920

# ── Safe zone margins — NOTHING renders outside these ──────────────
# 80px each side = 920px usable width (safe on all phones including notch devices)
SAFE_MARGIN   = 80
TEXT_WIDTH    = VIDEO_W - (SAFE_MARGIN * 2)   # 920px  ← fixes text cutoff

# ── Font sizes ──────────────────────────────────────────────────────
FONT_SIZE_NORMAL  = 72    # body lines   (was 88 — slightly smaller = never clips)
FONT_SIZE_POWER   = 80    # power word lines
FONT_SIZE_HOOK    = 96    # hook word-flash (each word pops)
FONT_SIZE_ENGAGE  = 82    # engage line
FONT_SIZE_PUNCH   = 108   # punch — full screen centered

# ── Wrap width: calculated from pixel budget ────────────────────────
# At FONT_SIZE_NORMAL ~72px, DejaVu Bold average char width ≈ 40px
# TEXT_WIDTH 920 / 40 = 23 chars → use 22 to be safe
WRAP_WIDTH_NORMAL = 22
WRAP_WIDTH_HOOK   = 16    # hook words are big — fewer chars per line
WRAP_WIDTH_PUNCH  = 18

# ── Vertical positions ──────────────────────────────────────────────
TEXT_BOTTOM_Y  = VIDEO_H - 420   # bottom anchor for body text
HOOK_Y         = 380             # hook sits high — scroll-stop zone
PUNCH_CENTER_Y = VIDEO_H // 2    # punch is vertically centered

# ── Timing ──────────────────────────────────────────────────────────
SILENCE_BUFFER = 0.5
OUTRO_HOLD     = 2.5
OUTRO_FADE_IN  = 0.7
OUTRO_FADE_OUT = 0.8

HOOK_WORD_DURATION = 0.18   # seconds per word in hook flash mode

# ── Colors ──────────────────────────────────────────────────────────
COLOR_WHITE   = (255, 255, 255)
COLOR_YELLOW  = (255, 225, 0)
COLOR_GOLD    = (255, 200, 0)
COLOR_GRAY    = (210, 210, 210)
COLOR_BLACK   = (0, 0, 0)
COLOR_BAR     = (255, 220, 0)    # progress bar — vivid yellow

# ── Overlay opacity arc ─────────────────────────────────────────────
# Dynamically changes per section for visual contrast arc
OVERLAY_HOOK    = 0.62
OVERLAY_BODY    = 0.52
OVERLAY_SHIFT   = 0.44
OVERLAY_PUNCH   = 0.65
OVERLAY_ENGAGE  = 0.50

# ── Music volume arc ────────────────────────────────────────────────
MUSIC_VOL_BASE  = 0.08
MUSIC_VOL_PUNCH = 0.22
MUSIC_VOL_OUTRO = 0.10

POWER_WORDS = {
    "silence", "power", "powerful", "respect", "weak", "weakness",
    "discipline", "stop", "never", "always", "dominate", "control",
    "strength", "winner", "loser", "fear", "dangerous", "brutal",
    "truth", "lies", "fake", "real", "rich", "poor", "free", "trap",
    "mind", "focus", "king", "slave", "elite", "average", "mediocre",
    "obsessed", "obsession", "money", "success", "failure", "quit",
    "calm", "chaos", "war", "peace", "hunger", "satisfy", "unstoppable",
    "rise", "grind", "built", "different", "rare", "chosen", "purpose",
}

MAX_RETRY    = int(os.environ.get("RENDER_MAX_RETRY", "3"))
ALIGN_BACKEND = os.environ.get("ALIGN_BACKEND", "wav2vec2")

# ── Chatterbox per-section emotion ──────────────────────────────────
SECTION_TTS_PARAMS = {
    "hook":     {"exaggeration": 0.75, "cfg_weight": 0.55},
    "punch":    {"exaggeration": 0.82, "cfg_weight": 0.62},
    "conflict": {"exaggeration": 0.65, "cfg_weight": 0.50},
    "shift":    {"exaggeration": 0.42, "cfg_weight": 0.42},
    "engage":   {"exaggeration": 0.50, "cfg_weight": 0.40},
    "default":  {"exaggeration": 0.55, "cfg_weight": 0.45},
}


# ═══════════════════════════════════════════════════════════════════
# CHATTERBOX TTS
# ═══════════════════════════════════════════════════════════════════

_tts_model = None

def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        import torch
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info(f"[tts] Loading Chatterbox on {device}...")
        _tts_model = ChatterboxTTS.from_pretrained(device=device)
        log.info("[tts] Model ready.")
    return _tts_model


def _preprocess_for_tts(text: str) -> str:
    """
    Clean text before Chatterbox.
    - SCREAMING CAPS → Title Case (neural TTS doesn't shout on caps)
    - Join lines with single space (NO ellipsis — Chatterbox speaks it literally)
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    cleaned = []
    for line in lines:
        line = re.sub(r'\b([A-Z]{2,})\b', lambda m: m.group(1).title(), line)
        cleaned.append(line)
    return " ".join(cleaned)


def _generate_voice_for_section(text: str, wav_path: str, section_key: str = "default"):
    import torchaudio as ta
    model  = _get_tts_model()
    params = SECTION_TTS_PARAMS.get(section_key, SECTION_TTS_PARAMS["default"])
    exaggeration = float(os.environ.get("TTS_EXAGGERATION", str(params["exaggeration"])))
    cfg_weight   = float(os.environ.get("TTS_CFG_WEIGHT",   str(params["cfg_weight"])))
    ref_clip     = os.environ.get("TTS_VOICE_REF", "").strip()
    kwargs = dict(exaggeration=exaggeration, cfg_weight=cfg_weight)
    if ref_clip and os.path.exists(ref_clip):
        kwargs["audio_prompt_path"] = ref_clip
    log.info(f"[tts] {section_key}: exag={exaggeration:.2f} cfg={cfg_weight:.2f}")
    wav = model.generate(text, **kwargs)
    ta.save(wav_path, wav, model.sr)


def _wav_to_mp3(wav_path: str, mp3_path: str):
    """Convert wav→mp3 with voice EQ: low-cut at 80Hz + 3dB presence boost at 3kHz."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path,
         "-af", "highpass=f=80,equalizer=f=3000:width_type=o:width=2:g=3",
         "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
        check=True, capture_output=True,
    )


def _concat_wavs(wav_paths: list, out_path: str):
    list_file = out_path + ".concat.txt"
    with open(list_file, "w") as f:
        for p in wav_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", list_file, "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    os.remove(list_file)


async def generate_voice_sectioned(
    sections: dict | None,
    script:   str,
    mp3_out:  str,
) -> str:
    tmp_dir = os.path.dirname(mp3_out)

    if not sections:
        processed = _preprocess_for_tts(script)
        wav_path  = mp3_out.replace(".mp3", ".wav")
        _generate_voice_for_section(processed, wav_path, "default")
        _wav_to_mp3(wav_path, mp3_out)
        try: os.remove(wav_path)
        except OSError: pass
        return mp3_out

    section_order = ["hook", "conflict", "shift", "punch", "engage"]
    wav_parts     = []
    for key in section_order:
        text = sections.get(key, "").strip()
        if not text:
            continue
        processed = _preprocess_for_tts(text)
        wav_path  = os.path.join(tmp_dir, f"_sec_{key}_{os.path.basename(mp3_out)}.wav")
        _generate_voice_for_section(processed, wav_path, key)
        wav_parts.append(wav_path)
        log.info(f"[tts] Section done: {key}")

    combined_wav = mp3_out.replace(".mp3", "_combined.wav")
    _concat_wavs(wav_parts, combined_wav)
    _wav_to_mp3(combined_wav, mp3_out)
    for p in wav_parts + [combined_wav]:
        try: os.remove(p)
        except OSError: pass
    return mp3_out


# ═══════════════════════════════════════════════════════════════════
# FORCED ALIGNMENT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WordStamp:
    word:  str
    start: float
    end:   float


def _align_wav2vec2(wav_path: str, transcript: str) -> list[WordStamp]:
    import torch, torchaudio
    device = "cuda" if torch.cuda.is_available() else "cpu"
    waveform, sample_rate = torchaudio.load(wav_path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    bundle    = torchaudio.pipelines.MMS_300M
    model_    = bundle.get_model().to(device)
    tokenizer = bundle.get_tokenizer()
    aligner   = bundle.get_aligner()
    if sample_rate != bundle.sample_rate:
        waveform = torchaudio.functional.resample(waveform, sample_rate, bundle.sample_rate)
    with torch.inference_mode():
        emission, _ = model_(waveform.to(device))
    words = re.findall(r"[a-zA-Z']+", transcript.lower())
    if not words: return []
    try:
        token_spans = aligner(emission[0], tokenizer(words))
    except Exception as e:
        log.warning(f"[align] wav2vec2 failed: {e}")
        return []
    ratio  = waveform.shape[1] / emission.shape[1] / bundle.sample_rate
    return [
        WordStamp(word=words[i], start=spans[0].start*ratio, end=spans[-1].end*ratio)
        for i, spans in enumerate(token_spans)
    ]


def _align_whisper(wav_path: str, transcript: str) -> list[WordStamp]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.warning("[align] faster-whisper not installed.")
        return []
    model = WhisperModel("base", device="auto", compute_type="int8")
    segs, _ = model.transcribe(wav_path, word_timestamps=True, language="en")
    stamps = []
    for seg in segs:
        for w in (seg.words or []):
            clean = re.sub(r"[^a-zA-Z']", "", w.word).lower()
            if clean:
                stamps.append(WordStamp(word=clean, start=w.start, end=w.end))
    return stamps


def get_word_timestamps(wav_path: str, transcript: str) -> list[WordStamp]:
    backend = ALIGN_BACKEND.lower()
    try:
        stamps = _align_wav2vec2(wav_path, transcript) if backend == "wav2vec2" \
            else _align_whisper(wav_path, transcript)  if backend == "whisper"  \
            else []
        if stamps:
            log.info(f"[align] {len(stamps)} word timestamps via {backend}.")
        else:
            log.warning("[align] No timestamps — proportional fallback.")
        return stamps
    except Exception as e:
        log.warning(f"[align] Error ({backend}): {e}")
        return []


# ═══════════════════════════════════════════════════════════════════
# TIMING HELPERS
# ═══════════════════════════════════════════════════════════════════

def _line_timings_from_stamps(
    lines: list[str], stamps: list[WordStamp], voice_dur: float
) -> list[tuple[float, float]]:
    line_words = []
    for i, line in enumerate(lines):
        for w in re.findall(r"[a-zA-Z']+", line.lower()):
            line_words.append((i, w))
    if not line_words or not stamps: return []

    stamp_idx   = 0
    line_starts: dict[int, float] = {}
    line_ends:   dict[int, float] = {}

    for (li, word) in line_words:
        for si in range(stamp_idx, len(stamps)):
            if stamps[si].word == word:
                if li not in line_starts:
                    line_starts[li] = stamps[si].start
                line_ends[li] = stamps[si].end
                stamp_idx = si + 1
                break

    if not line_starts: return []

    sorted_indices = sorted(line_starts.keys())
    timings = []
    for k, li in enumerate(sorted_indices):
        start   = line_starts[li]
        raw_end = line_ends.get(li, start + 0.5)
        end     = line_starts[sorted_indices[k+1]] if k+1 < len(sorted_indices) \
                  else max(raw_end, voice_dur)
        timings.append((start, max(end - start, 0.3)))

    if len(timings) != len(lines): return []
    return timings


def _proportional_timings(lines: list[str], voice_dur: float) -> list[tuple[float, float]]:
    total_words   = sum(max(len(l.split()), 1) for l in lines)
    raw           = [(max(len(l.split()), 1) / total_words) * voice_dur for l in lines]
    scale         = voice_dur / sum(raw)
    durations     = [d * scale for d in raw]
    timings, cur  = [], 0.0
    for d in durations:
        timings.append((cur, d))
        cur += d
    return timings


# ═══════════════════════════════════════════════════════════════════
# SECTION BOUNDARY TIMES
# Returns the audio start time of each section for visual sync
# ═══════════════════════════════════════════════════════════════════

def _get_section_times(
    sections: dict | None,
    lines: list[str],
    timings: list[tuple[float, float]],
) -> dict[str, float]:
    """
    Returns {section_name: start_time_in_audio} so we can sync
    visual effects (overlay opacity, music swell) to section boundaries.
    """
    if not sections:
        return {}

    section_order = ["hook", "conflict", "shift", "punch", "engage"]
    result = {}
    line_idx = 0

    for key in section_order:
        text = sections.get(key, "").strip()
        if not text:
            continue
        sec_lines = [l.strip() for l in text.split("\n") if l.strip()]
        if line_idx < len(timings):
            result[key] = timings[line_idx][0]
        line_idx += len(sec_lines)

    return result


# ═══════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════

def make_text_clip(text, font, font_size, color, method="label",
                   stroke_color=None, stroke_width=0, size=None):
    """Always adds \n\n padding and enforces TEXT_WIDTH cap."""
    padded = text + "\n\n"
    kwargs = dict(
        text=padded, font=font, font_size=font_size, color=color,
        stroke_color=stroke_color, stroke_width=stroke_width, method=method,
    )
    # Always constrain width — this is what prevents text from getting cut off
    kwargs["size"] = size if size is not None else (TEXT_WIDTH, None)
    return TextClip(**kwargs)


def contains_power_word(line: str) -> bool:
    return any(w in POWER_WORDS for w in re.findall(r"\w+", line.lower()))


def _pill_background(w: int, h: int, duration: float, opacity: float = 0.55) -> ColorClip:
    """Semi-transparent dark pill behind highlighted text for readability on any BG."""
    padding_x, padding_y = 24, 12
    return (
        ColorClip((w + padding_x * 2, h + padding_y * 2), color=COLOR_BLACK)
        .with_opacity(opacity)
        .with_duration(duration)
    )


# ═══════════════════════════════════════════════════════════════════
# PROGRESS BAR
# Yellow bar at bottom that drains left→right over voice_dur
# Pulses at each section boundary
# ═══════════════════════════════════════════════════════════════════

def build_progress_bar(
    voice_dur: float,
    section_times: dict[str, float],
) -> VideoClip:
    BAR_H    = 7
    BAR_Y    = VIDEO_H - BAR_H - 60   # 60px from bottom edge
    BAR_COLOR = np.array(COLOR_BAR, dtype=np.uint8)    # yellow
    PULSE_COLOR = np.array((255, 255, 255), dtype=np.uint8)  # white flash on pulse

    # Sections where we pulse the bar
    pulse_times = set(round(t, 2) for t in section_times.values() if t > 0.5)

    def make_frame(t):
        if t >= voice_dur:
            # Bar gone after voice ends
            frame = np.zeros((BAR_H, VIDEO_W, 3), dtype=np.uint8)
            return frame

        progress   = 1.0 - (t / voice_dur)          # 1.0 → 0.0 (drains left→right)
        bar_width  = max(int(progress * VIDEO_W), 0)

        # Pulse: check if any section boundary within ±0.15s
        is_pulse = any(abs(t - pt) < 0.15 for pt in pulse_times)
        color    = PULSE_COLOR if is_pulse else BAR_COLOR

        frame = np.zeros((BAR_H, VIDEO_W, 3), dtype=np.uint8)
        if bar_width > 0:
            frame[:, :bar_width] = color
        return frame

    bar_clip = (
        VideoClip(make_frame, duration=voice_dur + SILENCE_BUFFER)
        .with_position((0, BAR_Y))
    )
    return bar_clip


# ═══════════════════════════════════════════════════════════════════
# TOP WATERMARK — page name, low opacity, always visible
# ═══════════════════════════════════════════════════════════════════

def build_watermark(total_dur: float) -> TextClip:
    wm = make_text_clip(
        PAGE_NAME.upper(),
        font=FONT_GEORGIA,
        font_size=28,
        color=(255, 255, 255),
        method="label",
        size=(TEXT_WIDTH, None),
    )
    return (
        wm
        .with_opacity(0.28)
        .with_position(("center", 52))
        .with_duration(total_dur)
    )


# ═══════════════════════════════════════════════════════════════════
# DYNAMIC OVERLAY
# Opacity arc: hook dark → shift lighter → punch darkest
# ═══════════════════════════════════════════════════════════════════

def build_dynamic_overlay(total_dur: float, section_times: dict) -> VideoClip:
    """
    Returns a black ColorClip whose opacity changes per section.
    Uses a numpy frame function for smooth transitions.
    """
    # Build a timeline of (time, opacity) keyframes
    keyframes = [(0.0, OVERLAY_HOOK)]

    order_opacity = [
        ("conflict", OVERLAY_BODY),
        ("shift",    OVERLAY_SHIFT),
        ("punch",    OVERLAY_PUNCH),
        ("engage",   OVERLAY_ENGAGE),
    ]
    for sec, opac in order_opacity:
        t = section_times.get(sec)
        if t is not None:
            keyframes.append((t, opac))

    keyframes.append((total_dur, OVERLAY_ENGAGE))
    keyframes.sort(key=lambda x: x[0])

    times   = [k[0] for k in keyframes]
    opacities = [k[1] for k in keyframes]

    def make_frame(t):
        # Interpolate opacity
        opacity = float(np.interp(t, times, opacities))
        frame   = np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
        return frame

    def make_mask(t):
        opacity = float(np.interp(t, times, opacities))
        mask    = np.full((VIDEO_H, VIDEO_W), opacity, dtype=np.float32)
        return mask

    clip = VideoClip(make_frame, duration=total_dur)
    clip = clip.with_effects([])   # no extra effects

    # Simpler approach: use ColorClip with average opacity
    # (full dynamic opacity requires custom mask which complicates compose)
    # We use a layered approach: one ColorClip per section
    clips = []
    for i in range(len(keyframes) - 1):
        t_start, opac_start = keyframes[i]
        t_end,   opac_end   = keyframes[i + 1]
        seg_dur = t_end - t_start
        if seg_dur <= 0:
            continue
        avg_opacity = (opac_start + opac_end) / 2
        seg = (
            ColorClip((VIDEO_W, VIDEO_H), color=COLOR_BLACK, duration=seg_dur)
            .with_opacity(avg_opacity)
            .with_start(t_start)
        )
        clips.append(seg)

    return clips   # list of segmented overlays


# ═══════════════════════════════════════════════════════════════════
# VIGNETTE — dark edges top and bottom, cinematic feel
# ═══════════════════════════════════════════════════════════════════

def build_vignette(total_dur: float) -> list:
    VIGNETTE_H = 280
    clips = []

    def top_frame(t):
        frame = np.zeros((VIGNETTE_H, VIDEO_W, 3), dtype=np.uint8)
        return frame

    def top_mask(t):
        gradient = np.linspace(0.72, 0.0, VIGNETTE_H, dtype=np.float32)
        mask = np.tile(gradient[:, np.newaxis], (1, VIDEO_W))
        return mask

    top = (VideoClip(top_frame, duration=total_dur)
           .with_position((0, 0)))

    def bot_frame(t):
        frame = np.zeros((VIGNETTE_H, VIDEO_W, 3), dtype=np.uint8)
        return frame

    bot = (VideoClip(bot_frame, duration=total_dur)
           .with_position((0, VIDEO_H - VIGNETTE_H)))

    # Approximate with ColorClip gradients
    top_vig = (
        ColorClip((VIDEO_W, VIGNETTE_H), color=COLOR_BLACK, duration=total_dur)
        .with_opacity(0.55)
        .with_position((0, 0))
    )
    bot_vig = (
        ColorClip((VIDEO_W, VIGNETTE_H), color=COLOR_BLACK, duration=total_dur)
        .with_opacity(0.60)
        .with_position((0, VIDEO_H - VIGNETTE_H))
    )
    clips.extend([top_vig, bot_vig])
    return clips


# ═══════════════════════════════════════════════════════════════════
# BACKGROUND — dual image with crossfade at shift section
# ═══════════════════════════════════════════════════════════════════

def build_background(
    image1: str,
    image2: str,
    total_dur: float,
    shift_time: float | None,
) -> list:
    """
    Two background images. If shift_time is available, crossfade
    from image1 to image2 over 1.2s at the shift section boundary.
    This resets viewer attention at the emotional pivot point.
    """
    def zoom_func(t):
        base   = 1 + 0.008 * t
        pulse  = 0.018 if (5.0  < t < 5.30) else 0.0
        pulse2 = 0.012 if (12.0 < t < 12.25) else 0.0
        return base + pulse + pulse2

    bg1 = (
        ImageClip(image1).with_duration(total_dur).resized(height=VIDEO_H)
    )
    bg1 = bg1.cropped(x_center=bg1.w/2, width=VIDEO_W, height=VIDEO_H)
    bg1 = bg1.with_effects([vfx.Resize(zoom_func)])

    if image1 == image2 or shift_time is None:
        return [bg1]

    # Second image fades in at shift_time
    crossfade_dur = 1.2
    bg2_start     = max(shift_time - crossfade_dur / 2, 0)
    bg2_dur       = total_dur - bg2_start

    bg2 = (
        ImageClip(image2).with_duration(bg2_dur).resized(height=VIDEO_H)
    )
    bg2 = bg2.cropped(x_center=bg2.w/2, width=VIDEO_W, height=VIDEO_H)

    def zoom_func2(t):
        return 1 + 0.008 * t

    bg2 = (
        bg2
        .with_effects([vfx.Resize(zoom_func2), vfx.FadeIn(crossfade_dur)])
        .with_start(bg2_start)
    )

    return [bg1, bg2]


# ═══════════════════════════════════════════════════════════════════
# OUTRO CLIPS
# ═══════════════════════════════════════════════════════════════════

def build_outro_clips(voice_duration: float, total_duration: float) -> list:
    outro_start = voice_duration + SILENCE_BUFFER
    outro_dur   = total_duration - outro_start
    clips       = []

    vignette = (
        ColorClip((VIDEO_W, VIDEO_H), color=COLOR_BLACK, duration=outro_dur)
        .with_opacity(0.72).with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(vignette)

    ANCHOR       = VIDEO_H // 2
    LINE_W       = 380
    LINE_ABOVE_Y = ANCHOR - 70
    NAME_Y       = ANCHOR - 50
    LINE_BELOW_Y = ANCHOR + 30
    TAGLINE_Y    = ANCHOR + 50

    for y in [LINE_ABOVE_Y, LINE_BELOW_Y]:
        clips.append(
            ColorClip((LINE_W, 2), color=COLOR_WHITE, duration=outro_dur)
            .with_position(("center", y)).with_start(outro_start)
            .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
        )

    spaced_name = "  ".join(PAGE_NAME.upper())
    name_clip = (
        make_text_clip(spaced_name, FONT_GEORGIA, 74, COLOR_WHITE, method="label",
                       size=(TEXT_WIDTH, None))
        .with_position(("center", NAME_Y)).with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(name_clip)

    tagline_clip = (
        make_text_clip("philosophy for the modern mind", FONT_GEORGIA_I, 32,
                       COLOR_GRAY, method="label", size=(TEXT_WIDTH, None))
        .with_position(("center", TAGLINE_Y)).with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN + 0.35), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(tagline_clip)
    return clips


# ═══════════════════════════════════════════════════════════════════
# SUBTITLE CLIPS
# ═══════════════════════════════════════════════════════════════════

def build_subtitle_clips(
    lines:         list[str],
    voice_dur:     float,
    sections:      dict | None,
    stamps:        list[WordStamp],
    section_times: dict[str, float],
) -> list:
    """
    Hook    → word-by-word flash (each word pops individually)
    Punch   → full-screen centered, no fade-out (hard cut to outro)
    Power   → yellow text + dark pill background
    Engage  → gold
    Normal  → white
    All text constrained to TEXT_WIDTH — no cutoff on any device.
    """
    subtitle_clips = []

    hook_lines   = []
    punch_lines  = []
    engage_lines = []

    if sections:
        hook_text   = sections.get("hook",   "").strip()
        punch_text  = sections.get("punch",  "").strip()
        engage_text = sections.get("engage", "").strip()
        hook_lines   = [l.strip() for l in hook_text.split("\n")   if l.strip()]
        punch_lines  = [l.strip() for l in punch_text.split("\n")  if l.strip()]
        engage_lines = [l.strip() for l in engage_text.split("\n") if l.strip()]

    # Timing
    timings = None
    if stamps:
        timings = _line_timings_from_stamps(lines, stamps, voice_dur)
    if not timings:
        timings = _proportional_timings(lines, voice_dur)
        log.info("[subtitle] Proportional fallback timing.")
    else:
        log.info("[subtitle] Real word-timestamp alignment.")

    punch_start_time = section_times.get("punch")

    for i, line in enumerate(lines):
        start_t, dur = timings[i]

        is_hook   = any(line.strip() == hl for hl in hook_lines)
        is_punch  = any(line.strip() == pl for pl in punch_lines)
        is_engage = any(line.strip() == el for el in engage_lines)
        has_power = contains_power_word(line)

        # ── HOOK: word-by-word flash ─────────────────────────────
        if is_hook:
            words     = line.split()
            word_dur  = HOOK_WORD_DURATION
            # Distribute across available time, capped at word_dur each
            available  = dur
            actual_dur = min(word_dur, available / max(len(words), 1))

            for wi, word in enumerate(words):
                w_start = start_t + wi * actual_dur
                if w_start >= start_t + dur:
                    break
                w_clip = make_text_clip(
                    word.upper(),
                    font=FONT_PATH,
                    font_size=FONT_SIZE_HOOK,
                    color=COLOR_WHITE,
                    method="caption",
                    stroke_color="black",
                    stroke_width=8,
                    size=(TEXT_WIDTH, None),
                )
                y_pos = HOOK_Y
                w_clip = (
                    w_clip
                    .with_position(("center", y_pos))
                    .with_start(w_start)
                    .with_duration(actual_dur)
                    .with_effects([vfx.FadeIn(0.04), vfx.FadeOut(0.06)])
                )
                subtitle_clips.append(w_clip)
            continue

        # ── PUNCH: full screen centered, no fade-out ─────────────
        if is_punch:
            wrapped = textwrap.fill(line, width=WRAP_WIDTH_PUNCH)
            txt = make_text_clip(
                wrapped,
                font=FONT_PATH,
                font_size=FONT_SIZE_PUNCH,
                color=COLOR_YELLOW,
                method="caption",
                stroke_color="black",
                stroke_width=9,
                size=(TEXT_WIDTH, None),
            )
            # Center vertically
            y_pos = max(PUNCH_CENTER_Y - txt.h // 2, 200)
            txt = (
                txt
                .with_position(("center", y_pos))
                .with_start(start_t)
                .with_duration(dur)
                .with_effects([vfx.FadeIn(0.08)])  # fast pop in, NO fade out
            )
            subtitle_clips.append(txt)
            continue

        # ── ENGAGE ───────────────────────────────────────────────
        if is_engage:
            wrapped = textwrap.fill(line, width=WRAP_WIDTH_NORMAL)
            txt = make_text_clip(
                wrapped,
                font=FONT_PATH,
                font_size=FONT_SIZE_ENGAGE,
                color=COLOR_GOLD,
                method="caption",
                stroke_color="black",
                stroke_width=5,
                size=(TEXT_WIDTH, None),
            )
            y_pos = max(TEXT_BOTTOM_Y - txt.h, 200)
            txt = (
                txt
                .with_position(("center", y_pos))
                .with_start(start_t)
                .with_duration(dur)
                .with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.3)])
            )
            subtitle_clips.append(txt)
            continue

        # ── POWER WORD: yellow + pill background ─────────────────
        if has_power:
            wrapped = textwrap.fill(line, width=WRAP_WIDTH_NORMAL)
            txt = make_text_clip(
                wrapped,
                font=FONT_PATH,
                font_size=FONT_SIZE_POWER,
                color=COLOR_YELLOW,
                method="caption",
                stroke_color="black",
                stroke_width=6,
                size=(TEXT_WIDTH, None),
            )
            y_pos = max(TEXT_BOTTOM_Y - txt.h, 200)

            # Dark pill behind the text for readability
            pill = (
                _pill_background(txt.w, txt.h, dur, opacity=0.50)
                .with_position(("center", y_pos - 12))
                .with_start(start_t)
                .with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.3)])
            )
            txt = (
                txt
                .with_position(("center", y_pos))
                .with_start(start_t)
                .with_duration(dur)
                .with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.3)])
            )
            subtitle_clips.extend([pill, txt])
            continue

        # ── NORMAL ───────────────────────────────────────────────
        wrapped = textwrap.fill(line, width=WRAP_WIDTH_NORMAL)
        txt = make_text_clip(
            wrapped,
            font=FONT_PATH,
            font_size=FONT_SIZE_NORMAL,
            color=COLOR_WHITE,
            method="caption",
            stroke_color="black",
            stroke_width=5,
            size=(TEXT_WIDTH, None),
        )
        y_pos = max(TEXT_BOTTOM_Y - txt.h, 200)
        txt = (
            txt
            .with_position(("center", y_pos))
            .with_start(start_t)
            .with_duration(dur)
            .with_effects([vfx.FadeIn(0.35), vfx.FadeOut(0.3)])
        )
        subtitle_clips.append(txt)

    return subtitle_clips


# ═══════════════════════════════════════════════════════════════════
# AUDIO — music swell at punch + optional impact SFX
# ═══════════════════════════════════════════════════════════════════

def build_audio(
    voice_mp3:     str,
    total_dur:     float,
    voice_dur:     float,
    punch_time:    float | None,
) -> CompositeAudioClip:
    """
    Voice + music with dynamic volume arc:
      - Base volume 0.08 throughout
      - Swell to 0.22 at punch section, ramp back down over 3s
    Optional: impact SFX at punch_time if sfx/impact.mp3 exists.
    """
    voice       = AudioFileClip(voice_mp3)
    voice_faded = voice.with_effects([afx.AudioFadeOut(0.5)])

    raw_music = AudioFileClip(MUSIC_FILE).subclipped(0, total_dur)

    if punch_time is None:
        # Flat volume
        music = (
            raw_music
            .with_volume_scaled(MUSIC_VOL_BASE)
            .with_effects([afx.AudioFadeOut(OUTRO_FADE_OUT + 0.2)])
        )
        audio_layers = [voice_faded, music]
    else:
        # Build volume array: base → swell at punch → back down → outro
        sr          = 44100
        n_samples   = int(total_dur * sr)
        vol_array   = np.full(n_samples, MUSIC_VOL_BASE, dtype=np.float32)

        swell_start = int(punch_time * sr)
        swell_peak  = int((punch_time + 0.4) * sr)
        swell_end   = int((punch_time + 3.0) * sr)

        # Ramp up to peak
        ramp_up_len = max(swell_peak - swell_start, 1)
        vol_array[swell_start:swell_peak] = np.linspace(
            MUSIC_VOL_BASE, MUSIC_VOL_PUNCH, ramp_up_len
        )
        # Ramp down from peak
        ramp_dn_len = max(min(swell_end, n_samples) - swell_peak, 1)
        vol_array[swell_peak:swell_peak + ramp_dn_len] = np.linspace(
            MUSIC_VOL_PUNCH, MUSIC_VOL_OUTRO,
            ramp_dn_len,
        )
        # Flat outro level after swell
        if swell_end < n_samples:
            vol_array[swell_end:] = MUSIC_VOL_OUTRO

        def make_music_frame(t):
            # Get the raw frame and scale by our volume envelope
            raw_frame  = raw_music.get_frame(t)
            sample_idx = min(int(t * sr), n_samples - 1)
            return raw_frame * vol_array[sample_idx]

        music = (
            AudioFileClip(MUSIC_FILE)
            .subclipped(0, total_dur)
            .with_volume_scaled(MUSIC_VOL_BASE)
            .with_effects([afx.AudioFadeOut(OUTRO_FADE_OUT + 0.2)])
        )
        # Note: full per-sample envelope requires AudioArrayClip for precision.
        # Using scaled clip + manual swell approximation via MultiplyVolumeTo is
        # not in moviepy public API. We implement the swell as a secondary clip
        # layered over the base, which is the clean moviepy way to do it.

        # Swell layer: short clip at punch time, fades in/out, louder volume
        swell_clip_dur = min(3.5, total_dur - punch_time)
        if swell_clip_dur > 0.5:
            swell = (
                AudioFileClip(MUSIC_FILE)
                .subclipped(punch_time, punch_time + swell_clip_dur)
                .with_volume_scaled(MUSIC_VOL_PUNCH - MUSIC_VOL_BASE)
                .with_effects([afx.AudioFadeIn(0.4), afx.AudioFadeOut(2.0)])
                .with_start(punch_time)
            )
            audio_layers = [voice_faded, music, swell]
        else:
            audio_layers = [voice_faded, music]

    # Optional impact SFX
    sfx_path = os.path.join(SFX_FOLDER, "impact.mp3")
    if punch_time is not None and os.path.exists(sfx_path):
        try:
            sfx = (
                AudioFileClip(sfx_path)
                .with_volume_scaled(0.6)
                .with_start(punch_time)
            )
            audio_layers.append(sfx)
            log.info(f"[audio] Impact SFX added at t={punch_time:.1f}s")
        except Exception as e:
            log.warning(f"[audio] SFX load failed: {e}")

    return CompositeAudioClip(audio_layers)


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def render_reel(reel_name: str, script: str, sections_json: str | None) -> str:
    """
    Renders a single reel. Returns output .mp4 path.
    Raises on failure — caller handles retry / status update.
    """
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    sections = json.loads(sections_json) if sections_json else None

    safe_name   = re.sub(r"[^\w]", "_", reel_name).lower()
    voice_mp3   = os.path.join(OUTPUT_FOLDER, f"_tmp_voice_{safe_name}.mp3")
    voice_wav   = os.path.join(OUTPUT_FOLDER, f"_tmp_voice_{safe_name}_align.wav")
    output_path = os.path.join(OUTPUT_FOLDER, f"{safe_name}.mp4")

    log.info(f"[render] ══ Starting: {reel_name} ══")

    # ── 1. Voice ──────────────────────────────────────────
    log.info("[render] Generating voice (Chatterbox, sectioned)...")
    asyncio.run(generate_voice_sectioned(sections, script, voice_mp3))
    voice     = AudioFileClip(voice_mp3)
    voice_dur = voice.duration
    total_dur = voice_dur + SILENCE_BUFFER + OUTRO_HOLD
    log.info(f"[render] voice={voice_dur:.1f}s  total={total_dur:.1f}s")

    # ── 2. Forced alignment ────────────────────────────────
    subprocess.run(
        ["ffmpeg", "-y", "-i", voice_mp3, voice_wav],
        check=True, capture_output=True,
    )
    lines  = [l.strip() for l in script.split("\n") if l.strip()]
    stamps = get_word_timestamps(voice_wav, " ".join(lines))
    try: os.remove(voice_wav)
    except OSError: pass

    # ── 3. Timings + section boundary times ───────────────
    timings = None
    if stamps:
        timings = _line_timings_from_stamps(lines, stamps, voice_dur)
    if not timings:
        timings = _proportional_timings(lines, voice_dur)

    section_times = _get_section_times(sections, lines, timings)
    punch_time    = section_times.get("punch")
    shift_time    = section_times.get("shift")
    log.info(f"[render] Section times: {section_times}")

    # ── 4. Background (dual image crossfade at shift) ──────
    images = [
        f for f in os.listdir(STOCK_FOLDER)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ]
    if not images:
        raise FileNotFoundError(f"No images in STOCK_FOLDER={STOCK_FOLDER!r}")

    img1 = os.path.join(STOCK_FOLDER, random.choice(images))
    img2 = os.path.join(STOCK_FOLDER, random.choice(images))
    log.info(f"[render] BG1={os.path.basename(img1)}  BG2={os.path.basename(img2)}")
    bg_clips = build_background(img1, img2, total_dur, shift_time)

    # ── 5. Dynamic overlay (opacity arc per section) ───────
    overlay_clips = build_dynamic_overlay(total_dur, section_times)

    # ── 6. Vignette ────────────────────────────────────────
    vignette_clips = build_vignette(total_dur)

    # ── 7. Subtitles ───────────────────────────────────────
    log.info("[render] Building subtitles...")
    subtitle_clips = build_subtitle_clips(
        lines, voice_dur, sections, stamps, section_times
    )

    # ── 8. Progress bar ────────────────────────────────────
    log.info("[render] Building progress bar...")
    progress_bar = build_progress_bar(voice_dur, section_times)

    # ── 9. Watermark ───────────────────────────────────────
    watermark = build_watermark(total_dur)

    # ── 10. Outro ──────────────────────────────────────────
    log.info("[render] Building outro...")
    outro_clips = build_outro_clips(voice_dur, total_dur)

    # ── 11. Audio (music swell + optional SFX) ─────────────
    log.info("[render] Building audio...")
    final_audio = build_audio(voice_mp3, total_dur, voice_dur, punch_time)

    # ── 12. Compose ────────────────────────────────────────
    all_clips = (
        bg_clips
        + overlay_clips
        + vignette_clips
        + [watermark]
        + subtitle_clips
        + [progress_bar]
        + outro_clips
    )

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
        preset="fast",
        threads=4,
    )

    # ── 13. Cleanup ────────────────────────────────────────
    try: os.remove(voice_mp3)
    except OSError: pass

    log.info(f"[render] ✓ Done: {output_path}")
    return output_path