/**
 * 字幕组件 - 整段淡入 或 逐行进度（OPENCUT_FORCED_ALIGN）
 *
 * 模式1（默认）：subtitleLines 缺失 -> 整段文案 spring 淡入
 * 模式2（forced align）：subtitleLines 提供逐行段内时间戳 ->
 *   按段内时间找当前行，interpolate 淡入(0.15s)/淡出(0.1s)
 *
 * useCurrentFrame() 在 <Sequence> 内返回相对该 Sequence 的帧，所以 currentTime 是段内秒。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

type SubtitleLine = {
  text: string;
  start: number; // 段内相对秒
  end: number;
};

type Props = {
  text: string;
  springConfig?: { damping: number; stiffness: number; mass: number };
  subtitleLines?: SubtitleLine[];
};

const CAPTION_STYLE: React.CSSProperties = {
  color: "#FFFFFF",
  fontSize: 42,
  fontWeight: 700,
  fontFamily: "Noto Sans SC, sans-serif",
  whiteSpace: "pre-wrap",
  lineHeight: 1.5,
  textShadow: "0 2px 8px rgba(0,0,0,0.8)",
};

const WRAPPER_STYLE: React.CSSProperties = {
  justifyContent: "flex-end",
  alignItems: "center",
  paddingBottom: 60,
};

export const WordByWordSubtitle: React.FC<Props> = ({ text, springConfig, subtitleLines }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 模式2：逐行进度（forced align）
  if (subtitleLines && subtitleLines.length > 0) {
    const currentTime = frame / fps;
    let activeLine: SubtitleLine | null = null;
    for (const line of subtitleLines) {
      if (currentTime >= line.start && currentTime < line.end) {
        activeLine = line;
        break;
      }
    }
    // 间隙：显示上一行（让它淡出）
    if (!activeLine) {
      for (const line of subtitleLines) {
        if (line.end <= currentTime) activeLine = line;
      }
    }
    if (!activeLine) return null;

    const opacity = interpolate(
      currentTime,
      [activeLine.start, activeLine.start + 0.15, activeLine.end, activeLine.end + 0.1],
      [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );

    return (
      <AbsoluteFill style={WRAPPER_STYLE}>
        <div style={{
          opacity,
          transform: `translateY(${(1 - opacity) * 8}px)`,
          maxWidth: "92%",
          textAlign: "center",
        }}>
          <span style={CAPTION_STYLE}>{activeLine.text}</span>
        </div>
      </AbsoluteFill>
    );
  }

  // 模式1：整段 spring 淡入（fallback / OPENCUT_FORCED_ALIGN=0）
  const enterProgress = spring({
    frame, fps,
    config: springConfig || { damping: 18, stiffness: 120 },
  });

  return (
    <AbsoluteFill style={WRAPPER_STYLE}>
      <div style={{
        opacity: enterProgress,
        transform: `translateY(${(1 - enterProgress) * 15}px)`,
        maxWidth: "92%",
        textAlign: "center",
      }}>
        <span style={CAPTION_STYLE}>{text}</span>
      </div>
    </AbsoluteFill>
  );
};
