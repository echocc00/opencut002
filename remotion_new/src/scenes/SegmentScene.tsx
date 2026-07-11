import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { WordByWordSubtitle } from "../components/WordByWordSubtitle";

export const SegmentScene: React.FC<{
  image: string;
  subtitleWords: { word: string; start: number; end: number }[];
  transition: string;
  style: { activeColor: string; pastColor: string; upcomingColor: string };
}> = ({ image, subtitleWords, style }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.15], { extrapolateRight: "clamp" });
  const enterOpacity = interpolate(frame, [0, 5], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: enterOpacity }}>
      {image && (
        <AbsoluteFill>
          <Img src={image} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }} />
          <AbsoluteFill style={{ background: "linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0) 40%)" }} />
        </AbsoluteFill>
      )}
      <WordByWordSubtitle words={subtitleWords} style={style} />
    </AbsoluteFill>
  );
};
