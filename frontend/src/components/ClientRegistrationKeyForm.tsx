import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { buildRegistrationScriptFromRuntime } from "../clientRegistrationScript";
import { useI18n } from "../i18n";
import { writeClipboardText } from "../terminalClipboard";
import { UiIcon } from "./UiIcon";

type ClientRegistrationKeyFormProps = {
  registrationKey: string | null;
  registrationKeyPending: boolean;
  registrationKeyError: string | null;
  onGenerateRegistrationKey: (label?: string | null) => void;
};

type PendingGeneratedScriptCopy = {
  previousKey: string | null;
};

export function ClientRegistrationKeyForm({
  registrationKey,
  registrationKeyPending,
  registrationKeyError,
  onGenerateRegistrationKey
}: ClientRegistrationKeyFormProps) {
  const { t } = useI18n();
  const [registrationClientName, setRegistrationClientName] = useState("");
  const [scriptCopyState, setScriptCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const pendingGeneratedScriptCopyRef = useRef<PendingGeneratedScriptCopy | null>(null);
  const effectiveRegistrationClientName = registrationClientName.trim() || t("registration.clientNameToken");
  const registrationScript = useMemo(() => buildRegistrationScriptFromRuntime({
    registrationKey: registrationKey ?? t("registration.keyToken"),
    clientName: effectiveRegistrationClientName,
  }), [effectiveRegistrationClientName, registrationKey, t]);
  const canGenerate = !registrationKeyPending && registrationClientName.trim().length > 0;

  const copyRegistrationScript = useCallback(() => {
    writeClipboardText(registrationScript, true)
      .then(() => setScriptCopyState("copied"))
      .catch(() => setScriptCopyState("failed"));
  }, [registrationScript]);

  useEffect(() => {
    if (scriptCopyState === "idle") {
      return;
    }
    const timeoutId = window.setTimeout(() => setScriptCopyState("idle"), 1600);
    return () => window.clearTimeout(timeoutId);
  }, [scriptCopyState]);

  useEffect(() => {
    if (
      registrationKey === null
      || pendingGeneratedScriptCopyRef.current === null
      || pendingGeneratedScriptCopyRef.current.previousKey === registrationKey
    ) {
      return;
    }
    pendingGeneratedScriptCopyRef.current = null;
    copyRegistrationScript();
  }, [copyRegistrationScript, registrationKey]);

  useEffect(() => {
    if (registrationKeyPending) {
      return;
    }
    if (registrationKeyError !== null) {
      pendingGeneratedScriptCopyRef.current = null;
    }
  }, [registrationKeyError, registrationKeyPending]);

  return (
    <section className="client-registration-key-form" data-onboarding-id="remote-registration-panel">
      <h3>{t("registration.title")}</h3>
      <p className="muted">
        {t("registration.description")}
      </p>
      <label className="settings-field">
        <span>{t("registration.clientName")}</span>
        <input
          value={registrationClientName}
          onChange={(event) => setRegistrationClientName(event.target.value)}
          placeholder={t("registration.clientNamePlaceholder")}
        />
      </label>
      <div className="registration-generate-actions">
        <button
          type="button"
          disabled={!canGenerate}
          onClick={() => onGenerateRegistrationKey(registrationClientName.trim() || null)}
        >
          {registrationKeyPending ? t("registration.generating") : t("registration.generate")}
        </button>
        <button
          type="button"
          disabled={!canGenerate}
          onClick={() => {
            pendingGeneratedScriptCopyRef.current = { previousKey: registrationKey };
            onGenerateRegistrationKey(registrationClientName.trim() || null);
          }}
        >
          {registrationKeyPending ? t("registration.generating") : t("registration.generateAndCopyScript")}
        </button>
      </div>
      {registrationKeyError && (
        <p className="error settings-error" role="alert">
          {registrationKeyError}
        </p>
      )}
      {registrationKey && (
        <label className="settings-field">
          <span>{t("registration.key")}</span>
          <textarea readOnly rows={3} value={registrationKey} />
        </label>
      )}
      <label className="settings-field">
        <span className="registration-script-label">
          <span>{t("registration.script")}</span>
          <button
            type="button"
            className="ui-icon-button registration-script-copy-button"
            aria-label={t("registration.copyScript")}
            title={scriptCopyState === "copied" ? t("common.copied") : t("registration.copyScript")}
            onClick={copyRegistrationScript}
          >
            <UiIcon name="copy" />
          </button>
        </span>
        <textarea readOnly rows={7} value={registrationScript} />
      </label>
      {scriptCopyState === "copied" && (
        <p className="registration-script-copy-status">{t("registration.scriptCopied")}</p>
      )}
      {scriptCopyState === "failed" && (
        <p className="error settings-error" role="alert">{t("registration.copyScriptFailed")}</p>
      )}
    </section>
  );
}
