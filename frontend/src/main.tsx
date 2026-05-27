import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { applyElectronDocumentClass } from "./electronEnv";
import "./styles.css";
import "@xterm/xterm/css/xterm.css";

applyElectronDocumentClass();

const queryClient = new QueryClient();
const root = document.getElementById("root");

if (!root) {
  throw new Error('Root element "#root" was not found.');
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
