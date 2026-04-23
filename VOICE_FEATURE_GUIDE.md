# Voice Selection Feature - User Guide

## 🎙️ What's New

You now have the ability to choose different speaker voices for your reels! Each voice creates a unique emotional impact on your viewers.

### Why Use Different Voices?

- **Variety**: Keep content fresh by alternating between voices
- **Emotional Impact**: Deep calm voices vs. energetic voices set different tones
- **Brand Building**: Consistent voice creates recognition and trust
- **Viewer Engagement**: Different audiences connect with different voices

---

## 🚀 Quick Start

### Step 1: Add Your First Voice

1. **Record or source** a voice reference file (3-10 seconds)
   - Format: WAV, MP3, or FLAC
   - Content: Clear speech (e.g., "My name is [Name], and I'm here to share something important")
   - Quality: Clear audio, no background noise

2. **Place it** in the `voices/` directory at the root of your project:
   ```
   project_root/
   └── voices/
       └── voice_ref_cilian_murphy.wav
   ```

3. **Refresh** the portal (Ctrl+R or Cmd+R)

4. **Done!** Your voice now appears in the dropdown

### Step 2: Use It When Creating Reels

1. Go to **Submit** tab
2. Scroll to **SPEAKER VOICE** section
3. Select your voice from the grid
4. Write your reel content
5. Click **Queue** - all reels use this voice

---

## 📝 Voice Naming Convention

Name your files like this:

```
voice_ref_[speaker_name].wav
```

**Examples:**
- `voice_ref_cilian_murphy.wav` → displays as "Cilian Murphy"
- `voice_ref_morgan_freeman.wav` → displays as "Morgan Freeman"  
- `voice_ref_deep_calm.wav` → displays as "Deep Calm"
- `voice_ref_energetic_female.wav` → displays as "Energetic Female"

The system automatically converts underscores to spaces and title-cases the display name.

---

## 🎤 Recording Tips

### For Best Results

✅ **DO:**
- Use clear, natural speech
- Speak at normal conversational volume
- Record in a quiet room
- Use a good quality microphone
- Keep it 3-10 seconds long
- Speak with personality (this is your brand voice!)

❌ **DON'T:**
- Use robotic or monotone speech
- Record in noisy environments
- Make it too short (<1 second) or too long (>15 seconds)
- Use background music or sound effects
- Use multiple speakers in one file

### Example Phrases

Choose phrases that showcase the voice's character:

**Calm/Authoritative:**
> "Every moment is an opportunity to become stronger. Choose discipline."

**Energetic:**
> "Rise up! Push through the pain. Your best is yet to come!"

**Mysterious:**
> "Some truths are only discovered in silence..."

**Professional:**
> "Let me share a perspective that might change how you see things."

---

## 🎯 Using the Portal

### The Voice Selector Interface

1. **Grid Layout** - All available voices shown as buttons
2. **Visual Feedback** - Selected voice shows a checkmark
3. **Info Box** - Shows which voice is selected
4. **AI Default** - Falls back to standard voice if needed

### How Voices Affect Output

Each voice maintains its character across all sections:
- **Hook**: Attention-grabbing with emotion
- **Conflict**: Building tension
- **Shift**: Perspective change
- **Punch**: Maximum impact
- **Engage**: Call to action

Different voices will emphasize these moments differently.

---

## 🔧 Advanced: Environment Variables

If you have a global default voice, set it:

```bash
export TTS_VOICE_REF="/path/to/my/default/voice.wav"
```

Portal selections will **override** this default.

---

## ❓ FAQ

**Q: How many voices can I add?**
A: Unlimited! Add as many as you want.

**Q: Can I use celebrity voice clones?**
A: Yes, if you have the rights. Ensure proper licensing.

**Q: What if my voice doesn't sound right?**
A: Try a different recording, ensure quality, check file format.

**Q: Can I switch voices between reels?**
A: Not yet - all reels in a batch use the same voice. Future feature could allow per-reel selection.

**Q: What's the file size limit?**
A: No hard limit, but keep files under 1MB for best performance.

**Q: Can I update a voice file?**
A: Yes, just replace it in the `voices/` directory and refresh.

---

## 📊 Voice Impact Tracking

After using different voices, you can:
1. Check YouTube analytics to see which voices get more engagement
2. A/B test by publishing similar content with different voices
3. Track viewer retention by voice type
4. Adjust strategy based on audience response

---

## 🛠️ Troubleshooting

### Voice doesn't appear in dropdown?

1. Check file is in `voices/` directory
2. Verify filename starts with `voice_ref_`
3. Check file format (WAV, MP3, or FLAC)
4. Try refreshing portal (Ctrl+R)
5. Check browser console for errors (F12)

### Voice sounds different than expected?

1. Voice may sound different based on the text being spoken
2. Try a different voice reference recording
3. Ensure source audio is clear and natural
4. Different section types (hook vs. punch) have different emotion settings
5. The TTS model may interpret the prompt differently than expected

### Voice not being used?

1. Verify voice file exists in `voices/` directory
2. Check job was created with correct voice
3. Check rendering logs for errors
4. Verify file permissions (readable by app process)

---

## 💡 Pro Tips

1. **Start Simple**: Try 2-3 voices before expanding
2. **Test Early**: Submit a test reel with each new voice before mass production
3. **Match Your Brand**: Pick voices that reflect your channel's vibe
4. **Backup Your Voices**: Keep originals safe, no licensing issues then
5. **Document**: Note which voices resonate with your audience

---

## 📚 More Info

For technical details, see:
- `voices/README.md` - Detailed implementation guide
- `portal/src/components/ui/VoiceSelector.jsx` - Component details
- Backend: `app/renderer.py` - TTS rendering logic

---

**Questions?** Check the README files or review the code comments.

**Ready to add your first voice?** Head to the `voices/` directory and follow the naming convention!
