"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface Project {
  project_id: string;
  domain: string;
  approval_mode: string;
  created_at: string;
}

export default function Dashboard() {
  const { user, loading, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login";
      return;
    }
    apiFetch<Project[]>("/api/projects")
      .then(setProjects)
      .catch((e) => setErr(String(e.message)));
  }, [user, loading]);

  if (loading) return <div className="container">加载中…</div>;

  return (
    <div>
      <div className="nav">
        <strong>OpenCut</strong>
        <div>
          <span style={{ marginRight: 12 }}>{user?.username}</span>
          <button
            type="button"
            style={{ background: "#1a1d24", color: "#888" }}
            onClick={logout}
          >退出</button>
        </div>
      </div>
      <div className="container">
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
          <h2>我的项目</h2>
          <a href="/projects/new"><button type="button">+ 新建项目</button></a>
        </div>
        {err && <div className="error">{err}</div>}
        {projects.length === 0 ? (
          <p style={{ color: "#888" }}>还没有项目，点「新建项目」开始创作。</p>
        ) : (
          <div>
            {projects.map((p) => (
              <a
                key={p.project_id}
                href={`/projects/${p.project_id}`}
                style={{ display: "block", padding: 14, marginBottom: 10,
                         background: "#1a1d24", borderRadius: 8, textDecoration: "none",
                         color: "#e6e6e6" }}
              >
                <strong>{p.project_id}</strong>
                <span style={{ marginLeft: 12, color: "#888" }}>
                  {p.domain} · {new Date(p.created_at).toLocaleString()}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
