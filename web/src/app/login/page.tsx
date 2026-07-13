"use client";
import { useState, FormEvent } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, username, password);
      }
      window.location.href = "/dashboard";
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginBottom: 20 }}>
        {mode === "login" ? "登录 OpenCut" : "注册 OpenCut"}
      </h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        <button
          style={mode === "login" ? {} : { background: "#1a1d24", color: "#888" }}
          onClick={() => setMode("login")}
          type="button"
        >登录</button>
        <button
          style={mode === "register" ? {} : { background: "#1a1d24", color: "#888" }}
          onClick={() => setMode("register")}
          type="button"
        >注册</button>
      </div>
      <form onSubmit={submit}>
        <input
          placeholder="邮箱" value={email}
          onChange={(e) => setEmail(e.target.value)}
          required style={{ width: "100%", marginBottom: 10 }}
        />
        {mode === "register" && (
          <input
            placeholder="用户名" value={username}
            onChange={(e) => setUsername(e.target.value)}
            required style={{ width: "100%", marginBottom: 10 }}
          />
        )}
        <input
          type="password" placeholder="密码" value={password}
          onChange={(e) => setPassword(e.target.value)}
          required style={{ width: "100%", marginBottom: 10 }}
        />
        {err && <div className="error">{err}</div>}
        <button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "处理中…" : mode === "login" ? "登录" : "注册"}
        </button>
      </form>
    </div>
  );
}
