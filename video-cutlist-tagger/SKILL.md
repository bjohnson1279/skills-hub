---
name: video-cutlist-tagger
description: >-
  Parses complex filename cutpoint tags (start, stop, cut ranges), safely handles active/encoding
  video streams, integrates with local metadata servers for container tagging, and verifies full
  stream integrity before deleting or replacing original files.
---

# Video Cutlist Tagger

## Overview
Automates post-processing of recorded and clipped TV episodes. Accurately parses human-annotated filename tags (e.g. `(start at 0_00 to 22_00, cut 05_00 to 07_00, cut 12_00 to 14_00)`), produces clean concatenated clips, queries local metadata servers (`localhost:3000`, `localhost:8080`) when online to apply official metadata tags, and rigorously verifies audio/video streams before removing original untrimmed source files.

---

## Dependencies
- **FFmpeg & FFprobe**
- **Bash 4.0+** (`extglob`, `nullglob`)
- **jq**, **curl**, **bc**

---

## Core Capabilities & Architecture

### 1. Robust Cutpoint & Range Parsing
- **Parenthetical Tag Isolation**: Isolates tags inside parentheses `(...)` from episode titles to prevent false keyword matches (e.g., preventing *"A Fresh Start"* or *"Director's Cut"* from triggering premature handlers).
- **Keyword Precedence**: Checks for `cut` operations before `start` / `stop` / `from` so that complex composite tags (e.g. `(start at 0_00 to 22_00, cut 05_00 to 07_00)`) route to multi-segment cut extraction.
- **Timestamp Normalization**: Accepts `MM_SS`, `MM_SS.ms`, `HH_MM_SS`, `MM:SS`, or raw seconds and formats them into FFmpeg-compliant timestamps.

### 2. Resilient In-Progress / Encoding Stream Handling
Strict Bash mode (`set -euo pipefail` with `trap '...' ERR`) immediately crashes if `ffprobe` fails on a file currently being written by a background encoder.
- **Safe Probe**:
  ```bash
  get_duration() {
      local dur
      dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null) || true
      if [[ -n "$dur" && "$dur" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
          echo "$dur"
      else
          echo ""
      fi
  }
  ```
- If duration is empty or invalid, the script logs a warning and skips the file without crashing the execution loop.

### 3. Metadata Server Query & Tagging
- Tests local API endpoints with short connect timeouts (`--connect-timeout 2 --max-time 3`).
- On server response, extracts `title`, `description`, `synopsis`, `release`, `year`, `season_number`, `episode_sort`.
- If offline, falls back to parsed filename information.
- Applies tags losslessly via stream copying (`-c:v copy -c:a copy -movflags faststart`).

### 4. Deterministic Multi-Segment Clock Extraction (PBS Kids Pattern)
For shows adhering to fixed non-commercial broadcast clocks (e.g. *Daniel Tiger*), extract and concatenate the 3 core content segments without relying on brittle video heuristics:
```bash
# Part 1: Intro Theme (0:00 to 0:15.02)
partialClip "$1" "00:00:00.000" "00:00:15.020" "$join_file"
# Part 2: Main Episode (0:30 to 26:10.03)
partialClip "$1" "00:00:30.000" "00:26:10.030" "$join_file"
# Part 3: Closing Credits (27:10.09 to End)
partialClip "$1" "00:27:10.090" "$dur" "$join_file"
# Lossless Join
joinClips "$join_file" "$new_file_final"
```

### 5. EDL-Driven Dynamic Multi-Segment Clipping (The Simpsons Pattern)
For shows where commercial breaks vary per episode but are mapped to an EDL file (from `comskip_batch.sh` with custom harmonized profiles):
```bash
# Read EDL entries (start_seconds, end_seconds)
clip_start="00:00:00.000"
while read -r c_start c_end _; do
    [[ -z "$c_start" || -z "$c_end" ]] && continue
    # Convert seconds to HH:MM:SS.mmm
    f_start=$(format_seconds_to_timestamp "$c_start")
    f_end=$(format_seconds_to_timestamp "$c_end")

    partialClip "$1" "$clip_start" "$f_start" "$join_file"
    clip_start="$f_end"
done < "$edl_file"
# Append final segment from last commercial to end of video
partialClip "$1" "$clip_start" "$f_dur" "$join_file"
joinClips "$join_file" "$new_file_final"
```

### 6. Subprocess Stream Decoding Resilience
When reading subprocess output (e.g. `ffmpeg`, `ffprobe`, `comskip`) in Python or shell wrappers, stream transport packets and CEA-608 closed caption bytes can contain non-UTF-8 characters (e.g. `0xe9` / `é`). Always enforce `errors="replace"` and explicit `encoding="utf-8"`:
```python
proc = subprocess.run(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace"
)
```

### 7. Full Content Verification Prior to Deletion
Never delete an original source file without verifying the replacement:
1. **File Size**: Target file must exist and have non-trivial size (`>100 KB`).
2. **Stream Validation**: Video stream must be present and decodable (`ffprobe -select_streams v:0`).
3. **Duration Integrity**: Output duration must be positive and match expected cut length within tolerance ($\Delta < 2.0\text{s}$).

---

## Common Mistakes

1. **Strict Python `subprocess.run(text=True)` without `errors="replace"`**: Closed caption and progress output containing Latin-1 / binary stream bytes throws fatal `UnicodeDecodeError`. Always pass `errors="replace"`.
2. **Unsafe Temporary File Removal**: Calling `rm "$join_file"` without `-f` when an early return occurs causes `rm` to fail on non-existent files, terminating strict Bash scripts.
3. **Matching Entire Filename for Keywords**: Matching `*cut*` against `$filename` rather than the parenthetical parameter substring erroneously triggers on episode titles like *"The Shortcut"* or *"A Cut Above"*.
4. **Deleting Before Verification**: Deleting source files immediately after an FFmpeg command without checking stream validity and duration can result in unrecoverable data loss if FFmpeg writes a truncated file.
