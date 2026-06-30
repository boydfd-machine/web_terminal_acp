import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import { UiIcon } from "./UiIcon";
import { useI18n } from "../i18n";

type AppToastTone = "error";

export type AppToastInput = {
  message: string;
  title?: string;
  tone?: AppToastTone;
  dedupeKey?: string;
};

type AppToastState = {
  id: number;
  message: string;
  title: string;
  tone: AppToastTone;
};

type AppToastContextValue = {
  showToast: (input: AppToastInput) => void;
};

const TOAST_DURATION_MS = 5000;
const TOAST_DEDUPE_MS = 30000;

const AppToastContext = createContext<AppToastContextValue | null>(null);

export function AppToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toast, setToast] = useState<AppToastState | null>(null);
  const nextToastIdRef = useRef(0);
  const recentToastKeysRef = useRef<Map<string, number>>(new Map());

  const dismissToast = useCallback((id: number) => {
    setToast((current) => (current?.id === id ? null : current));
  }, []);

  const showToast = useCallback((input: AppToastInput) => {
    const message = input.message.trim();
    if (message.length === 0) {
      return;
    }

    const now = Date.now();
    const dedupeKey = input.dedupeKey ?? `${input.tone ?? "error"}:${input.title ?? ""}:${message}`;
    const recentAt = recentToastKeysRef.current.get(dedupeKey);
    if (recentAt !== undefined && now - recentAt < TOAST_DEDUPE_MS) {
      return;
    }

    recentToastKeysRef.current.set(dedupeKey, now);
    for (const [key, timestamp] of recentToastKeysRef.current) {
      if (now - timestamp > TOAST_DEDUPE_MS) {
        recentToastKeysRef.current.delete(key);
      }
    }

    nextToastIdRef.current += 1;
    setToast({
      id: nextToastIdRef.current,
      message,
      title: input.title ?? t("toast.apiError.title"),
      tone: input.tone ?? "error"
    });
  }, [t]);

  const value = useMemo<AppToastContextValue>(() => ({ showToast }), [showToast]);

  return (
    <AppToastContext.Provider value={value}>
      {children}
      <AppToast toast={toast} onDismiss={dismissToast} />
    </AppToastContext.Provider>
  );
}

export function useAppToast(): AppToastContextValue {
  const context = useContext(AppToastContext);
  if (context === null) {
    throw new Error("useAppToast must be used within AppToastProvider");
  }
  return context;
}

export function useOptionalAppToast(): AppToastContextValue | null {
  return useContext(AppToastContext);
}

function AppToast({
  toast,
  onDismiss
}: {
  toast: AppToastState | null;
  onDismiss: (id: number) => void;
}) {
  const { t } = useI18n();

  useEffect(() => {
    if (toast === null) {
      return;
    }

    const timeout = window.setTimeout(() => onDismiss(toast.id), TOAST_DURATION_MS);
    return () => window.clearTimeout(timeout);
  }, [onDismiss, toast]);

  if (toast === null) {
    return null;
  }

  return (
    <div className={`app-toast ${toast.tone}`} role="alert" aria-live="assertive">
      <UiIcon name="alert-triangle" className="app-toast-icon" />
      <div className="app-toast-content">
        <strong>{toast.title}</strong>
        <span>{toast.message}</span>
      </div>
      <button
        type="button"
        className="app-toast-dismiss"
        aria-label={t("toast.dismiss")}
        title={t("toast.dismiss")}
        onClick={() => onDismiss(toast.id)}
      >
        <UiIcon name="x" className="app-toast-dismiss-icon" />
      </button>
    </div>
  );
}
