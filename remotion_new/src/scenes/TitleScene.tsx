import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, spring } from "remotion";

export const TitleScene: React.FC<{ text: string; color: string }> = ({ text, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: { damping: 12, stiffness: 100, mass: 0.8 } });
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", backgroundColor: "#000" }}>
      <h1 style={{
        color, fontSize: 72, fontWeight: 700, fontFamily: "Noto Serif SC, serif",
        transform: `scale(${scale})`, opacity, textShadow: "0 4px 20px rgba(0,0,0,0.5)",
      }}>{text}</h1>
    </AbsoluteFill>
  );
};
