import { useEffect, useState } from "react";

import { useI18n } from "../i18n";

type LoginGateProps = {
  onSubmit: (secret: string, captchaAnswer?: string) => Promise<void>;
  onKeycloakLogin?: () => void;
  mode?: "password" | "keycloak";
  error: string | null;
  captchaImageBase64: string | null;
  isSubmitting: boolean;
  backendAddress: string;
  backendAddressError: string | null;
  isCheckingBackend: boolean;
  onSaveBackendAddress: (value: string) => void;
};

type BackendAddressGateProps = {
  backendAddress: string;
  backendAddressError: string | null;
  connectionError?: string | null;
  isCheckingBackend: boolean;
  onSaveBackendAddress: (value: string) => void;
};

function BackendAddressFields({
  backendAddress,
  backendAddressError,
  isCheckingBackend,
  saveLabel,
  onSaveBackendAddress
}: {
  backendAddress: string;
  backendAddressError: string | null;
  isCheckingBackend: boolean;
  saveLabel: string;
  onSaveBackendAddress: (value: string) => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(backendAddress);

  useEffect(() => {
    setDraft(backendAddress);
  }, [backendAddress]);

  return (
    <>
      <label className="settings-field">
        <span>{t("auth.backend.address")}</span>
        <input
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSaveBackendAddress(draft);
            }
          }}
          placeholder="http://server.example.com:8001"
        />
      </label>
      <div className="settings-actions">
        <button type="button" disabled={isCheckingBackend} onClick={() => onSaveBackendAddress(draft)}>
          {saveLabel}
        </button>
        <button type="button" disabled={isCheckingBackend} onClick={() => onSaveBackendAddress("")}>
          {t("auth.backend.restoreDefault")}
        </button>
      </div>
      {backendAddressError && (
        <p className="error" role="alert">{backendAddressError}</p>
      )}
    </>
  );
}

export function BackendConnectionGate({
  backendAddress,
  backendAddressError,
  connectionError,
  isCheckingBackend,
  onSaveBackendAddress
}: BackendAddressGateProps) {
  const { t } = useI18n();

  return (
    <main className="login-shell">
      <section className="login-panel" aria-label={t("auth.backend.connection")}>
        <h1>Web Terminal ACP</h1>
        <p className="error" role="alert">
          {connectionError
            ? t("auth.backend.connectionFailedWithReason", { reason: connectionError })
            : t("auth.backend.connectionFailed")}
        </p>
        <BackendAddressFields
          backendAddress={backendAddress}
          backendAddressError={backendAddressError}
          isCheckingBackend={isCheckingBackend}
          saveLabel={t("auth.backend.saveAndRetry")}
          onSaveBackendAddress={onSaveBackendAddress}
        />
      </section>
    </main>
  );
}

export function LoginGate({
  onSubmit,
  onKeycloakLogin,
  mode = "password",
  error,
  captchaImageBase64,
  isSubmitting,
  backendAddress,
  backendAddressError,
  isCheckingBackend,
  onSaveBackendAddress
}: LoginGateProps) {
  const { t } = useI18n();
  const [secret, setSecret] = useState("");
  const isKeycloak = mode === "keycloak";
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const requiresCaptcha = captchaImageBase64 !== null;

  useEffect(() => {
    setCaptchaAnswer("");
  }, [captchaImageBase64]);

  return (
    <main className="login-shell">
      <form
        className="login-panel"
        onSubmit={(event) => {
          event.preventDefault();
          if (!isKeycloak) {
            void onSubmit(secret, captchaAnswer);
          }
        }}
      >
        <h1>Web Terminal ACP</h1>
        <BackendAddressFields
          backendAddress={backendAddress}
          backendAddressError={backendAddressError}
          isCheckingBackend={isCheckingBackend}
          saveLabel={t("auth.backend.saveAddress")}
          onSaveBackendAddress={onSaveBackendAddress}
        />
        {isKeycloak ? (
          <button type="button" disabled={isSubmitting || !onKeycloakLogin} onClick={onKeycloakLogin}>
            {t("auth.login.keycloak")}
          </button>
        ) : (
          <>
            <label className="settings-field">
              <span>{t("auth.login.secret")}</span>
              <input
                autoFocus
                type="password"
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
              />
            </label>
            {requiresCaptcha && (
              <div className="login-captcha">
                <img
                  alt={t("auth.login.captchaImage")}
                  src={`data:image/png;base64,${captchaImageBase64}`}
                />
                <label className="settings-field">
                  <span>{t("auth.login.captcha")}</span>
                  <input
                    autoCapitalize="characters"
                    autoCorrect="off"
                    spellCheck={false}
                    value={captchaAnswer}
                    onChange={(event) => setCaptchaAnswer(event.target.value)}
                  />
                </label>
              </div>
            )}
            <button
              type="submit"
              disabled={isSubmitting || secret.length === 0 || (requiresCaptcha && captchaAnswer.length === 0)}
            >
              {t("auth.login.submit")}
            </button>
          </>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </form>
    </main>
  );
}
