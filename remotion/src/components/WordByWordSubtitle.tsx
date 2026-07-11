/**
 * 字幕组件 - 整段显示（简化版）
 *
 * 不做逐词高亮和分页，直接显示完整字幕文本。
 * 消除所有时间同步问题。后续需要逐词高亮时再恢复分页逻辑。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

export const WordByWordSubtitle: React.FC<{
  words: { word: string; start: number; end: number }[];
  style: { activeColor: string; pastColor: string; upcomingColor: string };
}> = ({ words, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 把所有词拼成完整文本
  const fullText = words.map(w => w.word).join("");

  // 入场动画
  const enterProgress = spring({
    frame, fps,
    config: { damping: 18, stiffness: 120 },
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
        <span style={{
          color: "#FFFFFF",
          fontSize: 42,
          fontWeight: 700,
          fontFamily: "Noto Sans SC, sans-serif",
          whiteSpace: "pre-wrap",
          lineHeight: 1.5,
        }}>
          {fullText}
        </span>
      </div>
    </AbsoluteFill>
  );
};
