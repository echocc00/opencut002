# TTS Stage Skill - Travel Domain

## Purpose
Generate voice narration from copywriting text using Edge-TTS or MiniMax.

## Output Contract
- audio_path: path to generated WAV file
- word_timestamps: list of {word, start, end} from WhisperX

## Quality Rules
1. Audio duration must match expected duration from copywriting
2. Word timestamps must cover the full audio duration
