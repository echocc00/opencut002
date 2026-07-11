import { AbsoluteFill, Sequence, Audio, useVideoConfig } from "remotion";
import { TitleScene } from "./scenes/TitleScene";
import { SegmentScene } from "./scenes/SegmentScene";

interface SegmentData {
  image: string;
  actualDuration: number;
  timeStart: number;
  subtitle: string;
  transition: string;
  subtitleWords: { word: string; start: number; end: number }[];
}

interface VideoData {
  title: string;
  titleDuration: number;
  segments: SegmentData[];
  voicePath: string;
  bgmPath: string;
  bgmVolume: number;
  style: {
    activeColor: string;
    pastColor: string;
    upcomingColor: string;
  };
}

export const VideoComposition: React.FC<{ data: VideoData }> = ({ data }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {data.title && (
        <Sequence
          from={0}
          durationInFrames={Math.round(data.titleDuration * fps)}
        >
          <TitleScene text={data.title} color={data.style.activeColor} />
        </Sequence>
      )}

      {data.segments.map((seg, i) => {
        const startFrame = Math.round(seg.timeStart * fps);
        const durationFrames = Math.round(seg.actualDuration * fps);
        return (
          <Sequence
            key={i}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <SegmentScene
              image={seg.image}
              subtitleWords={seg.subtitleWords}
              transition={seg.transition}
              style={data.style}
            />
          </Sequence>
        );
      })}

      {data.voicePath && <Audio src={data.voicePath} />}
      {data.bgmPath && (
        <Audio src={data.bgmPath} volume={data.bgmVolume} />
      )}
    </AbsoluteFill>
  );
};
