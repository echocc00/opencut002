/**
 * 字幕组件 - 单行 ≤16 字分块轮播
 *
 * 整段文案按标点切成 ≤16 字的块，段内 even-split 轮播（块均分段时长）。
 * 单行、大字号、逐块淡入。段级同步不变（段 = TTS = 音频 = 画面）；
 * 块与语音近似对齐（even-split，±0.3s 内）。
 */
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { splitSubtitle } from "../utils/splitSubtitle";

interface ChunkViewProps {
  chunk: string;
  opacity: number;
  translateY: number;
}

function ChunkView({ chunk, opacity, translateY }: ChunkViewProps) {
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
          {chunk}
        </span>
      </div>
    </AbsoluteFill>
  );
}

export const WordByWordSubtitle: React.FC<{
  text: string;
  springConfig?: { damping: number; stiffness: number; mass: number };
}> = ({ text, springConfig }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const chunks = splitSubtitle(text || "", 16);

  if (chunks.length === 0) return null;

  // 单块：整段淡入（短文案）
  if (chunks.length === 1) {
    const enter = spring({ frame, fps, config: springConfig || { damping: 18, stiffness: 120 } });
    return <ChunkView chunk={chunks[0]} opacity={enter} translateY={(1 - enter) * 15} />;
  }

  // 多块：段内 even-split 轮播
  const perChunk = Math.max(durationInFrames / chunks.length, 1);
  const idx = Math.min(Math.floor(frame / perChunk), chunks.length - 1);
  const localFrame = frame - idx * perChunk;
  const fade = interpolate(localFrame, [0, 4], [0, 1], { extrapolateRight: "clamp" });
  return <ChunkView chunk={chunks[idx]} opacity={fade} translateY={(1 - fade) * 10} />;
};
