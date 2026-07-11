import { Audio, useVideoConfig, interpolate } from "remotion";
import { resolveAsset } from "../utils/resolveAsset";

export const Soundtrack: React.FC<{
  src: string;
  volume?: number;
  trimBeforeSeconds?: number;
  fadeInSeconds?: number;
  fadeOutSeconds?: number;
  loop?: boolean;
}> = ({ src, volume = 1, trimBeforeSeconds = 0, fadeInSeconds = 0.5, fadeOutSeconds = 0.5, loop = false }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const startFrom = Math.round(trimBeforeSeconds * fps);
  const fadeInFrames = Math.round(fadeInSeconds * fps);
  const fadeOutFrames = Math.round(fadeOutSeconds * fps);

  return (
    <Audio
      src={resolveAsset(src)}
      startFrom={startFrom}
      loop={loop}
      volume={(f: number) => {
        const fadeIn = interpolate(f, [0, fadeInFrames], [0, volume], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const fadeOut = interpolate(f, [durationInFrames - fadeOutFrames, durationInFrames], [volume, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return Math.min(fadeIn, fadeOut);
      }}
    />
  );
};
