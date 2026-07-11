/**
 * 段落场景 - 模糊背景 + 图片卡片画中画
 *
 * 设计：
 * - 背景层：当前图片放大铺满全屏 + 重度模糊 + 暗化遮罩
 * - 前景层：图片卡片（圆角+阴影）居中显示
 * - 字幕层：逐词高亮字幕
 */
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { WordByWordSubtitle } from "../components/WordByWordSubtitle";
import { ThemeConfig } from "../theme";
import { useCameraMotion, pickCameraMotion } from "../utils/cameraMotion";
import { resolveAsset } from "../utils/resolveAsset";

export const SegmentScene: React.FC<{
  image: string;
  subtitleWords: { word: string; start: number; end: number }[];
  transition: string;
  theme: ThemeConfig;
  segmentIndex: number;
  segmentDuration: number;
}> = ({ image, subtitleWords, transition, theme, segmentIndex, segmentDuration }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const segFrames = Math.round(segmentDuration * fps);
  const motion = useCameraMotion(pickCameraMotion(segmentIndex), frame, segFrames);

  // 入场动画
  const enterScale = spring({ frame, fps, config: theme.springConfig });
  const enterOpacity = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: "clamp" });

  // 退出淡出
  const fadeOutStart = durationInFrames - 8;
  const exitOpacity = interpolate(
    frame, [fadeOutStart, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // transition入场效果
  let enterTransform = `scale(${enterScale})`;
  if (transition === "slide" || transition === "slide_left") {
    const slideX = interpolate(frame, [0, 8], [-80, 0], { extrapolateRight: "clamp" });
    enterTransform = `translateX(${slideX}px) scale(${enterScale})`;
  } else if (transition === "slide_right") {
    const slideX = interpolate(frame, [0, 8], [80, 0], { extrapolateRight: "clamp" });
    enterTransform = `translateX(${slideX}px) scale(${enterScale})`;
  }

  const opacity = enterOpacity * exitOpacity;
  const resolvedImage = image ? resolveAsset(image) : "";

  return (
    <AbsoluteFill style={{ backgroundColor: theme.backgroundColor }}>
      {/* 背景层：模糊放大图片 */}
      {resolvedImage && (
        <AbsoluteFill style={{ opacity }}>
          <Img src={resolvedImage} style={{
            width: "100%", height: "100%", objectFit: "cover",
            transform: `scale(1.3) translate(${motion.translateX * 0.5}px, ${motion.translateY * 0.5}px)`,
            filter: "blur(30px) brightness(0.4)",
          }} />
          {/* 暗化遮罩 */}
          <AbsoluteFill style={{ backgroundColor: "rgba(0,0,0,0.3)" }} />
        </AbsoluteFill>
      )}

      {/* 前景层：图片卡片 */}
      {resolvedImage && (
        <AbsoluteFill style={{
          justifyContent: "center",
          alignItems: "center",
          opacity,
        }}>
          <div style={{
            width: "88%", height: "58%",
            borderRadius: 16,
            overflow: "hidden",
            boxShadow: "0 16px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.08)",
            transform: enterTransform,
            position: "relative",
          }}>
            <Img src={resolvedImage} style={{
              width: "100%", height: "100%", objectFit: "cover",
              transform: `scale(${motion.scale}) translate(${motion.translateX}px, ${motion.translateY}px)`,
            }} />
          </div>
        </AbsoluteFill>
      )}

      {/* 字幕层 */}
      <WordByWordSubtitle
        words={subtitleWords || []}
        style={{
          activeColor: theme.captionHighlightColor,
          pastColor: theme.captionPastColor,
          upcomingColor: theme.captionFutureColor,
        }}
      />
    </AbsoluteFill>
  );
};
