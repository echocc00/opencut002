"""验证素材分层决策（第1/2层，真实 minimax 匹配打分）

构造 2 张池图 + 4 段文案（2 段匹配、2 段不匹配），跑 ImageMatchingAgent，
看 layer_log 的分层判定。gen 默认关 -> 缺口段走文字卡。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from src.providers.provider_registry import auto_register_from_env
from src.agents.image_matching_agent import ImageMatchingAgent
from src.orchestrator.state import ProjectState


async def main():
    if not auto_register_from_env():
        print("[X] 无 Provider，请配 MINIMAX_API_KEY")
        return
    os.environ.pop("OPENCUT_IMAGE_GEN", None)  # gen 关，缺口走文字卡

    agent = ImageMatchingAgent(None, None, None)
    state = ProjectState(project_id="verify_layer", domain="education")
    state.get_stage("material_analysis").output_data = {
        "images": [
            {"file": "classroom.jpg", "scene": "教室里学生听课，暖色调纪实摄影"},
            {"file": "playground.jpg", "scene": "操场上孩子奔跑，户外阳光"},
        ]
    }
    state.get_stage("copywriting").output_data = {
        "paragraphs": [
            {"text": "学生们在教室里认真听课", "image_hint": "", "emotion_tone": "neutral"},
            {"text": "下课后孩子们在操场上奔跑", "image_hint": "", "emotion_tone": "neutral"},
            {"text": "宇宙飞船缓缓降落在火星表面", "image_hint": "", "emotion_tone": "neutral"},
            {"text": "深海里的鲸鱼缓缓游过", "image_hint": "", "emotion_tone": "neutral"},
        ]
    }

    result = await agent.execute(state, state.get_stage("image_matching"))
    print("\n=== 分层结果 ===")
    for line in result["data"]["layer_log"]:
        print(line)
    print(f"\n文字卡段（缺口）: {result['data']['text_cards']}")
    print(f"最终匹配: {result['data']['matches']}")


if __name__ == "__main__":
    asyncio.run(main())
