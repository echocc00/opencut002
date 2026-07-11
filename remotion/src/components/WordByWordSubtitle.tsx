/**
 * 逐词高亮字幕
 *
 * - words 非空：每个词随配音节奏放大变色（isActive 放大、isPast 变色）
 * - words 为空：降级整段显示 fallbackText（转录失败/无词时间戳时的兜底）
 * - 暗色背板保证在画面上的可读性，容器入场 spring 动画
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

export const WordByWordSubtitle: React.FC<{
  words: { word: string; start: number; end: number }[];
  style: { activeColor: string; pastColor: string; upcomingColor: string };
  fallbackText?: string;
  springConfig?: { damping: number; stiffness: number; mass: number };
}> = ({ words, style, fallbackText, springConfig }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  const enterProgress = spring({
    frame, fps,
    config: springConfig || { damping: 18, stiffness: 120 },
  });

  return (
    <AbsoluteFill style={{
      justifyContent: "flex-end",
      alignItems: "center",
      paddingBottom: 60,
    }}>
      <div style={{
        opacity: enterProgress,
        transform: `translateY(${interpolate(enterProgress, [0, 1], [15, 0])}px)`,
        backgroundColor: "rgba(0,0,0,0.7)",
        borderRadius: 10,
        padding: "10px 24px",
        maxWidth: "92%",
        textAlign: "center",
      }}>
        {words.length === 0
          ? <span style={{ color: "#FFFFFF", fontSize: 42, fontWeight: 700, fontFamily: "Noto Sans SC, sans-serif", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
              {fallbackText || ""}
            </span>
          : <div style={{ fontSize: 42, fontWeight: 700, fontFamily: "Noto Sans SC, sans-serif", lineHeight: 1.5 }}>
              {words.map((w, i) => {
                const isActive = currentTime >= w.start && currentTime <= w.end;
                const isPast = currentTime > w.end;
                const wordDur = Math.max(w.end - w.start, 0.05);
                const scaleStart = Math.round(w.start * fps);
                const scaleEnd = Math.round((w.start + Math.min(wordDur, 0.1)) * fps);
                const scale = isActive
                  ? interpolate(frame, [scaleStart, scaleEnd], [1.3, 1.0], { extrapolateRight: "clamp" })
                  : 1.0;
                const color = isActive ? style.activeColor : isPast ? style.pastColor : style.upcomingColor;
                return (
                  <span key={i} style={{ color, transform: `scale(${scale})`, display: "inline-block", marginRight: "4px", transition: "color 0.08s ease" }}>
                    {w.word}
                  </span>
                );
              })}
            </div>
        }
      </div>
    </AbsoluteFill>
  );
};
