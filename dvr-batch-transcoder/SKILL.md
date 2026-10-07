---
name: dvr-batch-transcoder
description: >-
  Orchestrates bounded parallel video transcoding queues (e.g. 720p/1080p, crop filters, x264 CRF),
  aspect ratio handling, and automated post-encode commercial detection hooks.
---

# DVR Batch Transcoder

## Overview
Provides robust multi-file transcode queue management for TV libraries and DVR archives. Enforces strict job-slot limits (e.g. `MAX_JOBS=2`) to avoid CPU/memory saturation, manages downscaling and crop filtergraphs, and automatically triggers post-encode commercial analysis to generate companion reports and cutlists immediately upon encode completion.

---

## Dependencies
- **FFmpeg & FFprobe**
- **Comskip**
- **Bash 4.0+**
- **bc**

---

## Core Capabilities & Architecture

### 1. Bounded Parallel Job Management
Running unlimited parallel `ffmpeg` instances with `veryslow` presets or high resolutions triggers out-of-memory errors and CPU starvation.
- Use a subshell tracking loop with controlled concurrency:
  ```bash
  MAX_JOBS=2
  job_count=0
  for file in "${files[@]}"; do
      (
          encode_file "$file" "$out_file"
      ) &

      job_count=$((job_count + 1))
      if [[ "$job_count" -ge "$MAX_JOBS" ]]; then
          wait -n 2>/dev/null || wait
          job_count=$((job_count - 1))
      fi
  done
  wait
  ```

### 2. Standardized Transcode Presets
- **720p Downscaling**: `-vf "scale=-2:720" -c:v libx264 -crf 18 -preset veryslow -c:a copy`
- **4:3 Aspect Restoration & Cropping**: `-vf "crop=W:H:X:Y" -c:v libx264 -crf 20 -preset veryslow -pix_fmt yuv420p -movflags faststart`

### 3. Automated Post-Encode Commercial Detection Hook
Upon successful encoding of each individual video, the pipeline immediately runs Comskip against the newly generated file:
1. Selects channel profile based on show title (e.g. RewindTV INI for *Head Of The Class*, *Growing Pains*, *Who's The Boss* vs Default INI for others).
2. Runs Comskip in a dedicated working directory.
3. Parses cut points and computes exact frame numbers and timestamps using stream FPS.
4. Generates companion `<filename>.commercials.txt` containing a formatted summary table.

**Example Implementation (Dynamic Routing & Backgrounding):**
```bash
run_comskip() {
    local file_path="$1"
    local show_name="$2"
    local output_dir="$(dirname "$file_path")"
    local base_name="$(basename "${file_path%.*}")"
    
    local show_name_lower="${show_name,,}"
    local ini_file="/etc/comskip/comskip.ini"
    local dvr_dir="${DVR_DIR:-/etc/comskip}"
    
    if [[ "$show_name_lower" == *"head of the class"* || "$show_name_lower" == *"growing pains"* || "$show_name_lower" == *"who's the boss"* ]]; then
        [ -f "$dvr_dir/rewindtv.ini" ] && ini_file="$dvr_dir/rewindtv.ini"
    elif [[ "$show_name_lower" == *"abbott elementary"* || "$show_name_lower" == *"the rookie"* || "$show_name_lower" == *"shark tank"* ]]; then
        [ -f "$dvr_dir/network_abc.ini" ] && ini_file="$dvr_dir/network_abc.ini"
    elif [[ "$show_name_lower" == *"daniel tiger"* ]]; then
        [ -f "$dvr_dir/pbs_kids.ini" ] && ini_file="$dvr_dir/pbs_kids.ini"
    fi

    # Run in background (script should call `wait` at the end)
    comskip --threads=8 --output="$output_dir" --output-filename="$base_name" --ini="$ini_file" "$file_path" > "${output_dir}/${base_name}_comskip.log" 2>&1 &
}
```

---

## Common Mistakes

1. **Unbounded Subshell Forking**: Relying on unconstrained background `(&)` processes without a slot counter exhausts system resources.
2. **Missing `faststart` Atom Placement**: Omitting `-movflags faststart` places the MP4 `moov` atom at the end of the file, delaying playback and stream verification.
3. **Hardcoding Core Count Without Cap**: Setting `MAX_JOBS=$(nproc)` on high-core machines (e.g. 16-32 cores) spawns 16-32 simultaneous heavy `libx264 veryslow` encodes, leading to thermal throttling and disk I/O bottlenecks. Cap `MAX_JOBS` explicitly (default to 2 or 4).
