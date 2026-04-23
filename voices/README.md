# Voice References for ReelForge

This directory contains speaker voice reference files used for text-to-speech (TTS) synthesis. Each voice file is used as an audio prompt to guide the Chatterbox TTS model to match a specific speaker's tone and characteristics.

## Adding New Voices

### File Format & Requirements

- **Format**: WAV, MP3, or FLAC
- **Suggested Duration**: 3-10 seconds
- **Sample Rate**: 16kHz, 22kHz, or 44.1kHz
- **Content**: Clear speech in the target speaker's voice - a short phrase works well (e.g., "My name is [Name], and I'm here to share something important with you")

### Naming Convention

Use the following naming pattern for clarity:

```
voice_ref_[speaker_name].wav
```

**Examples:**
- `voice_ref_cilian_murphy.wav` - displays as "Cilian Murphy"
- `voice_ref_morgan_freeman.wav` - displays as "Morgan Freeman"
- `voice_ref_deep_calm.wav` - displays as "Deep Calm"
- `voice_ref_energetic_female.wav` - displays as "Energetic Female"

## How It Works

1. **Voice Selection**: When creating reels in the portal, users select a voice from the "SPEAKER VOICE" dropdown
2. **Processing**: The selected voice file is passed to Chatterbox TTS as an audio prompt
3. **Synthesis**: The TTS model generates speech that mimics the selected speaker's characteristics
4. **Impact**: Different voices create different emotional impacts on viewers

## Best Practices

### Recording or Sourcing Voice Files

- **Quality**: Use clear, high-quality audio without background noise
- **Consistency**: The voice should be consistent and natural
- **Length**: Typically 3-10 seconds is optimal
- **Content**: Record a meaningful phrase, not just random words
- **Licensing**: Ensure you have rights to use the voice (for your own voice, this is automatic)

### Example Voice Phrases

Choose phrases that demonstrate the voice's character:

- **Calm/Authoritative**: "Every moment is an opportunity to become stronger. Choose discipline."
- **Energetic**: "Rise up! Push through the pain. Your best is yet to come!"
- **Mysterious**: "Some truths are only discovered in silence..."
- **Professional**: "Let me share a perspective that might change how you see things."

### How to Add a Voice

1. **Record/Source** a voice reference file (WAV, MP3, or FLAC)
2. **Place it** in this `voices/` directory
3. **Name it** following the `voice_ref_[name].wav` pattern
4. **Restart** the ReelForge application (or just refresh the portal)
5. **Select** the new voice from the dropdown when creating reels

## Voice Characteristics Impact

Different voices will:
- **Affect viewer engagement**: Familiar or celebrity voices may increase engagement
- **Set emotional tone**: Deep calm voices vs. energetic voices
- **Build brand consistency**: Using the same voice across videos builds recognition
- **Diversify content**: Alternating voices can keep content fresh for audiences

## Troubleshooting

### Voice not appearing in the list?

- Ensure file is in the correct format (WAV, MP3, or FLAC)
- Check filename follows the `voice_ref_*.wav` pattern
- Verify the file path is exactly: `/project_root/voices/voice_ref_[name].[ext]`
- Try refreshing the portal (Ctrl+R or Cmd+R)

### Voice sounds different than expected?

- The TTS model's interpretation varies based on the base text
- Try different voice reference lengths (3-10 seconds)
- Ensure source voice is clear and natural
- The same voice may sound different depending on section emotion settings (hook, punch, shift, etc.)

## Examples Included

The system comes with:
- **AI Default**: Standard Chatterbox voice (no reference file needed)
- **Your Custom Voices**: Any voices you add to this directory

## Advanced Configuration

You can also set a global default voice via environment variable:

```bash
export TTS_VOICE_REF="/path/to/default/voice.wav"
```

Individual voice selections in the portal will override this default.

---

**Last Updated**: April 2026
**System**: ReelForge v3 Beast Mode
