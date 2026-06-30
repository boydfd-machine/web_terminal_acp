import { readApiBase, readClientAgentServerUrl } from "./apiBase";

function apiPath(path: string): string {
  const base = new URL(readApiBase());
  if (!base.pathname.endsWith("/")) {
    base.pathname = `${base.pathname}/`;
  }
  return new URL(path.replace(/^\/+/, ""), base).toString();
}

export function shellSingleQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

export function registrationScriptUrl(): string {
  return apiPath("/api/clients/register-script");
}

export type RegistrationScriptInput = {
  scriptUrl: string;
  serverUrl: string;
  registrationKey: string;
  clientName: string;
};

export function buildRegistrationScript(input: RegistrationScriptInput): string {
  return [
    `curl -fsSL ${shellSingleQuote(input.scriptUrl)} -o register-client-direct.sh`,
    "chmod +x register-client-direct.sh",
    `WEB_TERMINAL_SERVER_URL=${shellSingleQuote(input.serverUrl)} \\`,
    `WEB_TERMINAL_REGISTRATION_KEY=${shellSingleQuote(input.registrationKey)} \\`,
    `WEB_TERMINAL_CLIENT_NAME=${shellSingleQuote(input.clientName)} \\`,
    "./register-client-direct.sh",
  ].join("\n");
}

export type RegistrationScriptRuntimeInput = {
  registrationKey: string;
  clientName: string;
};

export function buildRegistrationScriptFromRuntime(input: RegistrationScriptRuntimeInput): string {
  return buildRegistrationScript({
    scriptUrl: registrationScriptUrl(),
    serverUrl: readClientAgentServerUrl(),
    registrationKey: input.registrationKey,
    clientName: input.clientName,
  });
}
