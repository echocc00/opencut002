# Material Analysis Stage Skill - Travel Domain

## Purpose
Analyze uploaded images to extract scene, emotion, and quality information.

## Output Contract
- images: list of {file, scene, emotion, score (1-5)}
- destination: guessed destination name
- scene_types: list of scene type strings

## Quality Rules
1. Every uploaded image must be analyzed
2. score must be 1-5 integer
3. destination should be derived from scene analysis

## Anti-Patterns
- DO NOT skip images
- DO NOT assign score without reasoning
