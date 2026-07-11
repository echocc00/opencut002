import { Composition } from "remotion";
import { VideoComposition } from "./VideoComposition";

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoComposition"
        component={VideoComposition}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        calculateMetadata={({ props }) => {
          const titleDur = props.data?.titleDuration || 2.0;
          const segDur = (props.data?.segments || []).reduce((s, seg) => s + (seg.actualDuration || 0), 0);
          const coverDur = props.data?.coverImage ? 3.0 : 0;
          const total = Math.max(30, Math.round((titleDur + segDur + coverDur) * 30));
          return { durationInFrames: total };
        }}
        defaultProps={{
          data: {
            title: "示例标题",
            titleDuration: 2.0,
            segments: [],
            voicePath: "",
            bgmPath: "",
            bgmVolume: 0.2,
            domain: "education",
            coverImage: "",
          },
        }}
      />
    </>
  );
};
