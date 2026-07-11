import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";

export const WordByWordSubtitle: React.FC<{
  words: { word: string; start: number; end: number }[];
  style: { activeColor: string; pastColor: string; upcomingColor: string };
}> = ({ words, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 120 }}>
      <div style={{ fontSize: 42, fontWeight: 600, fontFamily: "Noto Sans SC, sans-serif", textAlign: "center", maxWidth: "85%", lineHeight: 1.5 }}>
        {words.map((w, i) => {
          const isActive = currentTime >= w.start && currentTime <= w.end;
          const isPast = currentTime > w.end;
          const scale = isActive
            ? interpolate(frame, [Math.round(w.start * fps), Math.round(w.start * fps) + 3], [1.3, 1.0], { extrapolateRight: "clamp" })
            : 1.0;
          const color = isActive ? style.activeColor : isPast ? style.pastColor : style.upcomingColor;
          return (
            <span key={i} style={{ color, transform: `scale(${scale})`, display: "inline-block", marginRight: "4px", transition: "color 0.08s ease" }}>
              {w.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
