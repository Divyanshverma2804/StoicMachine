"""
renderer.py — Reel rendering logic for ReelForge pipeline.
Visual / timing logic ported from Viral-Reel-Script.py.

KEY UPGRADES vs previous version:
  1. Real word-level timestamp sync via forced alignment (wav2vec2)
     — subtitles snap to actual spoken word boundaries, not word-count estimates
  2. Chatterbox TTS tuned for authoritative motivational delivery
     — per-section emotion: hook/punch = high exaggeration, body = medium, engage = warm
  3. Script preprocessed with pacing markers before TTS
     — SCREAMING CAPS normalised so neural TTS reads them naturally
     — ellipsis pause injected between lines for natural rhythm

TTS: Chatterbox only (edge-tts not available on VM).
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
from dataclasses import dataclass

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
# CONFIG  —  resolved from env
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

# ── Chatterbox tuning per content section ─────────────────────────────────────
# exaggeration: 0.0 = flat/robotic  →  1.0 = very dramatic
# cfg_weight:   higher = more committed to the style/emotion
#
# hook / punch  → punchy, intense, commanding
# conflict      → urgent, tense
# shift         → calm authority — the "truth drop" moment
# engage        → warm, inviting, slightly softer
# default       → neutral authoritative baseline
SECTION_TTS_PARAMS = {
    "hook":     {"exaggeration": 0.75, "cfg_weight": 0.55},
    "punch":    {"exaggeration": 0.80, "cfg_weight": 0.60},
    "conflict": {"exaggeration": 0.65, "cfg_weight": 0.50},
    "shift":    {"exaggeration": 0.45, "cfg_weight": 0.45},
    "engage":   {"exaggeration": 0.50, "cfg_weight": 0.40},
    "default":  {"exaggeration": 0.55, "cfg_weight": 0.45},
}

# ── Forced-alignment backend ───────────────────────────────────────────────────
# "wav2vec2"  : best accuracy, ~400MB model on first run (recommended)
# "whisper"   : good accuracy, uses faster-whisper
# "fallback"  : word-count proportional — used if alignment fails
ALIGN_BACKEND = os.environ.get("ALIGN_BACKEND", "wav2vec2")


# =========================================
# CHATTERBOX TTS
# model loaded once into memory, reused for every reel in the batch
# =========================================

_tts_model = None


def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        import torch
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info(f"[tts] Loading Chatterbox on {device}...")
        _tts_model = ChatterboxTTS.from_pretrained(device=device)
        log.info("[tts] Model ready and cached.")
    return _tts_model


def _preprocess_for_tts(text: str) -> str:
    """
    Clean up script text before sending to Chatterbox.

    - SCREAMING CAPS → Title Case
      Neural TTS reads ALL-CAPS identically to lowercase.
      Title-casing lets the model focus on prosody instead of fighting the casing.
    - Lines joined with a single space.
      Chatterbox handles natural pauses from punctuation (. , !) on its own.
      DO NOT use '...' as a join — Chatterbox will literally speak it.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    cleaned = []
    for line in lines:
        # Normalize SCREAMING CAPS words to Title Case
        line = re.sub(
            r'\b([A-Z]{2,})\b',
            lambda m: m.group(1).title(),
            line,
        )
        cleaned.append(line)
    # Join with single space — punctuation already signals pauses to Chatterbox
    return " ".join(cleaned)


def _generate_voice_for_section(text: str, wav_path: str, section_key: str = "default"):
    """Synchronous Chatterbox call for one section. Saves .wav to wav_path."""
    import torchaudio as ta

    model  = _get_tts_model()
    params = SECTION_TTS_PARAMS.get(section_key, SECTION_TTS_PARAMS["default"])

    # env vars override defaults so you can tune without redeploying
    exaggeration = float(os.environ.get("TTS_EXAGGERATION", str(params["exaggeration"])))
    cfg_weight   = float(os.environ.get("TTS_CFG_WEIGHT",   str(params["cfg_weight"])))
    ref_clip     = os.environ.get("TTS_VOICE_REF", "").strip()

    kwargs = dict(exaggeration=exaggeration, cfg_weight=cfg_weight)
    if ref_clip and os.path.exists(ref_clip):
        kwargs["audio_prompt_path"] = ref_clip
        log.info(f"[tts] Voice cloning from: {ref_clip}")

    log.info(f"[tts] {section_key}: exag={exaggeration:.2f}  cfg={cfg_weight:.2f}")
    wav = model.generate(text, **kwargs)
    ta.save(wav_path, wav, model.sr)


def _wav_to_mp3(wav_path: str, mp3_path: str):
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path,
         "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
        check=True, capture_output=True,
    )


def _concat_wavs(wav_paths: list, out_path: str):
    """Concatenate multiple .wav files using ffmpeg concat demuxer."""
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
    """
    Generate TTS audio with per-section emotion tuning.

    If sections dict is available each section is rendered with its own
    exaggeration / cfg_weight params then concatenated into one file.
    Falls back to a single-pass render with default params if no sections.

    Returns the path to the final .mp3.
    """
    tmp_dir = os.path.dirname(mp3_out)

    if not sections:
        processed = _preprocess_for_tts(script)
        wav_path  = mp3_out.replace(".mp3", ".wav")
        _generate_voice_for_section(processed, wav_path, "default")
        _wav_to_mp3(wav_path, mp3_out)
        try:
            os.remove(wav_path)
        except OSError:
            pass
        return mp3_out

    # Per-section rendering
    section_order = ["hook", "conflict", "shift", "punch", "engage"]
    wav_parts     = []

    for key in section_order:
        text = sections.get(key, "").strip()
        if not text:
            continue
        processed = _preprocess_for_tts(text)
        wav_path  = os.path.join(
            tmp_dir,
            f"_sec_{key}_{os.path.basename(mp3_out)}.wav",
        )
        _generate_voice_for_section(processed, wav_path, key)
        wav_parts.append(wav_path)
        log.info(f"[tts] Section rendered: {key}")

    combined_wav = mp3_out.replace(".mp3", "_combined.wav")
    _concat_wavs(wav_parts, combined_wav)
    _wav_to_mp3(combined_wav, mp3_out)

    for p in wav_parts + [combined_wav]:
        try:
            os.remove(p)
        except OSError:
            pass

    return mp3_out


# =========================================
# FORCED ALIGNMENT — real word timestamps
# =========================================

@dataclass
class WordStamp:
    word:  str
    start: float   # seconds into audio
    end:   float   # seconds into audio


def _align_wav2vec2(wav_path: str, transcript: str) -> list[WordStamp]:
    """
    torchaudio MMS forced alignment — best accuracy.
    Requires torchaudio >= 2.1  (already on the VM for Chatterbox).
    No extra model download needed beyond torchaudio's bundled MMS_300M.
    """
    import torch
    import torchaudio

    device = "cuda" if torch.cuda.is_available() else "cpu"
    waveform, sample_rate = torchaudio.load(wav_path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    bundle    = torchaudio.pipelines.MMS_300M
    model_    = bundle.get_model().to(device)
    tokenizer = bundle.get_tokenizer()
    aligner   = bundle.get_aligner()

    if sample_rate != bundle.sample_rate:
        waveform = torchaudio.functional.resample(
            waveform, sample_rate, bundle.sample_rate
        )

    with torch.inference_mode():
        emission, _ = model_(waveform.to(device))

    words = re.findall(r"[a-zA-Z']+", transcript.lower())
    if not words:
        return []

    try:
        token_spans = aligner(emission[0], tokenizer(words))
    except Exception as e:
        log.warning(f"[align] wav2vec2 failed: {e}")
        return []

    ratio  = waveform.shape[1] / emission.shape[1] / bundle.sample_rate
    stamps = []
    for i, spans in enumerate(token_spans):
        stamps.append(WordStamp(
            word=words[i],
            start=spans[0].start * ratio,
            end=spans[-1].end   * ratio,
        ))
    return stamps


def _align_whisper(wav_path: str, transcript: str) -> list[WordStamp]:
    """
    faster-whisper with word_timestamps=True.
    Install: pip install faster-whisper
    """
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
    """Try configured alignment backend; return empty list on any failure."""
    backend = ALIGN_BACKEND.lower()
    try:
        stamps = _align_wav2vec2(wav_path, transcript) if backend == "wav2vec2" \
            else _align_whisper(wav_path, transcript) if backend == "whisper" \
            else []

        if stamps:
            log.info(f"[align] {len(stamps)} word timestamps via {backend}.")
        else:
            log.warning("[align] No timestamps — will use proportional fallback.")
        return stamps

    except Exception as e:
        log.warning(f"[align] Error ({backend}): {e} — using proportional fallback.")
        return []


# =========================================
# TIMESTAMP → PER-LINE (start, duration) PAIRS
# =========================================

def _line_timings_from_stamps(
    lines:     list[str],
    stamps:    list[WordStamp],
    voice_dur: float,
) -> list[tuple[float, float]]:
    """
    Walk stamp list in order and assign each script line a start/end
    based on its first and last matched word stamps.

    Gaps between lines are absorbed into the preceding line so there is
    never a blank-screen moment mid-speech.
    """
    # Build flat (line_index, clean_word) list
    line_words = []
    for i, line in enumerate(lines):
        for w in re.findall(r"[a-zA-Z']+", line.lower()):
            line_words.append((i, w))

    if not line_words or not stamps:
        return []

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

    if not line_starts:
        return []

    sorted_indices = sorted(line_starts.keys())
    timings        = []

    for k, li in enumerate(sorted_indices):
        start   = line_starts[li]
        raw_end = line_ends.get(li, start + 0.5)

        # Extend to next line's start to absorb gap
        if k + 1 < len(sorted_indices):
            end = line_starts[sorted_indices[k + 1]]
        else:
            end = max(raw_end, voice_dur)

        duration = max(end - start, 0.3)   # floor at 0.3s
        timings.append((start, duration))

    if len(timings) != len(lines):
        log.warning("[align] Line count mismatch after stamp matching — using proportional.")
        return []

    return timings


def _proportional_timings(lines: list[str], voice_dur: float) -> list[tuple[float, float]]:
    """Word-count proportional timing — fallback when alignment unavailable."""
    total_words   = sum(max(len(l.split()), 1) for l in lines)
    raw_durations = [(max(len(l.split()), 1) / total_words) * voice_dur for l in lines]
    scale         = voice_dur / sum(raw_durations)
    durations     = [d * scale for d in raw_durations]

    timings  = []
    current  = 0.0
    for d in durations:
        timings.append((current, d))
        current += d
    return timings


# =========================================
# HELPERS
# =========================================

def make_text_clip(text, font, font_size, color, method="label",
                   stroke_color=None, stroke_width=0, size=None):
    padded = text + "\n\n"
    kwargs = dict(
        text=padded, font=font, font_size=font_size, color=color,
        stroke_color=stroke_color, stroke_width=stroke_width, method=method,
    )
    if size is not None:
        kwargs["size"] = size
    return TextClip(**kwargs)


def contains_power_word(line: str) -> bool:
    return any(w in POWER_WORDS for w in re.findall(r"\w+", line.lower()))


# =========================================
# OUTRO CLIPS
# =========================================

def build_outro_clips(voice_duration: float, total_duration: float) -> list:
    outro_start = voice_duration + SILENCE_BUFFER
    outro_dur   = total_duration - outro_start
    clips       = []

    vignette = (
        ColorClip((VIDEO_W, VIDEO_H), color=(0, 0, 0), duration=outro_dur)
        .with_opacity(0.70).with_start(outro_start)
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

    line_above = (
        ColorClip((LINE_W, LINE_H), color=(255, 255, 255), duration=outro_dur)
        .with_position(("center", LINE_ABOVE_Y)).with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(line_above)

    spaced_name = "  ".join(PAGE_NAME.upper())
    name_clip = (
        make_text_clip(spaced_name, FONT_GEORGIA, 74, "white", method="label")
        .with_position(("center", NAME_Y)).with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(name_clip)

    line_below = (
        ColorClip((LINE_W, LINE_H), color=(255, 255, 255), duration=outro_dur)
        .with_position(("center", LINE_BELOW_Y)).with_start(outro_start)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(line_below)

    tagline_clip = (
        make_text_clip(
            "philosophy for the modern mind",
            FONT_GEORGIA_I, 32, (210, 210, 210), method="label",
        )
        .with_position(("center", TAGLINE_Y)).with_start(outro_start)
        .with_duration(outro_dur)
        .with_effects([vfx.FadeIn(OUTRO_FADE_IN + 0.35), vfx.FadeOut(OUTRO_FADE_OUT)])
    )
    clips.append(tagline_clip)
    return clips


# =========================================
# SUBTITLE CLIPS  —  real timestamps when available, proportional fallback
# =========================================

def build_subtitle_clips(
    lines:     list[str],
    voice_dur: float,
    sections:  dict | None,
    stamps:    list[WordStamp],
) -> list:
    subtitle_clips = []

    hook_line   = None
    engage_line = None
    if sections:
        hook_line   = sections.get("hook",   "").strip().split("\n")[0].strip()
        engage_line = sections.get("engage", "").strip().split("\n")[0].strip()

    # Choose timing source
    timings = None
    if stamps:
        timings = _line_timings_from_stamps(lines, stamps, voice_dur)
    if not timings:
        timings = _proportional_timings(lines, voice_dur)
        log.info("[subtitle] Using proportional fallback timing.")
    else:
        log.info("[subtitle] Using real word-timestamp alignment.")

    for i, line in enumerate(lines):
        wrapped  = textwrap.fill(line, width=24)
        is_hook  = bool(hook_line   and line.strip().startswith(hook_line[:20]))
        is_engage= bool(engage_line and line.strip().startswith(engage_line[:20]))
        has_power= contains_power_word(line)

        if is_hook:
            font_size, color, fade_in_dur, y_override = 118, "white", 0.12, 420
        elif is_engage:
            font_size, color, fade_in_dur, y_override = 96, (255, 215, 0), 0.2, None
        elif has_power:
            font_size, color, fade_in_dur, y_override = FONT_SIZE + 6, (255, 230, 50), 0.3, None
        else:
            font_size, color, fade_in_dur, y_override = FONT_SIZE, "white", 0.4, None

        txt = make_text_clip(
            wrapped, FONT_PATH, font_size, color,
            method="caption", stroke_color="black",
            stroke_width=5 if not is_hook else 7,
            size=(TEXT_WIDTH, None),
        )

        y_pos        = y_override if y_override is not None else max(TEXT_BOTTOM_Y - txt.h, 200)
        start_t, dur = timings[i]

        txt = (
            txt
            .with_position(("center", y_pos))
            .with_start(start_t)
            .with_duration(dur)
            .with_effects([vfx.FadeIn(fade_in_dur), vfx.FadeOut(0.3)])
        )
        subtitle_clips.append(txt)

    return subtitle_clips


# =========================================
# BACKGROUND
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
        pulse  = 0.022 if (5.0  < t < 5.35) else 0.0
        pulse2 = 0.015 if (12.0 < t < 12.3) else 0.0
        return base + pulse + pulse2

    return bg.with_effects([vfx.Resize(zoom_func)])


# =========================================
# PUBLIC API
# =========================================

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

    log.info(f"[render] ── Starting: {reel_name} ──")

    # ── 1. Voice  (per-section emotion tuning) ────────────
    log.info("[render] Generating voice (Chatterbox, sectioned)...")
    asyncio.run(generate_voice_sectioned(sections, script, voice_mp3))
    voice     = AudioFileClip(voice_mp3)
    voice_dur = voice.duration
    total_dur = voice_dur + SILENCE_BUFFER + OUTRO_HOLD
    log.info(f"[render] voice={voice_dur:.1f}s  total={total_dur:.1f}s")

    # ── 2. Forced alignment — real word timestamps ─────────
    # Convert mp3 → wav (alignment tools need PCM)
    subprocess.run(
        ["ffmpeg", "-y", "-i", voice_mp3, voice_wav],
        check=True, capture_output=True,
    )
    lines  = [l.strip() for l in script.split("\n") if l.strip()]
    stamps = get_word_timestamps(voice_wav, " ".join(lines))
    try:
        os.remove(voice_wav)
    except OSError:
        pass

    # ── 3. Background ─────────────────────────────────────
    images = [
        f for f in os.listdir(STOCK_FOLDER)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ]
    if not images:
        raise FileNotFoundError(f"No images in STOCK_FOLDER={STOCK_FOLDER!r}")
    selected_image = os.path.join(STOCK_FOLDER, random.choice(images))
    log.info(f"[render] Background: {selected_image}")
    bg = build_background(selected_image, total_dur)

    overlay = (
        ColorClip((VIDEO_W, VIDEO_H), color=(0, 0, 0), duration=total_dur)
        .with_opacity(0.52)
    )

    # ── 4. Subtitles  (real timestamps when available) ────
    log.info("[render] Building subtitles...")
    subtitle_clips = build_subtitle_clips(lines, voice_dur, sections, stamps)

    # ── 5. Outro ──────────────────────────────────────────
    log.info("[render] Building outro...")
    outro_clips = build_outro_clips(voice_dur, total_dur)

    # ── 6. Audio ──────────────────────────────────────────
    music = (
        AudioFileClip(MUSIC_FILE)
        .subclipped(0, total_dur)
        .with_volume_scaled(0.12)
        .with_effects([afx.AudioFadeOut(OUTRO_FADE_OUT + 0.2)])
    )
    voice_faded = voice.with_effects([afx.AudioFadeOut(0.5)])
    final_audio = CompositeAudioClip([voice_faded, music])

    # ── 7. Compose ────────────────────────────────────────
    final = (
        CompositeVideoClip(
            [bg, overlay] + subtitle_clips + outro_clips,
            size=(VIDEO_W, VIDEO_H),
        )
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
    )

    # ── 8. Cleanup ────────────────────────────────────────
    try:
        os.remove(voice_mp3)
    except OSError:
        pass

    log.info(f"[render] ✓ Saved: {output_path}")
    return output_path