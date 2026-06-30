import { useCallback, useEffect } from "react";
import {
  QueryCache,
  QueryClient,
  MutationCache
} from "@tanstack/react-query";

import { ApiError, ApiNetworkError, apiErrorDetailText, isApiFailure } from "./apiCore";
import { useAppToast, useOptionalAppToast } from "./components/AppToastProvider";
import { translate, useI18n, type TranslateFn } from "./i18n";

type ApiFailureListener = (error: unknown) => void;

const apiFailureListeners = new Set<ApiFailureListener>();

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => notifyApiFailure(error, query)
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => notifyApiFailure(error, mutation)
  })
});

export function AppQueryErrorBridge() {
  const { showToast } = useAppToast();
  const { t } = useI18n();

  const handleFailure = useCallback((error: unknown) => {
    if (!isApiFailure(error)) {
      return;
    }

    showToast({
      title: t("toast.apiError.title"),
      message: apiFailureToastMessage(error, t),
      tone: "error",
      dedupeKey: apiFailureDedupeKey(error)
    });
  }, [showToast, t]);

  useEffect(() => {
    apiFailureListeners.add(handleFailure);
    return () => {
      apiFailureListeners.delete(handleFailure);
    };
  }, [handleFailure]);

  return null;
}

export function apiFailureToastMessage(error: unknown, t: TranslateFn): string {
  if (error instanceof ApiError) {
    const detail = apiErrorDetailText(error.detail);
    if (detail !== null) {
      return t("toast.apiError.statusWithDetail", { status: error.status, detail });
    }
    const statusText = error.statusText.trim();
    return t("toast.apiError.status", {
      status: error.status,
      statusText: statusText.length > 0 ? statusText : t("toast.apiError.statusFallback")
    });
  }

  if (error instanceof ApiNetworkError) {
    return t("toast.apiError.network");
  }

  return t("toast.apiError.generic");
}

export function useApiFailureToast(): (error: unknown) => void {
  const toast = useOptionalAppToast();
  const { t } = useI18n();

  return useCallback((error: unknown) => {
    if (toast === null || !isApiFailure(error)) {
      return;
    }

    toast.showToast({
      title: t("toast.apiError.title"),
      message: apiFailureToastMessage(error, t),
      tone: "error",
      dedupeKey: apiFailureDedupeKey(error)
    });
  }, [toast, t]);
}

function apiFailureDedupeKey(error: ApiError | ApiNetworkError): string {
  if (error instanceof ApiError) {
    return `api:${error.status}:${apiErrorDetailText(error.detail) ?? error.statusText}`;
  }
  return `api-network:${error.message}`;
}

function notifyApiFailure(error: unknown, source?: { meta?: Record<string, unknown> }) {
  if (source?.meta?.suppressApiErrorToast === true) {
    return;
  }
  if (
    source?.meta?.suppressProjectTodoNotFoundToast === true
    && error instanceof ApiError
    && error.status === 404
    && apiErrorDetailText(error.detail) === "todo not found"
  ) {
    return;
  }

  for (const listener of apiFailureListeners) {
    listener(error);
  }
}

export const defaultApiFailureToastMessage = (error: unknown): string =>
  apiFailureToastMessage(error, (key, params) => translate("en-US", key, params));
