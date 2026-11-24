
from pathlib import Path
import csv

source = Path("data/LibriSpeech/dev-clean")
audio_folder = Path("datasets/sample_audio")
output_file = audio_folder / "metadata.csv"

# Read all reference transcripts
transcripts = {}

for transcript_file in source.rglob("*.trans.txt"):
    with transcript_file.open(encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                transcripts[parts[0]] = parts[1]

# Match existing audio files with their transcripts
audio_files = sorted(audio_folder.glob("*.flac"))
matched = []

for audio in audio_files:
    utterance_id = audio.stem

    if utterance_id in transcripts:
        matched.append([
            audio.name,
            utterance_id,
            transcripts[utterance_id]
        ])

# Verify all files have matching transcripts
if len(matched) != len(audio_files):
    raise RuntimeError(
        f"Only {len(matched)} of {len(audio_files)} audio files matched!"
    )

# Create metadata CSV
with output_file.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["file", "utterance_id", "transcript"])
    writer.writerows(matched)

print(f"SUCCESS: {len(matched)} transcripts saved!")
print(f"File created: {output_file.resolve()}")
