---
name: dvr-commercial-pipeline
description: >-
  Standardizes broadcast commercial detection (Comskip), channel-specific profile tuning
  (RewindTV/AntennaTV syndicated vs ABC/CBS/NBC network broadcasts), dynamic framerate
  conversions (29.97 vs 59.94 fps), and automated EDL/TXT report aggregations.
---

# DVR Commercial Pipeline

## Overview
Commercial detection on broadcast and OTA DVR recordings presents unique challenges across networks:
- **Syndicated 80s/90s Sitcoms (RewindTV, AntennaTV)**: Fast cold opens (~60s), credit tags (~25s), persistent channel watermark bugs, and long subchannel commercial breaks (3.5m - 4.5m).
- **Network Broadcasts (ABC, CBS, NBC, FOX)**: High progressive framerates (720p @ 59.94 fps), 5.1 Surround Sound AC3 to 2.0 Stereo switching during breaks (`cut_on_ac_change`), animated translucent logos, and short 1-2 frame black transitions.

This skill standardizes Comskip profile tuning, dynamic stream framerate detection via `ffprobe`, multi-format cutlist parsing (`.edl` and `.txt`), multi-threaded decode acceleration, and aggregated CSV/text reporting.

---

## Dependencies
- **Comskip** (0.82+ with FFmpeg decode backend)
- **FFmpeg / FFprobe**
- **Python 3.8+** / **Bash 4.0+**
- **bc**, **jq**

---

## Channel & Network Profile Tuning

### 1. RewindTV / AntennaTV / Syndicated Sitcoms (`rewindtv.ini`)
**Target Shows**: *Head Of The Class*, *Growing Pains*, *Who's The Boss*
```ini
[Main]
detect_method=255
always_keep_first_seconds=30
always_keep_last_seconds=10
min_show_segment_length=20
min_commercial_break=45
max_commercialbreak=600
max_commercial_size=600

# Do not penalize longer subchannel commercial breaks
excessive_length_modifier=1.0
length_strict_modifier=1.0
length_nonstrict_modifier=1.0

# Logo Detection & Promo Filtering
connect_blocks_with_logo=0
logo_threshold=0.80
punish_no_logo=1
logo_present_modifier=0.01
delete_logo_file=1
shrink_logo=5

# Black Frame & Brightness Thresholds
max_brightness=65
test_brightness=40
max_avg_brightness=30
validate_uniform_frame=1
validate_scenechange=1

# Output Formats
output_edl=1
output_ffmeta=1
output_vdr=1
```

### 2. Network Broadcasts & ABC Shows (`network_abc.ini`)
**Target Shows**: *Abbott Elementary*, *Celebrity Family Feud*, *Celebrity Jeopardy*, *Celebrity Wheel of Fortune*, *The Rookie*, *The Great Christmas Light Fight*, *Shark Tank*
```ini
[Main]
detect_method=255
thread_count=8

# 1. Show Segmentation & Cold Open Protection
always_keep_first_seconds=220
always_keep_last_seconds=30
min_show_segment_length=180
min_commercial_size=60
min_commercial_break=60
min_commercialbreak=60
max_commercialbreak=240
max_commercial_break=240
max_commercial_size=240

# 2. Black Frame & Audio Detection (720p 59.94 fps)
max_brightness=60
test_brightness=35
max_avg_brightness=25
min_black_frames_for_break=2
validate_uniform_frame=1
validate_scenechange=1
cut_on_ac_change=1

# 3. Logo Detection (Relaxed)
logo_threshold=0.75
punish_no_logo=0
logo_present_modifier=0.1
delete_logo_file=1
shrink_logo=5
connect_blocks_with_logo=1

### 3. Public Broadcasting & PBS Kids (`pbs_kids.ini` / Broadcast Clock)
**Target Shows**: *Daniel Tiger's Neighborhood*, PBS Kids series
Public broadcasting lacks traditional commercial breaks but follows a strict broadcast clock:
- **Intro Theme**: `00:00.00 – 00:15.02` *(Keep)*
- **Sponsor Billboard**: `00:15.02 – 00:30.00` *(15s Cut)*
- **Main Episode**: `00:30.00 – 26:10.03` *(Keep)*
- **PBS Promos / Previews**: `26:10.03 – 27:10.09` *(60s Cut)*
- **Closing Credits**: `27:10.09 – End` *(Keep)*

Because PBS station watermarks persist across ~90% of the broadcast and animated scene transitions lack pitch-black frames, standard logo/black heuristics merge sponsor spots into the main show. Use deterministic clock generation or disable logo merging:
```ini
[Main]
detect_method=119
thread_count=8
ignore_logo=1
connect_blocks_with_logo=0
punish_no_logo=0

# Timing bounds for 15s sponsor & 60s promo
always_keep_first_seconds=10
always_keep_last_seconds=0
min_show_segment_length=10
min_commercial_size=10
min_commercial_break=10
max_commercialbreak=120
excessive_length_modifier=1.0

# Closed Caption Transitions
cut_on_cc_change=1
cc_wrong_modifier=10
punish_no_cc=1

# Output Formats
output_edl=1
output_ffmeta=1
output_vdr=1
```

### 4. Fox Broadcasts & Closing Credit / Epilogue Preservation (`the_simpsons.ini`)
**Target Shows**: *The Simpsons*, Fox prime-time animated series
Fox broadcasts present unique credit and watermark behaviors:
- **Delayed Watermark Fade-In**: Fox delays fading in the corner station watermark for ~17 seconds after commercial breaks conclude (e.g., show resumes at `10:06.12` while the logo only fades in at `10:23.00`). Strict logo heuristics extend Break 1 into actual episode footage.
- **Closing Executive Producer Credits**: A 7-second credits screen (e.g., Matt Groening / James L. Brooks at `26:43 – 26:51`) displays white text over black without a station bug.
- **Post-Commercial Epilogues & Vanity Cards**: Following Break 3, episodes feature a short epilogue scene (`29:18 – 29:58`), the Gracie Films vanity card (`29:58 – 30:02`), and the 20th Television Animation vanity card (`30:02 – 30:05`). Because the station watermark is omitted during epilogues and vanity cards, standard Comskip bridges Break 3 across the entire final sequence.

**INI Profile & Harmonization**:
```ini
detect_method=255
verbose=0
min_show_segment_length=125
min_commercial_break=45
max_commercialbreak=360
padding=0
max_silence=50
delete_logo_file=1
output_edl=1
output_ffmeta=1
output_vdr=1
output_framearray=0
```

**Post-Processing Harmonizer**:
Run targeted FFmpeg `blackdetect` filters across known transition windows:
1. **Break 1 Return** (`600s – 615s`): Find `black_end` to snap the return from `10:23` back to `10:06.12`.
2. **Break 3 Start** (`1600s – 1620s`): Find `black_end` to move commercial start past the 7-second producer credits screen (`26:51.38`).
3. **Break 3 End** (`1750s – 1765s`): Find `black_start` to snap the commercial end before the epilogue scene and vanity cards (`29:18.52`).

---

## Core Principles & Workflow

### 1. Dynamic Framerate Calculation
Never assume a fixed 29.970 fps across all TV broadcasts. Query the stream properties:
```bash
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE")
# Convert fractions (e.g. 60000/1001 -> 59.940, 30000/1001 -> 29.970)
```
Convert frames to timestamp:
$$\text{Seconds} = \frac{\text{Frame}}{\text{FPS}}$$

### 2. Dual Cutlist Format Support
- **`.edl` Format**: `<start_seconds>\t<end_seconds>\t<action_type>` (0 = commercial).
- **`.txt` Format**: Line 1 contains header (`FILE PROCESSING COMPLETE ... AT <FPS_INT>`), followed by `<start_frame>\t<end_frame>`.

### 3. Multi-Threading & Software Decode Optimization
High framerate 720p @ 59.94 fps recordings contain 108,000+ frames per 30 minutes. Always supply `--threads=4` or `--threads=8` to prevent process timeouts.

### 4. Non-Commercial Deterministic Clock Pattern
When processing public broadcasting (PBS Kids) where persistent station bugs defeat heuristics, apply deterministic cutpoints directly to the `.edl` cutlist:
- Break 1: `15.02s` to `30.00s`
- Break 2: `1570.03s` to `1630.09s`

---

## Common Mistakes

1. **Hardcoding 29.97 fps**: Converting 59.94 fps frame numbers with a 29.97 fps divisor cuts commercial timestamps in half, resulting in misaligned trims.
2. **Aggressive `always_keep_first_seconds` on PBS**: Setting `always_keep_first_seconds=30` prevents Comskip from flagging the 15-second sponsor bumper (`0:15 - 0:30`). Use `10` or lower.
3. **Relying on Logo Absence on PBS Kids**: The circular PBS Kids logo is present throughout sponsor and promo spots; using `connect_blocks_with_logo=1` welds the entire episode into one continuous block.
4. **Missing Output Directories**: Comskip terminates with fatal errors if the directory specified by `--output` does not exist prior to invocation. Always run `mkdir -p "$OUTPUT_DIR"`.
5. **Expecting `.edl` Without INI**: Without `output_edl=1` in the configuration file, Comskip defaults solely to writing `.txt` frame lists.
