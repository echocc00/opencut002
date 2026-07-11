import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { ThemeConfig } from "../theme";

export const TitleScene: React.FC<{ text: string; theme: ThemeConfig }> = ({ text, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: theme.enterSpring });
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", backgroundColor: theme.backgroundColor }}>
      <h1 style={{
        color: theme.primaryColor, fontSize: 48, fontWeight: 700,
        fontFamily: theme.headingFont,
        transform: `scale(${scale})`, opacity,
        textShadow: "0 4px 20px rgba(0,0,0,0.5)", textAlign: "center", padding: "0 60px",
      }}>{text}</h1>
    </AbsoluteFill>
  );
};
