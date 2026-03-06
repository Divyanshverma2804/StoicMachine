"""
renderer.py — Reel rendering logic (adapted from reel_maker.py)
Called per-job so one failure never blocks others.
"""
import os, re, asyncio, textwrap, random, json, logging
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip,
    CompositeVideoClip, CompositeAudioClip,
    ColorClip, vfx, afx,
)

log = logging.getLogger("renderer")

# ── Paths resolved from env so they work on the VM ──
STOCK_FOLDER  = os.environ.get("STOCK_FOLDER",  "stock")
MUSIC_FILE    = os.environ.get("MUSIC_FILE",    "music.mp3")
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "output")
FONT_PATH     = os.environ.get("FONT_PATH",     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_GEORGIA  = os.environ.get("FONT_GEORGIA",  "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf")
FONT_GEORGIA_I= os.environ.get("FONT_GEORGIA_I","/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf")

PAGE_NAME   = os.environ.get("PAGE_NAME", "Silenor")
VIDEO_W     = 1080
VIDEO_H     = 1920
FONT_SIZE   = 88
SIDE_MARGIN = 100
TEXT_WIDTH  = VIDEO_W - (SIDE_MARGIN * 2)
TEXT_BOTTOM_Y = VIDEO_H - 500

SILENCE_BUFFER = 0.5
OUTRO_HOLD     = 2.5
OUTRO_FADE_IN  = 0.7
OUTRO_FADE_OUT = 0.8

POWER_WORDS = {
    "silence","power","powerful","respect","weak","weakness",
    "discipline","stop","never","always","dominate","control",
    "strength","winner","loser","fear","dangerous","brutal",
    "truth","lies","fake","real","rich","poor","free","trap",
    "mind","focus","king","slave","elite","average","mediocre",
    "obsessed","obsession","money","success","failure","quit",
    "calm","chaos","war","peace","hunger","satisfy",
}

TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewNeural")
TTS_RATE  = os.environ.get("TTS_RATE",  "-12%")
TTS_PITCH = os.environ.get("TTS_PITCH", "-3Hz")
MAX_RETRY = int(os.environ.get("RENDER_MAX_RETRY", "3"))


# ── helpers ──────────────────────────────────────────────

def make_text_clip(text, font, font_size, color, method="label",
                   stroke_color=None, stroke_width=0, size=None):
    padded = text + "\n\n"
    kwargs = dict(text=padded, font=font, font_size=font_size, color=color,
                  stroke_color=stroke_color, stroke_width=stroke_width, method=method)
    if size is not None:
        kwargs["size"] = size
    return TextClip(**kwargs)


def contains_power_word(line: str) -> bool:
    return any(w in POWER_WORDS for w in re.findall(r"\w+", line.lower()))


async def _generate_voice(text: str, filename: str):
    comm = edge_tts.Communicate(text=text, voice=TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await comm.save(filename)


def build_outro_clips(voice_duration, total_duration):
    outro_start = voice_duration + SILENCE_BUFFER
    outro_dur   = total_duration - outro_start
    clips = []

    vignette = (ColorClip((VIDEO_W, VIDEO_H), color=(0,0,0), duration=outro_dur)
                .with_opacity(0.70).with_start(outro_start)
                .with_effects([vfx.FadeIn(OUTRO_FADE_IN), vfx.FadeOut(OUTRO_FADE_OUT)]))
    clips.append(vignette)

    ANCHOR = VIDEO_H // 2
    for y, is_line in [(ANCHOR-70, True),(ANCHOR-50, False),(ANCHOR+30, True)]:
        if is_line:
            clips.append(
                ColorClip((380,2),color=(255,255,255),duration=outro_dur)
                .with_position(("center",y)).with_start(outro_start)
                .with_effects([vfx.FadeIn(OUTRO_FADE_IN),vfx.FadeOut(OUTRO_FADE_OUT)])
            )

    name_clip = (make_text_clip("  ".join(PAGE_NAME.upper()),FONT_GEORGIA,74,"white")
                 .with_position(("center",ANCHOR-50)).with_start(outro_start)
                 .with_duration(outro_dur)
                 .with_effects([vfx.FadeIn(OUTRO_FADE_IN),vfx.FadeOut(OUTRO_FADE_OUT)]))
    clips.append(name_clip)

    tag_clip = (make_text_clip("philosophy for the modern mind",FONT_GEORGIA_I,32,(210,210,210))
                .with_position(("center",ANCHOR+50)).with_start(outro_start)
                .with_duration(outro_dur)
                .with_effects([vfx.FadeIn(OUTRO_FADE_IN+0.35),vfx.FadeOut(OUTRO_FADE_OUT)]))
    clips.append(tag_clip)
    return clips


def build_subtitle_clips(lines, voice_dur, sections):
    subtitle_clips = []
    hook_line   = sections.get("hook","").strip().split("\n")[0].strip() if sections else None
    engage_line = sections.get("engage","").strip().split("\n")[0].strip() if sections else None

    total_words    = sum(max(len(l.split()),1) for l in lines)
    line_durations = [(max(len(l.split()),1)/total_words)*voice_dur for l in lines]
    scale          = voice_dur / sum(line_durations)
    line_durations = [d*scale for d in line_durations]

    current_time = 0.0
    for i, line in enumerate(lines):
        wrapped  = textwrap.fill(line, width=24)
        is_hook  = bool(hook_line   and line.strip().startswith(hook_line[:20]))
        is_engage= bool(engage_line and line.strip().startswith(engage_line[:20]))
        has_power= contains_power_word(line)

        if is_hook:
            font_size,color,fade_in_dur,y_override = 118,"white",0.12,420
        elif is_engage:
            font_size,color,fade_in_dur,y_override = 96,(255,215,0),0.2,None
        elif has_power:
            font_size,color,fade_in_dur,y_override = FONT_SIZE+6,(255,230,50),0.3,None
        else:
            font_size,color,fade_in_dur,y_override = FONT_SIZE,"white",0.4,None

        txt = make_text_clip(wrapped,FONT_PATH,font_size,color,"caption",
                             "black",5 if not is_hook else 7,(TEXT_WIDTH,None))
        y_pos = y_override if y_override is not None else max(TEXT_BOTTOM_Y-txt.h,200)
        txt = (txt.with_position(("center",y_pos)).with_start(current_time)
               .with_duration(line_durations[i])
               .with_effects([vfx.FadeIn(fade_in_dur),vfx.FadeOut(0.3)]))
        subtitle_clips.append(txt)
        current_time += line_durations[i]
    return subtitle_clips


def build_background(selected_image, total_dur):
    bg = ImageClip(selected_image).with_duration(total_dur).resized(height=VIDEO_H)
    bg = bg.cropped(x_center=bg.w/2, width=VIDEO_W, height=VIDEO_H)
    def zoom_func(t):
        base   = 1 + 0.012*t
        pulse  = 0.022 if (5.0 < t < 5.35) else 0.0
        pulse2 = 0.015 if (12.0 < t < 12.3) else 0.0
        return base + pulse + pulse2
    return bg.with_effects([vfx.Resize(zoom_func)])


# ── Public API ───────────────────────────────────────────

def render_reel(reel_name: str, script: str, sections_json: str | None) -> str:
    """
    Renders a single reel. Returns output file path.
    Raises on failure (caller handles retry/status update).
    """
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    sections = json.loads(sections_json) if sections_json else None

    safe_name  = re.sub(r"[^\w]", "_", reel_name).lower()
    voice_file = os.path.join(OUTPUT_FOLDER, f"_tmp_voice_{safe_name}.mp3")
    output_path= os.path.join(OUTPUT_FOLDER, f"{safe_name}.mp4")

    log.info(f"[render] Starting: {reel_name}")

    # Voice
    asyncio.run(_generate_voice(script, voice_file))
    voice     = AudioFileClip(voice_file)
    voice_dur = voice.duration
    total_dur = voice_dur + SILENCE_BUFFER + OUTRO_HOLD
    log.info(f"[render] voice={voice_dur:.1f}s total={total_dur:.1f}s")

    # Background
    images = [f for f in os.listdir(STOCK_FOLDER)
              if f.lower().endswith((".jpg",".png",".jpeg"))]
    if not images:
        raise FileNotFoundError(f"No images found in STOCK_FOLDER={STOCK_FOLDER}")
    bg = build_background(os.path.join(STOCK_FOLDER, random.choice(images)), total_dur)

    overlay = ColorClip((VIDEO_W,VIDEO_H),color=(0,0,0),duration=total_dur).with_opacity(0.52)

    lines          = [l.strip() for l in script.split("\n") if l.strip()]
    subtitle_clips = build_subtitle_clips(lines, voice_dur, sections)
    outro_clips    = build_outro_clips(voice_dur, total_dur)

    music = (AudioFileClip(MUSIC_FILE).subclipped(0,total_dur)
             .with_volume_scaled(0.12)
             .with_effects([afx.AudioFadeOut(OUTRO_FADE_OUT+0.2)]))
    final_audio = CompositeAudioClip([voice.with_effects([afx.AudioFadeOut(0.5)]), music])

    final = (CompositeVideoClip([bg, overlay]+subtitle_clips+outro_clips, size=(VIDEO_W,VIDEO_H))
             .with_audio(final_audio).with_duration(total_dur)
             .with_effects([vfx.FadeOut(OUTRO_FADE_OUT)]))

    final.write_videofile(output_path, fps=30, codec="libx264",
                          audio_codec="aac", preset="fast")

    try:
        os.remove(voice_file)
    except OSError:
        pass

    log.info(f"[render] Done: {output_path}")
    return output_path
