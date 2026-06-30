import { useEffect, useState, type ReactNode } from "react";
import { useI18n } from "../i18n";
import { writeClipboardText } from "../terminalClipboard";
import { compactPath } from "./windowDetailData";

export function DetailTextValue({
  value,
  tone
}: {
  value: string;
  tone?: "muted" | "error";
}) {
  return <span className={tone === undefined ? "detail-value-text" : `detail-value-text ${tone}`}>{value}</span>;
}

export function DetailPathValue({ value }: { value: string | null | undefined }) {
  const { t } = useI18n();
  const displayValue = compactPath(value);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const canCopy = value !== null && value !== undefined && value.length > 0;

  useEffect(() => {
    if (copyState === "idle") {
      return;
    }
    const timeoutId = window.setTimeout(() => setCopyState("idle"), 1600);
    return () => window.clearTimeout(timeoutId);
  }, [copyState]);

  if (!canCopy) {
    return <DetailTextValue value="-" />;
  }

  return (
    <span className="detail-path-value">
      <span title={value}>{displayValue}</span>
      <button
        type="button"
        className="detail-copy-button"
        title={copyState === "copied" ? t("common.copied") : t("detail.copyPath")}
        aria-label={t("detail.copyPath")}
        onClick={() => {
          writeClipboardText(value, true)
            .then(() => setCopyState("copied"))
            .catch(() => setCopyState("failed"));
        }}
      >
        {copyState === "copied" ? t("common.copied") : t("common.copy")}
      </button>
      {copyState === "failed" && <span className="detail-copy-error" role="alert">{t("detail.copyFailed")}</span>}
    </span>
  );
}

export function DetailSection({
  title,
  children
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="detail-section" aria-label={title}>
      <h3>{title}</h3>
      <dl className="detail-list">{children}</dl>
    </section>
  );
}
