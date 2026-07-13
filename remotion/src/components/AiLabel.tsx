import { AbsoluteFill } from "remotion";

interface AiLabelProps {
  visible: boolean;
  text?: string;
}

/**
 * AI 生成内容标识。默认不渲染（visible=false）。
 *
 * 合规储备：国内《AI内容标识办法》2025-09-01 生效，要求 AI 生成视频在起始画面
 * 和播放周边加显著标识。本组件提供右下角角标（贯穿全片）+ 起始 2 秒居中提示。
 * 通过渲染数据 aiLabel 字段开关（由 OPENCUT_AI_LABEL 环境变量控制），默认关。
 */
export function AiLabel({ visible, text = "AI 生成" }: AiLabelProps) {
  if (!visible) return null;

  const cornerBadge: React.CSSProperties = {
    position: "absolute",
    bottom: 28,
    right: 24,
    padding: "6px 14px",
    borderRadius: 8,
    backgroundColor: "rgba(0,0,0,0.55)",
    color: "#ffffff",
    fontSize: 24,
    fontWeight: 600,
    letterSpacing: 2,
    fontFamily: "system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif",
  };

  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 100 }}>
      <div style={cornerBadge}>{text}</div>
    </AbsoluteFill>
  );
}
