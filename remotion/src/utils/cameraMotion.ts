/**
 * 相机运镜预设 - 基于 OpenMontage 的 useCameraMotion
 * 8种运镜模式：zoom-in, zoom-out, pan-left, pan-right, ken-burns, drift-up, drift-down, parallax
 */
import { interpolate } from "remotion";

export type CameraMotionType =
  | "zoom-in" | "zoom-out" | "pan-left" | "pan-right"
  | "ken-burns" | "drift-up" | "drift-down" | "parallax";

export function useCameraMotion(
  motion: CameraMotionType,
  frame: number,
  durationInFrames: number
): { scale: number; translateX: number; translateY: number } {
  const t = frame / Math.max(durationInFrames, 1);

  switch (motion) {
    case "zoom-in":
      return { scale: interpolate(t, [0, 1], [1.0, 1.2]), translateX: 0, translateY: 0 };

    case "zoom-out":
      return { scale: interpolate(t, [0, 1], [1.2, 1.0]), translateX: 0, translateY: 0 };

    case "pan-left":
      return { scale: 1.15, translateX: interpolate(t, [0, 1], [30, -30]), translateY: 0 };

    case "pan-right":
      return { scale: 1.15, translateX: interpolate(t, [0, 1], [-30, 30]), translateY: 0 };

    case "ken-burns":
      return {
        scale: interpolate(t, [0, 1], [1.05, 1.18]),
        translateX: interpolate(t, [0, 1], [-10, 10]),
        translateY: interpolate(t, [0, 1], [-5, 5]),
      };

    case "drift-up":
      return { scale: interpolate(t, [0, 1], [1.1, 1.15]), translateX: 0, translateY: interpolate(t, [0, 1], [20, -20]) };

    case "drift-down":
      return { scale: interpolate(t, [0, 1], [1.1, 1.15]), translateX: 0, translateY: interpolate(t, [0, 1], [-20, 20]) };

    case "parallax":
      return {
        scale: interpolate(t, [0, 1], [1.08, 1.12]),
        translateX: interpolate(t, [0, 1], [-15, 15]),
        translateY: interpolate(t, [0, 1], [10, -10]),
      };

    default:
      return { scale: 1.05, translateX: 0, translateY: 0 };
  }
}

// 根据 segment index 交替选择运镜
export function pickCameraMotion(index: number): CameraMotionType {
  const motions: CameraMotionType[] = ["ken-burns", "zoom-in", "pan-right", "ken-burns", "zoom-out", "pan-left"];
  return motions[index % motions.length];
}
