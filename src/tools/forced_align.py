"""强制对齐 - wav2vec2 CTC，从 TTS 音频 + 已知文本测真实逐字时间戳

opt-in（OPENCUT_FORCED_ALIGN=1）。替代 tts_agent 里 `char_dur = dur/len(chars)` 造假逻辑。
模型：jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn（中文 wav2vec2，每字一 token）。
依赖 [align] extras（torch+torchaudio+transformers）。未装/失败时返回 None，调用方回退造假。
首次调用下载 ~1.2GB 模型（HuggingFace 缓存，国内需 HTTPS_PROXY）。
"""
from __future__ import annotations
import logging
import os
import subprocess
import tempfile
from typing import Any

log = logging.getLogger(__name__)

_MODEL: Any = None
_PROCESSOR: Any = None
_MODEL_LOADING_TRIED = False

_MODEL_NAME = "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"
# wav2vec2 CNN 下采样 ~320x，16kHz -> 50Hz 帧率
_FRAME_RATE = 16000 / 320


def _is_available() -> bool:
    """torch/torchaudio/transformers 是否可 import。"""
    try:
        import torch  # noqa: F401
        import torchaudio  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _load_model() -> bool:
    """懒加载模型+processor（单例）。失败返 False 且不重试。"""
    global _MODEL, _PROCESSOR, _MODEL_LOADING_TRIED
    if _MODEL is not None:
        return True
    if _MODEL_LOADING_TRIED:
        return False
    _MODEL_LOADING_TRIED = True
    try:
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        log.info("加载 wav2vec2 中文对齐模型（首次需下载 ~1.2GB，需代理）...")
        _PROCESSOR = Wav2Vec2Processor.from_pretrained(_MODEL_NAME)
        _MODEL = Wav2Vec2ForCTC.from_pretrained(_MODEL_NAME)
        _MODEL.eval()
        log.info("wav2vec2 模型加载完成。")
        return True
    except Exception as e:
        log.warning(f"wav2vec2 模型加载失败（回退造假时间戳）: {e}")
        _MODEL = None
        _PROCESSOR = None
        return False


def _audio_to_wav(audio_path: str) -> str | None:
    """ffmpeg 转任意音频为 16kHz mono f32le wav。返回临时文件路径。"""
    try:
        tmp = tempfile.mktemp(suffix=".wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path,
             "-ar", "16000", "-ac", "1", "-f", "f32le", "-c:a", "pcm_f32le", tmp],
            capture_output=True, timeout=30, check=True,
        )
        return tmp
    except Exception as e:
        log.warning(f"音频转 wav 失败: {e}")
        return None


def _filter_chars(text: str) -> list[str]:
    """只留 CJK 汉字（vocab 里有的）。标点/数字/英文跳过（无时间戳）。"""
    return [c for c in text if "一" <= c <= "鿿"]


def align_chars(audio_path: str, text: str) -> list[dict] | None:
    """对齐文本字符到音频，返回逐字时间戳。

    Returns: [{char, start, end}]（段内相对秒，仅汉字），或 None（失败/未装依赖）。
    标点/数字/英文不在结果中（被 _filter_chars 跳过），调用方按汉字流处理。
    """
    if not _is_available():
        log.warning("forced align 依赖未装（torch/torchaudio/transformers）。"
                    "装：pip install -e \".[align]\"")
        return None
    if not _load_model():
        return None

    chars = _filter_chars(text)
    if not chars:
        log.warning("文本无汉字可对齐")
        return None

    wav_path = _audio_to_wav(audio_path)
    if wav_path is None:
        return None

    try:
        import torch
        import torchaudio

        waveform, sr = torchaudio.load(wav_path)
        if sr != 16000:
            waveform = torchaudio.functional.resample(waveform, sr, 16000)

        with torch.no_grad():
            inputs = _PROCESSOR(waveform.squeeze(), sampling_rate=16000, return_tensors="pt")
            logits = _MODEL(inputs.input_values).logits
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)

        # 构造 target token id 序列（每汉字一 token）
        targets_list: list[int] = []
        valid_chars: list[str] = []
        for c in chars:
            encoded = _PROCESSOR.tokenizer(c, add_special_tokens=False)
            if encoded.input_ids:
                targets_list.append(int(encoded.input_ids[0]))
                valid_chars.append(c)
        if not targets_list:
            log.warning("无有效 token id")
            return None

        targets = torch.tensor(targets_list, dtype=torch.int32)
        # forced_align: alignment 每帧 -> target 索引（0=blank, 1..N=第 i 个 target）
        alignment, _ = torchaudio.functional.forced_align(log_probs, targets, blank=0)

        # 合并连续同 token 帧为 char 时间段
        result: list[dict] = []
        prev_idx = -1
        time_per_frame = 1.0 / _FRAME_RATE
        for frame_idx in range(alignment.shape[0]):
            tok = int(alignment[frame_idx].item())
            if tok <= 0:
                continue  # blank
            char_idx = tok - 1
            t = frame_idx * time_per_frame
            if char_idx != prev_idx:
                if result:
                    result[-1]["end"] = t
                result.append({"char": valid_chars[char_idx], "start": t, "end": t + time_per_frame})
                prev_idx = char_idx
            else:
                result[-1]["end"] = t + time_per_frame

        return result if result else None
    except Exception as e:
        log.warning(f"forced align 失败: {e}")
        return None
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass
