/**
 * 字幕组件 - 单行显示（chunk-per-segment 后每段已是 ≤16 字块，无需 even-split）
 *
 * 每个分镜段的 subtitle 就是 TTS 的一个 ≤16 字块，段级精确同步（TTS 是时间源）。
 * 单行、大字号、淡入。同段落连续块（continuation）不重复淡入。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

export const WordByWordSubtitle: React.FC<{
  text: string;
  springConfig?: { damping: number; stiffness: number; mass: number };
  continuation?: boolean;
}> = ({ text, springConfig, continuation = false }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // continuation（同段落连续块）：不重复淡入，仅最后淡出
  const enter = continuation ? 1 : spring({ frame, fps, config: springConfig || { damping: 18, stiffness: 120 } });
  const fadeOut = interpolate(
    frame, [durationInFrames - 6, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const opacity = continuation ? fadeOut : enter * fadeOut;
  const translateY = continuation ? 0 : (1 - enter) * 15;

  if (!text) return null;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 90 }}>
      <div style={{ opacity, transform: `translateY(${translateY}px)`, textAlign: "center", maxWidth: "96%" }}>
        <span style={{
          color: "#FFFFFF",
          fontSize: 60,
          fontWeight: 800,
          fontFamily: "Noto Sans SC, sans-serif",
          whiteSpace: "nowrap",
          textShadow: "0 2px 12px rgba(0,0,0,0.85), 0 0 4px rgba(0,0,0,0.6)",
          letterSpacing: 1,
        }}>
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
