import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  createAuthCaptcha,
  fetchAuthStatus,
  login,
} from "./api";
import {
  authChangedEventName,
  buildKeycloakLoginUrl,
  clearAuthToken,
  consumeKeycloakRedirect,
  readAuthToken,
  writeAuthTokens,
} from "./auth";
import { readApiBase, writeConfiguredApiBase } from "./apiBase";
import { BackendConnectionGate, LoginGate } from "./components/LoginGate";
import { useI18n } from "./i18n";
import { ApiError } from "./apiCore";
import type { AuthCaptcha } from "./types";

type AppAuthGateProps = {
  children: (props: { authEnabled: boolean; onLogout: () => void }) => ReactNode;
};

export function AppAuthGate({ children }: AppAuthGateProps) {
  const { t } = useI18n();
  const [authToken, setAuthToken] = useState<string | null>(readAuthToken);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState(readApiBase);
  const [apiBaseRevision, setApiBaseRevision] = useState(0);
  const [apiBaseError, setApiBaseError] = useState<string | null>(null);
  const [captcha, setCaptcha] = useState<AuthCaptcha | null>(null);
  const queryClient = useQueryClient();
  const authStatusQuery = useQuery({
    queryKey: ["auth-status", apiBase, apiBaseRevision],
    queryFn: fetchAuthStatus,
    retry: false,
  });

  useEffect(() => {
    const handleAuthChanged = () => {
      const nextToken = readAuthToken();
      setAuthToken(nextToken);
      if (nextToken === null) {
        queryClient.clear();
      }
    };
    window.addEventListener(authChangedEventName(), handleAuthChanged);
    return () => {
      window.removeEventListener(authChangedEventName(), handleAuthChanged);
    };
  }, [queryClient]);

  useEffect(() => {
    if (authStatusQuery.data?.mode !== "keycloak" || authToken !== null) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    if (!params.has("code") || !params.has("state")) {
      return;
    }
    let cancelled = false;
    void consumeKeycloakRedirect(window.location.search)
      .then((token) => {
        if (cancelled || token === null) {
          return;
        }
        setAuthToken(token);
        setLoginError(null);
        queryClient.invalidateQueries();
      })
      .catch(() => {
        if (!cancelled) {
          clearAuthToken();
          setAuthToken(null);
          setLoginError(t("auth.login.keycloakFailed"));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authStatusQuery.data?.mode, authToken, queryClient, t]);

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      writeAuthTokens(result.token, result.refresh_token ?? null);
      setAuthToken(result.token);
      setLoginError(null);
      setCaptcha(null);
      queryClient.invalidateQueries();
    },
    onError: async (error) => {
      clearAuthToken();
      setAuthToken(null);
      if (isCaptchaRequired(error)) {
        try {
          setCaptcha(await createAuthCaptcha());
          setLoginError(t("auth.login.captchaRequired"));
        } catch {
          setCaptcha(null);
          setLoginError(t("auth.login.captchaLoadFailed"));
        }
      } else {
        setLoginError(t("auth.login.invalidSecret"));
      }
    },
  });

  const logout = useCallback(() => {
    clearAuthToken();
    setAuthToken(null);
    queryClient.clear();
  }, [queryClient]);

  const saveBackendAddress = useCallback((value: string) => {
    try {
      writeConfiguredApiBase(value);
      const nextApiBase = readApiBase();
      clearAuthToken();
      setAuthToken(null);
      setApiBase(nextApiBase);
      setApiBaseRevision((revision) => revision + 1);
      setApiBaseError(null);
      setLoginError(null);
      setCaptcha(null);
      queryClient.clear();
    } catch {
      setApiBaseError(t("auth.backend.invalidAddress"));
    }
  }, [queryClient, t]);

  const submitLogin = useCallback(async (secret: string, captchaAnswer?: string) => {
    await loginMutation.mutateAsync({
      secret,
      captchaId: captcha?.captcha_id ?? null,
      captchaAnswer: captchaAnswer ?? null,
    });
  }, [captcha, loginMutation]);

  const startKeycloakLogin = useCallback(async () => {
    const config = authStatusQuery.data?.keycloak;
    if (!config) {
      setLoginError(t("auth.login.keycloakUnavailable"));
      return;
    }
    try {
      window.location.assign(await buildKeycloakLoginUrl(config));
    } catch {
      setLoginError(t("auth.login.keycloakFailed"));
    }
  }, [authStatusQuery.data?.keycloak, t]);

  const authRequired = authStatusQuery.data?.enabled === true;
  const authReady = authStatusQuery.isSuccess && (!authRequired || authToken !== null);

  if (authStatusQuery.isLoading) {
    return (
      <main className="login-shell">
        <p className="muted">{t("app.loading")}</p>
      </main>
    );
  }

  if (authStatusQuery.isError) {
    return (
      <BackendConnectionGate
        backendAddress={apiBase}
        backendAddressError={apiBaseError}
        connectionError={authStatusQuery.error instanceof Error ? authStatusQuery.error.message : null}
        isCheckingBackend={authStatusQuery.isFetching}
        onSaveBackendAddress={saveBackendAddress}
      />
    );
  }

  if (!authReady) {
    return (
      <LoginGate
        backendAddress={apiBase}
        backendAddressError={apiBaseError}
        error={loginError}
        captchaImageBase64={captcha?.image_base64 ?? null}
        isCheckingBackend={authStatusQuery.isFetching}
        isSubmitting={loginMutation.isPending}
        mode={authStatusQuery.data?.mode === "keycloak" ? "keycloak" : "password"}
        onKeycloakLogin={startKeycloakLogin}
        onSaveBackendAddress={saveBackendAddress}
        onSubmit={submitLogin}
      />
    );
  }

  return <>{children({ authEnabled: authRequired, onLogout: logout })}</>;
}

function isCaptchaRequired(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return false;
  }
  if (error.status !== 429) {
    return false;
  }
  const body = error.body;
  return typeof body === "object"
    && body !== null
    && "code" in body
    && (body as { code?: unknown }).code === "captcha_required";
}
