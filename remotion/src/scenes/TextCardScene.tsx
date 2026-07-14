/**
 * 文字卡场景 - 缺口段（无匹配素材）用全屏文字卡代替图片
 *
 * 第2层兜底：image_matching 判定该段无合适素材（score < WEAK）时，
 * 段标记 textCard=true，VideoComposition 渲染本组件代替 SegmentScene。
 * 文案文本大字居中 + 背景色，淡入淡出。不配图，避免突兀。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { ThemeConfig } from "../theme";

interface TextCardSceneProps {
  text: string;
  theme: ThemeConfig;
}

export function TextCardScene({ text, theme }: TextCardSceneProps) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 120 } });
  const fadeOut = interpolate(
    frame, [durationInFrames - 8, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const opacity = enter * fadeOut;
  return (
    <AbsoluteFill style={{
      backgroundColor: theme.backgroundColor,
      justifyContent: "center", alignItems: "center", padding: 48,
    }}>
      <div style={{
        opacity,
        transform: `translateY(${(1 - enter) * 20}px)`,
        textAlign: "center", maxWidth: "92%",
      }}>
        <span style={{
          color: "#FFFFFF",
          fontSize: 56,
          fontWeight: 800,
          fontFamily: "Noto Sans SC, sans-serif",
          lineHeight: 1.5,
          textShadow: "0 2px 12px rgba(0,0,0,0.6)",
          whiteSpace: "pre-wrap",
        }}>
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
}
