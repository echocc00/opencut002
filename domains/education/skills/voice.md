# voice Stage Skill - Travel Domain

## Purpose
Execute the voice stage of the travel video pipeline.

## Output Contract
- Output must be valid JSON
- Must include all required fields per stage contract

## Quality Rules
1. Output must be non-empty
2. Must reference upstream data appropriately

## Anti-Patterns
- DO NOT generate empty output
- DO NOT ignore upstream context

## Domain-Specific Guidance
- 文旅领域voice阶段需要结合景点特色和用户情感
