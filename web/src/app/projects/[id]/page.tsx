"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface JobInfo {
  id: number;
  status: string;
  current_stage: string | null;
  stages_total: number;
  stages_completed: number;
  error: string | null;
}

interface StageState {
  name: string;
  status: string;
  confidence_score?: number;
}

interface ProjectStateData {
  stages: Record<string, StageState>;
}

const STAGE_NAMES = [
  "material_analysis", "web_research", "topic", "highlight_selection", "copywriting",
  "image_matching", "voice_selection", "tts", "storyboard", "opening_review",
  "slideshow_check", "bgm", "rhythm", "title", "cover", "fine_cut",
  "pre_render_check", "render", "post_render_check", "deliver",
];

export default function ProjectDetail({ params }: { params: { id: string } }) {
  const { user, loading } = useAuth();
  const [job, setJob] = useState<JobInfo | null>(null);
  const [stateData, setStateData] = useState<ProjectStateData | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login";
      return;
    }
    let stop = false;
    const poll = async () => {
      try {
        const jobs = await apiFetch<JobInfo[]>(`/api/jobs?project_id=${params.id}`);
        if (jobs.length > 0 && !stop) {
          setJob(jobs[0]);
          if (jobs[0].status === "running" || jobs[0].status === "queued") {
            // 继续轮询
          }
        }
        const st = await apiFetch<ProjectStateData>(`/api/projects/${params.id}/state`);
        if (!stop) setStateData(st);
      } catch (e) {
        if (!stop) setErr(String((e as Error).message));
      }
    };
    poll();
    const interval = setInterval(poll, 2000);
    // 任务终态停止轮询
    const stopCheck = setInterval(() => {
      if (job && (job.status === "completed" || job.status === "failed")) {
        clearInterval(interval);
      }
    }, 2000);
    return () => {
      stop = true;
      clearInterval(interval);
      clearInterval(stopCheck);
    };
  }, [user, loading, params.id, job?.status]);

  const stages = stateData?.stages || {};
  const status = job?.status || "未知";

  return (
    <div>
      <div className="nav">
        <a href="/dashboard">← 返回</a>
        <strong>{params.id}</strong>
        <span style={{ color: status === "completed" ? "#6ec07e" : status === "failed" ? "#ff6b6b" : "#ffd166" }}>
          {status}
        </span>
      </div>
      <div className="container">
        {err && <div className="error">{err}</div>}
        {job?.error && <div className="error">失败：{job.error}</div>}
        <div style={{ marginBottom: 20, color: "#888" }}>
          进度：{job?.stages_completed || 0} / {job?.stages_total || 20}
          {job?.current_stage && ` · 当前：${job.current_stage}`}
        </div>

        <div>
          {STAGE_NAMES.map((name) => {
            const st = stages[name];
            const s = st?.status || "pending";
            const cls = s === "completed" ? "done" : s === "in_progress" ? "active" : "pending";
            return (
              <div key={name} className={`stage ${cls}`}>
                {s === "completed" ? "✓" : s === "in_progress" ? "▶" : "·"} {name}
              </div>
            );
          })}
        </div>

        {status === "completed" && job && (
          <div style={{ marginTop: 24 }}>
            <a href={`/api/jobs/${job.id}/result`}>
              <button type="button">下载 final.mp4</button>
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
