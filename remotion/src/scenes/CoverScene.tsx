import { AbsoluteFill, Img, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import { ThemeConfig } from "../theme";
import { resolveAsset } from "../utils/resolveAsset";

export const CoverScene: React.FC<{ image: string; title: string; theme: ThemeConfig }> = ({ image, title, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: theme.springConfig });
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const bgOpacity = interpolate(frame, [0, 5], [0, 0.8], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill>
      {image && (
        <AbsoluteFill>
          <Img src={resolveAsset(image)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }} />
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{ backgroundColor: "rgba(0,0,0,0.7)", opacity: bgOpacity }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity, padding: "0 60px" }}>
        <h1 style={{
          color: "#FFFFFF", fontSize: 44, fontWeight: 700,
          fontFamily: theme.headingFont, textAlign: "center", lineHeight: 1.4,
          textShadow: "0 4px 20px rgba(0,0,0,0.8)",
        }}>{title}</h1>
        <div style={{
          marginTop: 30, width: 60, height: 4,
          backgroundColor: theme.primaryColor, borderRadius: 2,
          opacity: interpolate(frame, [15, 25], [0, 1], { extrapolateRight: "clamp" }),
        }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
