"""管道引擎 - 按YAML清单调度阶段，支持三种审批模式 + 质量关卡 + approve/resume"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from .state import ProjectState, StageStatus
from .approval_controller import should_pause_for_review, get_auto_retry_limit

log = logging.getLogger(__name__)


class PipelineEngine:
    def __init__(self, data_dir: Path, pipeline_file: str = "pipelines/default.yaml", dry_run: bool = False):
        self.data_dir = Path(data_dir)
        self.pipeline = self._load_pipeline(pipeline_file)
        self.stage_handlers: dict[str, Callable] = {}
        self.approval_callback: Optional[Callable] = None
        self.preference_profile = None
        self.dry_run = dry_run
        self.event_store = None  # 延迟初始化，需要project_id

    def _load_pipeline(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def register_handler(self, stage_name: str, handler: Callable):
        self.stage_handlers[stage_name] = handler

    def auto_register_handlers(self, skill_loader, provider_selector, decision_logger, preference_profile=None, annotation_store=None):
        """自动发现并注册所有 Agent"""
        from ..agents.topic_agent import TopicAgent
        from ..agents.highlight_selection_agent import HighlightAgent
        from ..agents.copywriting_agent import CopywritingAgent
        from ..agents.storyboard_agent import StoryboardAgent
        from ..agents.title_agent import TitleAgent
        from ..agents.cover_agent import CoverAgent
        from ..agents.fine_cut_agent import FineCutAgent
        from ..agents.render_agent import RenderAgent
        from ..agents.rhythm_agent import RhythmAgent
        from ..agents.bgm_agent import BGMAgent
        from ..agents.voice_selection_agent import VoiceAgent
        from ..agents.web_research_agent import WebResearchAgent
        from ..agents.material_analysis_agent import MaterialAnalysisAgent
        from ..agents.image_matching_agent import ImageMatchingAgent
        from ..agents.tts_agent import TTSAgent

        agent_classes = {
            "material_analysis": MaterialAnalysisAgent,
            "web_research": WebResearchAgent,
            "topic": TopicAgent,
            "highlight_selection": HighlightAgent,
            "copywriting": CopywritingAgent,
            "image_matching": ImageMatchingAgent,
            "voice_selection": VoiceAgent,
            "tts": TTSAgent,
            "storyboard": StoryboardAgent,
            "bgm": BGMAgent,
            "rhythm": RhythmAgent,
            "title": TitleAgent,
            "cover": CoverAgent,
            "fine_cut": FineCutAgent,
            "render": RenderAgent,
        }

        for stage_name, agent_cls in agent_classes.items():
            agent = agent_cls(skill_loader, provider_selector, decision_logger,
                              preference_profile=preference_profile, annotation_store=annotation_store)
            self.register_handler(stage_name, agent.execute)

        self._register_quality_gates()
        self.preference_profile = preference_profile
        # 初始化EventStore（如果有decision_logger的project_id）
        try:
            from ..observability.event_store import EventStore
            # 从decision_logger路径推断project_id
            pid = decision_logger.log_path.parent.name
            self.event_store = EventStore(decision_logger.log_path.parent.parent.parent, pid)
        except Exception:
            pass
        log.info(f"Auto-registered {len(self.stage_handlers)} handlers")

    def _register_quality_gates(self):
        """注册质量关卡为特殊handler"""
        async def slideshow_check_handler(state, stage):
            from ..quality.slideshow_scorer import score_storyboard
            sb_output = state.get_stage_output("storyboard")
            topic_output = state.get_stage_output("topic")
            segments = sb_output.get("segments", []) if sb_output else []
            score = score_storyboard(segments, topic_output)
            return {"data": {"total_score": score.total_score, "risk_level": score.risk_level,
                             "passed": score.passed, "suggestions": score.suggestions},
                    "confidence": 90.0 if score.passed else 40.0}

        async def opening_review_handler(state, stage):
            from ..config import get_domain_config
            sb_output = state.get_stage_output("storyboard")
            if not sb_output:
                return {"data": {"passed": True}, "confidence": 50.0}
            segments = sb_output.get("segments", [])
            first_segs = [s for s in segments if s.get("time_start", 0) < 3.0]

            # 从style.yaml读取检查项配置
            try:
                domain_cfg = get_domain_config(state.domain)
                style = domain_cfg.get_style()
                configured_checks = style.get("quality_gates", {}).get("opening_hard_checks", [])
            except Exception:
                configured_checks = []

            checks = {"has_first_segment": len(first_segs) > 0,
                      "has_image": bool(first_segs and first_segs[0].get("image")),
                      "has_subtitle": bool(first_segs and first_segs[0].get("subtitle"))}

            # 如果配置了额外检查项，加入检查
            if "high_info_first_frame" in configured_checks:
                checks["high_info_first_frame"] = bool(first_segs and first_segs[0].get("image"))
            if "identifiable_subject" in configured_checks:
                checks["identifiable_subject"] = bool(first_segs and first_segs[0].get("image"))
            if "subtitle_appears_early" in configured_checks:
                # 检查字幕word的第一条start < 1.0秒（无word数据时跳过此项）
                words = first_segs[0].get("subtitle_words", []) if first_segs else []
                if words:
                    checks["subtitle_appears_early"] = words[0].get("start", 99) < 1.0
                else:
                    checks["subtitle_appears_early"] = True  # 无数据时默认通过

            passed = all(checks.values())
            return {"data": {"passed": passed, "checks": checks}, "confidence": 90.0 if passed else 40.0}

        async def pre_render_check_handler(state, stage):
            sb_output = state.get_stage_output("storyboard")
            if not sb_output:
                return {"data": {"passed": False, "issues": ["无分镜数据"]}, "confidence": 20.0}
            segments = sb_output.get("segments", [])
            issues = []
            if not segments:
                issues.append("分镜段落数据为空")
            for i, s in enumerate(segments):
                if not s.get("image"):
                    issues.append(f"段落{i}无图片")
            # TTS 音频必须存在，否则会渲染无声视频（silent failure 防护）
            # 仅当 tts 在当前管道中时检查（12 阶段冒烟/e2e 跳过 tts 时不强求）
            pipeline_stage_names = {s["name"] for s in self.get_stages()}
            if "tts" in pipeline_stage_names:
                tts_output = state.get_stage_output("tts")
                audio_path = tts_output.get("audio_path", "") if tts_output else ""
                if not audio_path:
                    issues.append("TTS 音频路径为空")
                elif not Path(audio_path).exists():
                    issues.append(f"TTS 音频文件不存在: {audio_path}")
            passed = len(issues) == 0
            return {"data": {"passed": passed, "issues": issues}, "confidence": 90.0 if passed else 40.0}

        async def post_render_check_handler(state, stage):
            from ..quality.post_render_validator import validate_video, format_report
            render_output = state.get_stage_output("render")
            if not render_output or not render_output.get("video_path"):
                return {"data": {"passed": False, "issues": ["无渲染输出"]}, "confidence": 20.0}
            video_path = render_output["video_path"]
            sb_output = state.get_stage_output("storyboard")
            expected = sum(s.get("actual_duration", 3.0) for s in sb_output.get("segments", [])) if sb_output else 30.0
            result = validate_video(video_path, expected_duration=expected)
            return {"data": {"passed": result.passed, "issues": result.issues, "report": format_report(result)},
                    "confidence": 90.0 if result.passed else 40.0}

        async def deliver_handler(state, stage):
            render_output = state.get_stage_output("render")
            return {"data": {"video_path": render_output.get("video_path", "") if render_output else "",
                             "delivered": True}, "confidence": 90.0}

        self.register_handler("slideshow_check", slideshow_check_handler)
        self.register_handler("opening_review", opening_review_handler)
        self.register_handler("pre_render_check", pre_render_check_handler)
        self.register_handler("post_render_check", post_render_check_handler)
        self.register_handler("deliver", deliver_handler)

    def get_stages(self) -> list[dict]:
        return self.pipeline["pipeline"]["stages"]

    async def run(self, state: ProjectState, start_from: str | None = None) -> ProjectState:
        if self.dry_run:
            stages = self.get_stages()
            print(f"[DRY-RUN] {len(stages)} stages would execute:")
            for s in stages:
                print(f"  - {s['name']} ({s.get('type','auto')}) requires={s.get('requires',[])}")
            return state

        started = start_from is None
        for stage_def in self.get_stages():
            name = stage_def["name"]
            if not started:
                if name == start_from:
                    started = True
                else:
                    continue
            stage_type = stage_def.get("type", "auto")
            stage = state.get_stage(name)

            if stage.status == StageStatus.COMPLETED:
                continue
            if not self._check_prerequisites(state, stage_def):
                log.warning(f"Stage {name}: prerequisites not met, skipping")
                continue

            # 契约校验：上游在管道中却没产出必需字段 -> 标 ERROR 跳过（不再静默 warn）
            from ..quality.preflight import check_stage_inputs
            pipeline_stages = {s["name"] for s in self.get_stages()}
            input_ok, input_issues = check_stage_inputs(state, name, available_stages=pipeline_stages)
            if not input_ok:
                log.error(f"Stage {name}: input contract failed: {input_issues}")
                stage.status = StageStatus.ERROR
                stage.error = f"input contract failed: {input_issues}"
                state.save(self.data_dir)
                continue

            # 为特定阶段注入 input_data（领域配置/上游输出）
            from .stage_input_injector import inject_stage_input
            inject_stage_input(state, stage)

            stage.status = StageStatus.IN_PROGRESS
            stage.started_at = datetime.now()
            state.save(self.data_dir)

            # 发射事件
            if self.event_store:
                self.event_store.emit_stage_started(name, stage.input_data)

            try:
                handler = self.stage_handlers.get(name)
                if handler:
                    output = await handler(state, stage)
                    if isinstance(output, dict):
                        stage.output_data = output.get("data", output)
                        if "confidence" in output:
                            stage.confidence_score = output["confidence"]
                        # handler 返回 state_updates（如 last_provider/cost_total）-> engine 集中应用
                        # 注意：engine 按引用 in-place 应用（与 stage 变更一致），保证 state.json 持久化
                        if "state_updates" in output:
                            for k, v in output["state_updates"].items():
                                setattr(state, k, v)
                else:
                    log.warning(f"Stage {name}: no handler, auto-pass")

                needs_review = should_pause_for_review(stage_type, state.approval_mode, stage.confidence_score)
                if needs_review:
                    stage.status = StageStatus.REVIEW
                    state.save(self.data_dir)
                    if self.approval_callback:
                        approved = await self.approval_callback(state, name)
                        if not approved:
                            stage.status = StageStatus.PENDING
                            stage.retry_count += 1
                            state.save(self.data_dir)
                            continue
                    else:
                        continue

                if stage_type in ("quality_gate", "quality_gate_auto") and stage.output_data:
                    if not stage.output_data.get("passed", True):
                        retry_limit = get_auto_retry_limit(state.approval_mode)
                        if stage.retry_count < retry_limit:
                            stage.retry_count += 1
                            stage.status = StageStatus.PENDING
                            # 重置影响分数的上游阶段，让重试产生不同结果
                            if name == "slideshow_check":
                                sb = state.get_stage("storyboard")
                                sb.status = StageStatus.PENDING
                                sb.retry_count += 1
                            state.save(self.data_dir)
                            continue

                # postflight: 完整性校验（空/缺关键字段）失败则 RETRY；schema 类型不符仅 warn
                from ..quality.postflight import validate_output, check_output_completeness
                output_ok, output_issues = validate_output(name, stage.output_data)
                complete_ok, complete_issues = check_output_completeness(name, stage.output_data)
                if not complete_ok:
                    log.warning(f"Stage {name}: output completeness issues: {complete_issues}")
                    retry_limit = get_auto_retry_limit(state.approval_mode)
                    if stage.retry_count < retry_limit:
                        stage.retry_count += 1
                        stage.status = StageStatus.PENDING
                        state.save(self.data_dir)
                        continue
                    log.error(f"Stage {name}: output completeness exhausted retries: {complete_issues}")
                    stage.status = StageStatus.ERROR
                    stage.error = f"output completeness failed: {complete_issues}"
                    state.save(self.data_dir)
                    continue
                elif not output_ok:
                    # schema 类型不符（AI 返回更丰富结构，如 dict 代替 str）-> 非阻断，记录 warn
                    log.warning(f"Stage {name}: output schema issues (non-blocking): {output_issues}")

                state.mark_stage(name, StageStatus.COMPLETED)

                # 发射事件
                if self.event_store:
                    self.event_store.emit_stage_completed(name, stage.output_data, stage.confidence_score or 0)

            except Exception as e:
                log.error(f"Stage {name} failed: {e}", exc_info=True)
                stage.status = StageStatus.ERROR
                stage.error = str(e)
                if self.event_store:
                    self.event_store.emit_stage_error(name, str(e))
                state.save(self.data_dir)
                raise

            state.save(self.data_dir)
        return state

    async def approve_stage(self, state: ProjectState, stage_name: str, approved: bool = True, feedback: str = "") -> ProjectState:
        """审批一个处于REVIEW状态的阶段"""
        stage = state.get_stage(stage_name)
        if stage.status != StageStatus.REVIEW:
            log.warning(f"Stage {stage_name} is not in REVIEW (current: {stage.status})")
            return state

        if approved:
            state.mark_stage(stage_name, StageStatus.COMPLETED)
            if feedback:
                state.user_notes[stage_name] = feedback
            # 记录用户决策到偏好画像
            if self.preference_profile:
                self.preference_profile.record_decision(
                    stage_name, stage.output_data, stage.confidence_score or 0
                )
        else:
            stage.status = StageStatus.PENDING
            stage.retry_count += 1
            if feedback:
                state.user_notes[stage_name] = feedback

        state.save(self.data_dir)
        if approved:
            await self.run(state, start_from=stage_name)
        return state

    async def resume(self, state: ProjectState) -> ProjectState:
        """恢复执行"""
        await self.run(state)
        return state

    def _check_prerequisites(self, state: ProjectState, stage_def: dict) -> bool:
        for req in stage_def.get("requires", []):
            if not state.is_stage_completed(req):
                return False
        return True
