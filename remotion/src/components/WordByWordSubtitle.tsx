/**
 * 字幕组件 - 整段淡入
 *
 * 一句字幕整段淡入显示（spring opacity + 上移），暗色背板保证可读性。
 * 不逐词高亮 -- 句子-画面对齐由段落级 TTS 时长保证。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from "remotion";

export const WordByWordSubtitle: React.FC<{
  text: string;
  springConfig?: { damping: number; stiffness: number; mass: number };
}> = ({ text, springConfig }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

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
        transform: `translateY(${(1 - enterProgress) * 15}px)`,
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
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
