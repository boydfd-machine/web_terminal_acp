import { useCallback, useEffect, useRef, useState } from "react";

import { useI18n } from "../i18n";
import type { BootstrapClientInput } from "../types";
import { BootstrapClientForm } from "./BootstrapClientForm";
import { ClientRegistrationKeyForm } from "./ClientRegistrationKeyForm";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type AddClientMode = "bootstrap" | "registration";

type AddClientModalProps = {
  isOpen: boolean;
  initialMode?: AddClientMode;
  bootstrapFailed: boolean;
  bootstrapPending: boolean;
  registrationKey: string | null;
  registrationKeyPending: boolean;
  registrationKeyError: string | null;
  onClose: () => void;
  onBootstrapSubmit: (payload: BootstrapClientInput) => void;
  onGenerateRegistrationKey: (label?: string | null) => void;
};

export function AddClientModal({
  isOpen,
  initialMode = "bootstrap",
  bootstrapFailed,
  bootstrapPending,
  registrationKey,
  registrationKeyPending,
  registrationKeyError,
  onClose,
  onBootstrapSubmit,
  onGenerateRegistrationKey
}: AddClientModalProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<AddClientMode>(initialMode);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
    }
  }, [initialMode, isOpen]);

  const handleEscape = useCallback(() => {
    onClose();
  }, [onClose]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: handleEscape
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="add-client-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={panelRef}
        aria-label={t("addClient.title")}
        aria-modal="true"
        className="add-client-modal"
        role="dialog"
      >
        <div className="add-client-modal-header">
          <div>
            <h2>{t("addClient.title")}</h2>
            <p className="muted">{t("addClient.description")}</p>
          </div>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("addClient.close")}
            title={t("addClient.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </div>
        <div className="add-client-mode-tabs" role="tablist" aria-label={t("addClient.mode")}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "bootstrap"}
            className={mode === "bootstrap" ? "active" : ""}
            data-onboarding-id="add-client-bootstrap-tab"
            onClick={() => setMode("bootstrap")}
          >
            {t("addClient.bootstrap")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "registration"}
            className={mode === "registration" ? "active" : ""}
            data-onboarding-id="add-client-registration-tab"
            onClick={() => setMode("registration")}
          >
            {t("addClient.registration")}
          </button>
        </div>
        {mode === "bootstrap" ? (
          <>
            <BootstrapClientForm isSubmitting={bootstrapPending} onSubmit={onBootstrapSubmit} />
            {bootstrapFailed && (
              <p className="error" role="alert">
                {t("addClient.bootstrapFailed")}
              </p>
            )}
          </>
        ) : (
          <ClientRegistrationKeyForm
            registrationKey={registrationKey}
            registrationKeyPending={registrationKeyPending}
            registrationKeyError={registrationKeyError}
            onGenerateRegistrationKey={onGenerateRegistrationKey}
          />
        )}
      </div>
    </div>
  );
}
