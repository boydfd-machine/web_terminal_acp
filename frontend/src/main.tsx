import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { AppQueryErrorBridge, queryClient } from "./AppQueryErrorBridge";
import { AppPromptProvider } from "./components/AppPromptProvider";
import { AppToastProvider } from "./components/AppToastProvider";
import { installAutoHideScrollbars } from "./autoHideScrollbars";
import { applyElectronDocumentClass } from "./electronEnv";
import { I18nProvider } from "./i18n";
import "./styles.css";
import "@xterm/xterm/css/xterm.css";
import "./themeSkinCoverage.css";

applyElectronDocumentClass();
installAutoHideScrollbars();

const root = document.getElementById("root");

if (!root) {
  throw new Error('Root element "#root" was not found.');
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <I18nProvider>
      <AppToastProvider>
        <QueryClientProvider client={queryClient}>
          <AppQueryErrorBridge />
          <AppPromptProvider>
            <App />
          </AppPromptProvider>
        </QueryClientProvider>
      </AppToastProvider>
    </I18nProvider>
  </React.StrictMode>
);
