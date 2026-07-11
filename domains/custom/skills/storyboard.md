# Storyboard Stage Skill - Travel Domain

## Purpose
Generate storyboard segments from copywriting paragraphs and matched images.

## Input
- Copywriting paragraphs (text, target_duration, image_hint, highlight_ref)
- Matched images per paragraph
- TTS audio with word-level timestamps

## Output Contract
Each segment MUST include:
- index: segment number
- image: image filename
- actual_duration: duration in seconds (from TTS)
- time_start: start time in video
- subtitle: subtitle text for this segment
- transition: transition type to next segment
- subtitle_words: word-level timestamps for subtitle

## Quality Rules
1. Every paragraph must have at least 1 segment
2. actual_duration must match TTS audio duration
3. time_start must be cumulative (first segment starts at 0)
4. Transition types: crossfade, slide, zoom, cut
5. First segment must have high visual impact

## Anti-Patterns
- DO NOT use same image for consecutive segments without AB-split
- DO NOT set actual_duration > 6 seconds (split into multiple segments)
- DO NOT use "cut" transition for the first segment

## Domain-Specific Guidance
- 文旅分镜要有"景别变化"：全景->中景->特写交替
- Ken Burns效果参数：缩放幅度10-20%，平移幅度不超过画面50%
- 转场时长：crossfade 0.4s, slide 0.3s, zoom 0.5s
