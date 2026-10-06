"""Convert a raw recording (mp3/m4a/wav/...) into the site's media + a 16 kHz analysis WAV.

Usage:
    python tools/prepare_audio.py recording.m4a beeri-9a8bc7

Writes:
    <student>/media/full.oga   — Ogg/Opus mono, what the site plays
    <student>/media/_full16k.wav — 16 kHz mono PCM, used by align.py / build_env.py (not deployed)
"""
import os
import subprocess
import sys


def main():
    src, student = sys.argv[1], sys.argv[2]
    media = os.path.join(student, "media")
    os.makedirs(media, exist_ok=True)
    # light cleanup: drop rumble, normalise loudness — keeps the chant natural
    af = "highpass=f=70,loudnorm=I=-18:TP=-1.5:LRA=11"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-af", af,
                    "-c:a", "libopus", "-b:a", "48k", os.path.join(media, "full.oga")], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(media, "full.oga"), "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", os.path.join(media, "_full16k.wav")], check=True)
    print("ok ->", media)


if __name__ == "__main__":
    main()
