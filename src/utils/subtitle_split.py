"""屏级字幕自适应切分（v0.6.1，port 自 v0.5.4 audit + 修复）。

把一段文案切成 <= hard_max 字/屏（理想 8-14 字，硬上限 16），按标点切短语 +
贪心打包。每屏时长由 forced_align 真实逐字时间戳驱动（不是造假均分）。

与 v0.5.4 audit 的关键差异（修复评审 CRITICAL bug）：
- `compute_screen_durations` 改用 **汉字位置映射**（forced_align 只产汉字时间戳，
  标点/数字/英文无时间戳）。旧版映射所有非空格字符 -> hanzi-only 时间戳下错位，
  且 `char_cursor` 越界时静默回退 index 0（数据损坏）。
- 加边界校验：汉字数 != 时间戳数时整段均分 + log 警告（不静默崩）。
- 屏边界用每屏首字时间戳做连续分区，首屏起 0、末屏止 audio_duration，无间隙。

详见 docs/subtitle-screen-design.md（v0.5.4）+ CLAUDE.md #19。
"""
from __future__ import annotations

import logging
import re
from typing import List

log = logging.getLogger(__name__)


# 标点/空白等短语边界。用 chr() 构造避免编码问题（port 自 v0.5.4）。
PUNCT_CN_FULL = chr(0x3002) + chr(0xFF0C) + chr(0xFF01) + chr(0xFF1F) + chr(0xFF1B) + chr(0xFF1A) + chr(0x3001)
PUNCT_EN_HALF = "," + "." + "!" + "?" + ";" + ":"
PUNCT_BLANK = " " + chr(9) + chr(10) + chr(13)
PUNCT_QUOTE = chr(39) + chr(34) + chr(0x201C) + chr(0x201D) + chr(0x2018) + chr(0x2019)
PUNCT_BRACKET = ("(" + ")" + "[" + "]" + "<" + ">" + chr(0x300C) + chr(0x300D)
                 + chr(0x300E) + chr(0x300F) + chr(0x3010) + chr(0x3011) + chr(0x300A) + chr(0x300B))
PHRASE_BREAK = set(PUNCT_CN_FULL + PUNCT_EN_HALF + PUNCT_BLANK + PUNCT_QUOTE + PUNCT_BRACKET)

# 末屏太少时合并到上一屏的阈值
LAST_SCREEN_MIN_CHARS = 4

# 汉字范围（与 forced_align._filter_chars 一致：U+4E00..U+9FFF）
_HANZI_LO = "一"
_HANZI_HI = "鿿"


def _is_hanzi(c: str) -> bool:
    return _HANZI_LO <= c <= _HANZI_HI


def compute_ideal_chars(
    total_chars: int,
    audio_duration: float,
    ideal_screen_seconds: float = 1.5,
    min_ideal: int = 8,
    max_ideal: int = 14,
) -> int:
    """按 TTS 实际语速算每屏理想字数（~1.5s 阅读）。"""
    if audio_duration <= 0 or total_chars <= 0:
        return (min_ideal + max_ideal) // 2
    chars_per_sec = total_chars / audio_duration
    ideal = round(chars_per_sec * ideal_screen_seconds)
    return max(min_ideal, min(max_ideal, ideal))


def _split_at_punctuation(text: str) -> List[str]:
    """按非空白标点切短语，每短语保留尾标点。空白不断句（英文词不拆）。"""
    WS = chr(0x20) + chr(0x09) + chr(0x0A) + chr(0x0D)
    NON_WS_BREAK = PHRASE_BREAK - set(WS)
    phrases: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in NON_WS_BREAK:
            phrases.append(cur)
            cur = ""
    if cur:
        phrases.append(cur)
    return phrases


def _clean_chars_count(text: str) -> int:
    """可见字符数（去空白）。"""
    return len(re.sub(r"\s+", "", text))


def split_subtitle_adaptive(
    text: str,
    audio_duration: float = 0.0,
    ideal_screen_seconds: float = 1.5,
    ideal_min: int = 8,
    ideal_max: int = 14,
    hard_max: int = 16,
    last_screen_min: int = LAST_SCREEN_MIN_CHARS,
) -> List[str]:
    """把句子切成 <= hard_max 字/屏，自适应每屏字数。"""
    if not text or not text.strip():
        return []

    text = re.sub(r"\s+", " ", text).strip()
    clean = _clean_chars_count(text)

    # 短句 -> 单屏
    ideal = compute_ideal_chars(clean, audio_duration, ideal_screen_seconds, ideal_min, ideal_max)
    if clean <= ideal:
        return [text]

    phrases = _split_at_punctuation(text)

    # 贪心打包短语到 ideal 字数
    chunks: list[str] = []
    buf = ""
    for p in phrases:
        p_clean = _clean_chars_count(p)

        # 单短语超长：冲掉 buf，硬切
        if p_clean > hard_max:
            if buf.strip():
                chunks.append(buf.strip())
                buf = ""
            cut_parts = [p[i:i + hard_max].strip() for i in range(0, len(p), hard_max)]
            # 尾部纯标点碎片合回上一段（自然句尾，略超 hard_max 可接受）
            if len(cut_parts) >= 2 and len(cut_parts[-1]) <= 2 and all(c in PHRASE_BREAK for c in cut_parts[-1]):
                cut_parts[-2] = (cut_parts[-2] + cut_parts[-1]).strip()
                cut_parts.pop()
            chunks.extend(cut_parts)
            continue

        combined_clean = _clean_chars_count(buf) + p_clean
        if combined_clean <= ideal:
            buf += p
        elif combined_clean <= hard_max:
            buf += p
        else:
            if buf.strip():
                chunks.append(buf.strip())
            buf = p

    if buf.strip():
        chunks.append(buf.strip())

    # 末屏太少且合并不超 hard_max -> 并入上一屏
    if len(chunks) >= 2:
        last_clean = _clean_chars_count(chunks[-1])
        if last_clean < last_screen_min:
            prev_clean = _clean_chars_count(chunks[-2])
            if prev_clean + last_clean <= hard_max:
                chunks[-2] = (chunks[-2] + chunks[-1]).strip()
                chunks.pop()

    return [c for c in chunks if c]


def compute_screen_durations(
    text: str,
    audio_start: float,
    audio_duration: float,
    word_timestamps: List[dict],
    screens: List[str],
) -> List[dict]:
    """用 forced_align 真实逐字时间戳算每屏起止（段内相对 -> 全局绝对）。

    word_timestamps: [{word,start,end}]（段内相对秒，**仅汉字**，forced_align 输出）。
    screens: split_subtitle_adaptive 的输出（屏文本，含标点）。

    用每屏首字时间戳做连续分区：首屏起 0、末屏止 audio_duration，屏间无间隙。
    汉字数 != 时间戳数 -> 整段均分 + log 警告（修 v0.5.4 静默越界 bug）。
    """
    if not screens:
        return []

    n_screens = len(screens)

    # 无时间戳 -> 均分 fallback
    if not word_timestamps:
        per = audio_duration / n_screens if n_screens else 0
        return [
            {"start": round(audio_start + i * per, 3), "duration": round(per, 3), "text": s}
            for i, s in enumerate(screens)
        ]

    # 汉字位置（text 中的 index 列表），与 word_timestamps 一一对应
    hanzi_pos = [i for i, c in enumerate(text) if _is_hanzi(c)]
    if len(hanzi_pos) != len(word_timestamps):
        log.warning(f"屏级切分：汉字数({len(hanzi_pos)}) != 时间戳数({len(word_timestamps)})，回退均分")
        per = audio_duration / n_screens
        return [
            {"start": round(audio_start + i * per, 3), "duration": round(per, 3), "text": s}
            for i, s in enumerate(screens)
        ]

    # 每屏找首字在 word_timestamps 的索引（按汉字在 text 中出现顺序）
    screen_first_wi: list[int | None] = []
    search_pos = 0
    for screen_text in screens:
        start_pos = text.find(screen_text, search_pos)
        if start_pos < 0:
            screen_first_wi.append(None)
            continue
        end_pos = start_pos + len(screen_text)
        search_pos = end_pos
        first_wi: int | None = None
        for j, tp in enumerate(hanzi_pos):
            if start_pos <= tp < end_pos:
                first_wi = j
                break
        screen_first_wi.append(first_wi)

    # 连续分区：每屏 start = 其首字时间戳（首屏=0），end = 下一屏 start（末屏=audio_duration）
    result: list[dict] = []
    for i, s in enumerate(screens):
        if i == 0:
            s_start = 0.0
        elif screen_first_wi[i] is not None:
            s_start = word_timestamps[screen_first_wi[i]]["start"]
        else:
            # 该屏无汉字（纯标点）-> 紧接上一屏，时长 0.3s 占位
            prev_end = (result[-1]["start"] - audio_start) + result[-1]["duration"] if result else 0.0
            s_start = prev_end

        if i == n_screens - 1:
            s_end = audio_duration
        elif screen_first_wi[i + 1] is not None:
            s_end = word_timestamps[screen_first_wi[i + 1]]["start"]
        else:
            s_end = s_start + 0.3

        dur = s_end - s_start
        if dur <= 0:
            dur = 0.3
        result.append({
            "start": round(audio_start + s_start, 3),
            "duration": round(dur, 3),
            "text": s,
        })

    return result
