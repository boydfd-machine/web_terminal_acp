import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import { useI18n, type TranslationKey } from "../i18n";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

export type AppConfirmTone = "default" | "danger";

export type AppConfirmOptions = {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: AppConfirmTone;
};

type PendingConfirm = Required<AppConfirmOptions> & {
  id: number;
  resolve: (confirmed: boolean) => void;
};

type AppPromptContextValue = {
  confirm: (options: AppConfirmOptions) => Promise<boolean>;
};

const AppPromptContext = createContext<AppPromptContextValue | null>(null);

function translatedOrProvided(t: (key: TranslationKey) => string, value: string | undefined, key: TranslationKey): string {
  return value ?? t(key);
}

export function AppPromptProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const activeConfirmRef = useRef<PendingConfirm | null>(null);
  const nextIdRef = useRef(0);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const settleConfirm = useCallback((confirmed: boolean) => {
    const current = activeConfirmRef.current;
    if (current === null) {
      return;
    }

    activeConfirmRef.current = null;
    setPendingConfirm(null);
    current.resolve(confirmed);
  }, []);

  const confirm = useCallback((options: AppConfirmOptions): Promise<boolean> => {
    if (activeConfirmRef.current !== null) {
      return Promise.resolve(false);
    }

    return new Promise((resolve) => {
      const request: PendingConfirm = {
        id: nextIdRef.current,
        title: translatedOrProvided(t, options.title, "prompt.confirm.title"),
        message: options.message,
        confirmLabel: translatedOrProvided(t, options.confirmLabel, "prompt.confirm.submit"),
        cancelLabel: translatedOrProvided(t, options.cancelLabel, "prompt.confirm.cancel"),
        tone: options.tone ?? "default",
        resolve
      };
      nextIdRef.current += 1;
      activeConfirmRef.current = request;
      setPendingConfirm(request);
    });
  }, [t]);

  useOverlayFocus({
    isOpen: pendingConfirm !== null,
    ref: panelRef,
    onEscape: () => settleConfirm(false),
    initialFocusSelector: ".app-prompt-cancel"
  });

  const value = useMemo<AppPromptContextValue>(() => ({ confirm }), [confirm]);

  return (
    <AppPromptContext.Provider value={value}>
      {children}
      {pendingConfirm !== null && (
        <div
          className="app-prompt-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              settleConfirm(false);
            }
          }}
        >
          <div
            key={pendingConfirm.id}
            ref={panelRef}
            aria-describedby="app-prompt-message"
            aria-labelledby="app-prompt-title"
            aria-modal="true"
            className={`app-prompt-dialog app-prompt-${pendingConfirm.tone}`}
            role="alertdialog"
          >
            <div className="app-prompt-icon" aria-hidden="true">
              <UiIcon name="alert-triangle" />
            </div>
            <div className="app-prompt-content">
              <h2 id="app-prompt-title">{pendingConfirm.title}</h2>
              <p id="app-prompt-message">{pendingConfirm.message}</p>
            </div>
            <div className="app-prompt-actions">
              <button
                type="button"
                className="app-prompt-cancel"
                onClick={() => settleConfirm(false)}
              >
                {pendingConfirm.cancelLabel}
              </button>
              <button
                type="button"
                className="app-prompt-confirm"
                data-tone={pendingConfirm.tone}
                onClick={() => settleConfirm(true)}
              >
                {pendingConfirm.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppPromptContext.Provider>
  );
}

export function useAppPrompt(): AppPromptContextValue {
  const context = useContext(AppPromptContext);
  if (context === null) {
    throw new Error("useAppPrompt must be used within AppPromptProvider");
  }
  return context;
}
