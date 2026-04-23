import os
import sys
import subprocess
import tempfile

def run_ffmpeg(cmd):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("❌ FFmpeg command failed")
        sys.exit(1)

def main(folder_path):
    if not os.path.isdir(folder_path):
        print("❌ Invalid folder path")
        sys.exit(1)

    folder_name = os.path.basename(os.path.normpath(folder_path))
    output_file = f"voice_ref_{folder_name}.wav"

    # Get all mp4 files sorted
    mp4_files = sorted([
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".mp4")
    ])

    if not mp4_files:
        print("❌ No MP4 files found in folder")
        sys.exit(1)

    print(f"🎧 Found {len(mp4_files)} files. Processing...")

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_files = []

        # Step 1: Convert each mp4 → wav
        for i, mp4 in enumerate(mp4_files):
            wav_path = os.path.join(tmpdir, f"{i}.wav")
            cmd = [
                "ffmpeg",
                "-y",
                "-i", mp4,
                "-ac", "1",              # mono (optional)
                "-ar", "16000",         # sample rate (optional)
                wav_path
            ]
            run_ffmpeg(cmd)
            wav_files.append(wav_path)

        # Step 2: Create concat list file
        list_file = os.path.join(tmpdir, "concat.txt")
        with open(list_file, "w") as f:
            for wav in wav_files:
                f.write(f"file '{wav}'\n")

        # Step 3: Concatenate all wav files
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_file
        ]
        run_ffmpeg(cmd)

    print(f"✅ Done! Output file: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python voice_ref_tailor.py <folder_path>")
        sys.exit(1)

    main(sys.argv[1])