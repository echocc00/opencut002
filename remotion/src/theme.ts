/**
 * 主题系统 - 基于 OpenMontage 的 ThemeConfig
 * 每个领域对应一个主题，消除硬编码颜色
 */

export interface ThemeConfig {
  primaryColor: string;
  accentColor: string;
  backgroundColor: string;
  surfaceColor: string;
  textColor: string;
  mutedTextColor: string;
  headingFont: string;
  bodyFont: string;
  springConfig: { damping: number; stiffness: number; mass: number };
  transitionDuration: number;
  captionHighlightColor: string;
  captionBackgroundColor: string;
  captionPastColor: string;
  captionFutureColor: string;
}

const TRAVEL_THEME: ThemeConfig = {
  primaryColor: "#D4734A",
  accentColor: "#4A7C6F",
  backgroundColor: "#0d0d0d",
  surfaceColor: "#1a1a1a",
  textColor: "#FAF8F5",
  mutedTextColor: "#A9A49C",
  headingFont: "Noto Serif SC, serif",
  bodyFont: "Noto Sans SC, sans-serif",
  springConfig: { damping: 15, stiffness: 100, mass: 0.8 },
  transitionDuration: 0.4,
  captionHighlightColor: "#D4734A",
  captionBackgroundColor: "rgba(0,0,0,0.65)",
  captionPastColor: "#A9A49C",
  captionFutureColor: "#78736C",
};

const EDUCATION_THEME: ThemeConfig = {
  primaryColor: "#4A7C6F",
  accentColor: "#5B8C5A",
  backgroundColor: "#0d0d0d",
  surfaceColor: "#1a1a1a",
  textColor: "#F5F2ED",
  mutedTextColor: "#A9A49C",
  headingFont: "Noto Sans SC, sans-serif",
  bodyFont: "Noto Sans SC, sans-serif",
  springConfig: { damping: 18, stiffness: 120, mass: 0.8 },
  transitionDuration: 0.3,
  captionHighlightColor: "#4A7C6F",
  captionBackgroundColor: "rgba(0,0,0,0.65)",
  captionPastColor: "#A9A49C",
  captionFutureColor: "#78736C",
};

const KNOWLEDGE_PAID_THEME: ThemeConfig = {
  primaryColor: "#D4734A",
  accentColor: "#E0A545",
  backgroundColor: "#0d0d0d",
  surfaceColor: "#1a1a1a",
  textColor: "#FAF8F5",
  mutedTextColor: "#A9A49C",
  headingFont: "Noto Serif SC, serif",
  bodyFont: "Noto Sans SC, sans-serif",
  springConfig: { damping: 12, stiffness: 80, mass: 0.8 },
  transitionDuration: 0.4,
  captionHighlightColor: "#D4734A",
  captionBackgroundColor: "rgba(0,0,0,0.65)",
  captionPastColor: "#A9A49C",
  captionFutureColor: "#78736C",
};

export const THEMES: Record<string, ThemeConfig> = {
  travel: TRAVEL_THEME,
  education: EDUCATION_THEME,
  knowledge_paid: KNOWLEDGE_PAID_THEME,
};

export function resolveTheme(domain: string): ThemeConfig {
  return THEMES[domain] || EDUCATION_THEME;
}
