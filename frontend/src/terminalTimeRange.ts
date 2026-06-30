import type { TranslationKey } from "./i18n";

export type TerminalTimeRange = "1d" | "3d" | "5d" | "7d" | "14d" | "30d" | "all";
export type TerminalTimeRangeOption = {
  value: TerminalTimeRange;
  label: string;
  labelKey: TranslationKey;
};

export const DEFAULT_TERMINAL_TIME_RANGE: TerminalTimeRange = "7d";

export const TERMINAL_TIME_RANGE_OPTIONS: TerminalTimeRangeOption[] = [
  { value: "1d", label: "1天", labelKey: "timeRange.1d" },
  { value: "3d", label: "3天", labelKey: "timeRange.3d" },
  { value: "5d", label: "5天", labelKey: "timeRange.5d" },
  { value: "7d", label: "7天", labelKey: "timeRange.7d" },
  { value: "14d", label: "2周", labelKey: "timeRange.14d" },
  { value: "30d", label: "1个月", labelKey: "timeRange.30d" },
  { value: "all", label: "全部", labelKey: "timeRange.all" }
];

export function isTerminalTimeRange(value: unknown): value is TerminalTimeRange {
  return TERMINAL_TIME_RANGE_OPTIONS.some((option) => option.value === value);
}
