"use client";
import { useState, ChangeEvent, FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

const DOMAINS = ["education", "travel", "knowledge_paid", "custom"];

export default function NewProjectPage() {
  const { user, loading } = useAuth();
  const [domain, setDomain] = useState("education");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (loading) return <div className="container">加载中…</div>;
  if (!user) {
    if (typeof window !== "undefined") window.location.href = "/login";
    return null;
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (files.length === 0) {
      setErr("请至少上传 1 个素材");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("domain", domain);
      fd.append("approval_mode", "full_auto");
      files.forEach((f) => fd.append("materials", f, f.name));
      const data = await apiFetch<{ project_id: string }>(
        "/api/projects/create",
        { method: "POST", body: fd },
      );
      // 自动启动任务
      await apiFetch(`/api/projects/${data.project_id}/run`, { method: "POST" });
      window.location.href = `/projects/${data.project_id}`;
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const onFiles = (e: ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(e.target.files || []));
  };

  return (
    <div>
      <div className="nav">
        <a href="/dashboard">← 返回</a>
        <strong>新建项目</strong>
        <span />
      </div>
      <div className="container">
        <form onSubmit={submit} style={{ maxWidth: 520 }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 6 }}>领域</label>
            <select value={domain} onChange={(e) => setDomain(e.target.value)}>
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 6 }}>
              素材（图片 jpg/jpeg/png 或视频 mp4/mov 等，自动抽帧，取前 5 张）
            </label>
            <input
              type="file" multiple accept="image/jpeg,image/png,video/mp4,video/quicktime"
              onChange={onFiles}
            />
            {files.length > 0 && (
              <div style={{ marginTop: 8, color: "#888", fontSize: 14 }}>
                已选 {files.length} 个：{files.map((f) => f.name).join(", ")}
              </div>
            )}
          </div>
          {err && <div className="error">{err}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "创建并启动中…" : "创建并生成视频"}
          </button>
        </form>
      </div>
    </div>
  );
}
