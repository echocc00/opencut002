# Image Matching Stage Skill - Travel Domain

## Purpose
Match copywriting paragraphs to source images using AI semantic matching.

## Output Contract
- Each paragraph must be matched to an image filename
- Fallback chain: AI match -> local -> Pexels -> AI generate -> empty

## Quality Rules
1. Every paragraph must have an image (or empty string for no-image)
2. Same image should not be used for >2 consecutive paragraphs

## Anti-Patterns
- DO NOT leave paragraphs without image assignment
