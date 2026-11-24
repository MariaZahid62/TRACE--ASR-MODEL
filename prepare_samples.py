
from pathlib import Path
import shutil
import csv
import sys

# Change this to your extracted test-clean folder
SOURCE = Path(sys.argv[1])

# Destination inside TRACE
DEST = Path("datasets/sample_audio")
DEST.mkdir(parents=True, exist_ok=True)

# Read all LibriSpeech reference transcripts
transcripts = {}

for transcript_file in SOURCE.rglob("*.trans.txt"):
    with open(transcript_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" ", 1)
            if len(parts) == 2:
                transcripts[parts[0]] = parts[1]

# Select audio files that have matching transcripts
audio_files = sorted(SOURCE.rglob("*.flac"))

selected = [
    audio for audio in audio_files
    if audio.stem in transcripts
][:100]

if len(selected) < 100:
    raise RuntimeError(
        f"Only {len(selected)} matching files found."
    )

# Copy audio and save reference transcripts
manifest = DEST.parent / "transcripts.csv"

with open(manifest, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["audio_file", "reference_transcript"])

    for audio in selected:
        destination = DEST / audio.name
        shutil.copy2(audio, destination)

        writer.writerow([
            audio.name,
            transcripts[audio.stem]
        ])

print(f"Successfully selected {len(selected)} audio files.")
print(f"Audio folder: {DEST}")
print(f"Transcripts: {manifest}")