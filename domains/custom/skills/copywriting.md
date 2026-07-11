# Copywriting Stage Skill - Travel Domain

## Purpose
Generate 4-8 paragraph script based on confirmed topic direction and highlight selection.

## Input
- Topic direction (name, hook, psychology, why_work)
- Selected highlights (ids, names, presentation_style)
- Image analyses (scene, emotion, score per image)
- Web research brief (if available)

## Output Contract
Each paragraph MUST include:
- text: 15-30 Chinese characters
- target_duration: 2.5-5.0 seconds
- image_hint: source image filename
- highlight_ref: which highlight ID this paragraph embodies
- emotion_tone: emotional tone label

## Quality Rules
1. Total paragraphs: 4-8 (fit 30-60s total)
2. First paragraph MUST embody selected hook style
3. Each selected highlight MUST appear in at least 1 paragraph
4. No paragraph > 30 chars without image change
5. Emotional arc: hook -> build -> peak -> resolve

## Anti-Patterns
- DO NOT generate paragraphs without highlight_ref
- DO NOT use same image for >2 consecutive paragraphs
- DO NOT write paragraphs that just describe the image
- DO NOT exceed 8 paragraphs for videos under 60s

## Domain-Specific Guidance
- 文旅文案要有画面感：用感官词（看见/听见/闻到）
- 避免导览式平铺：不是"这里是XX，那里是YY"
- 情感共鸣优先：让读者想"我也想去看看"
- 开头3秒必须制造好奇或冲击
