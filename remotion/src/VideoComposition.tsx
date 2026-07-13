import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { TitleScene } from "./scenes/TitleScene";
import { SegmentScene } from "./scenes/SegmentScene";
import { CoverScene } from "./scenes/CoverScene";
import { Soundtrack } from "./components/Soundtrack";
import { AiLabel } from "./components/AiLabel";
import { resolveTheme } from "./theme";

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
  coverImage?: string;
  domain?: string;
  aiLabel?: boolean;
}

export const VideoComposition: React.FC<{ data: VideoData }> = ({ data }) => {
  const { fps } = useVideoConfig();
  const theme = resolveTheme(data.domain || "education");

  const titleFrames = Math.round(data.titleDuration * fps);
  const segmentsDuration = data.segments.reduce((s, seg) => s + seg.actualDuration, 0);
  const coverFrames = Math.round(3.0 * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.backgroundColor }}>
      {/* Layer 1: 标题 */}
      {data.title && (
        <Sequence from={0} durationInFrames={titleFrames}>
          <TitleScene text={data.title} theme={theme} />
        </Sequence>
      )}

      {/* Layer 2: 分镜段落（从标题后开始） */}
      {data.segments.map((seg, i) => {
        const startFrame = titleFrames + Math.round(seg.timeStart * fps);
        const durationFrames = Math.round(seg.actualDuration * fps);
        return (
          <Sequence key={i} from={startFrame} durationInFrames={durationFrames}>
            <SegmentScene
              image={seg.image}
              subtitle={seg.subtitle}
              transition={seg.transition}
              theme={theme}
              segmentIndex={i}
              segmentDuration={seg.actualDuration}
            />
          </Sequence>
        );
      })}

      {/* Layer 3: 封面 */}
      {data.coverImage && (
        <Sequence from={titleFrames + Math.round(segmentsDuration * fps)} durationInFrames={coverFrames}>
          <CoverScene image={data.coverImage} title={data.title} theme={theme} />
        </Sequence>
      )}

      {/* Layer 4: 音轨 */}

      {/* BGM: 从第0秒开始（标题期间也有背景音乐） */}
      {data.bgmPath && (
        <Soundtrack src={data.bgmPath} volume={data.bgmVolume} fadeInSeconds={1.0} fadeOutSeconds={1.0} loop={true} />
      )}

      {/* 配音: 从标题后开始（和分镜同步） */}
      {data.voicePath && (
        <Sequence from={titleFrames}>
          <Soundtrack src={data.voicePath} volume={1.0} fadeInSeconds={0.3} fadeOutSeconds={0.5} />
        </Sequence>
      )}

      {/* Layer 5: AI 生成标识（合规储备，默认关，由 aiLabel 字段控制） */}
      <AiLabel visible={data.aiLabel ?? false} />
    </AbsoluteFill>
  );
};
