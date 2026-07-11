# Topic Stage Skill - Travel Domain

## Purpose
Generate 2-3 topic directions based on material analysis and web research.

## Input
- Material analyses (images, destination, scene_types)
- Web research brief (hot_topics, angle_suggestions, avoid_angles)

## Output Contract
Each direction MUST include:
- name: topic name (5-15 chars)
- hook: opening hook style (suspense/contrast/impact/emotional)
- psychology: why this works psychologically
- ref_type: reference type (viral/educational/emotional)
- why_work: why this direction will perform well

## Quality Rules
1. Generate exactly 2-3 directions
2. Each direction must have a different hook style
3. At least 1 direction must reference web research hot topics
4. Avoid angles from web research avoid list

## Anti-Patterns
- DO NOT generate generic topics like "XX旅游攻略"
- DO NOT use the same hook style for all directions
- DO NOT ignore web research findings

## Domain-Specific Guidance
- 文旅选题要找到"独特视角"：不是"去哪里"而是"为什么去"
- 爆款文旅视频的核心是"发现感"：让用户觉得学到了新东西
- 参考爆款模式：悬念揭秘、反差对比、情感共鸣、知识科普
