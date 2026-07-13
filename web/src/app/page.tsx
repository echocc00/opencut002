"use client";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user, loading } = useAuth();
  useEffect(() => {
    if (!loading) {
      window.location.href = user ? "/dashboard" : "/login";
    }
  }, [user, loading]);
  return <div className="container">跳转中…</div>;
}
