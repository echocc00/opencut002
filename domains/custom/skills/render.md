# Render Stage Skill - Travel Domain

## Purpose
Render final video using Remotion (React components -> frames -> FFmpeg encode).

## Output Contract
- video_path: path to final MP4
- duration: actual video duration
- quality_report: post-render validation results

## Quality Rules
1. Video must pass post-render self-review (ffprobe + frame sampling + audio analysis)
2. If quality check fails, video is not presented to user
