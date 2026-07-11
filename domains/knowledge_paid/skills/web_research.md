# Web Research Stage Skill - Travel Domain

## Purpose
Search trending topics and viral angles before topic generation.

## Input
- Material analyses (destination, scene_types)
- Search queries from domain config

## Output Contract
- hot_topics: list of 3-5 trending topics
- angle_suggestions: list of 2-3 content angles
- avoid_angles: list of overused angles to avoid
- differentiation: description of unique opportunity

## Quality Rules
1. At least 3 hot topics must be generated
2. At least 2 angle suggestions
3. Avoid angles must reference actual search findings
4. Differentiation must be specific to the destination

## Anti-Patterns
- DO NOT generate generic topics not related to search results
- DO NOT ignore avoid_angles from search data

## Domain-Specific Guidance
- 文旅调研要关注"季节性"和"时效性"
- 热门话题要结合平台特性（抖音/小红书/视频号）
- 避坑角度要具体（如"不要再做XX攻略了"）
