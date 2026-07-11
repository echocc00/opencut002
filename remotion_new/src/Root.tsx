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
        defaultProps={{
          data: {
            title: "示例标题",
            titleDuration: 2.0,
            segments: [],
            voicePath: "",
            bgmPath: "",
            bgmVolume: 0.25,
            style: {
              activeColor: "#D4734A",
              pastColor: "#A9A49C",
              upcomingColor: "#78736C",
            },
          },
        }}
      />
    </>
  );
};
