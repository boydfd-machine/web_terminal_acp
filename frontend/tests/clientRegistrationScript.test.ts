import { describe, expect, it } from "vitest";

import {
  buildRegistrationScript,
  shellSingleQuote,
} from "../src/clientRegistrationScript";

describe("shellSingleQuote", () => {
  it("wraps a plain string in single quotes", () => {
    expect(shellSingleQuote("abc")).toBe("'abc'");
  });

  it("escapes embedded single quotes using the closing-quote idiom", () => {
    expect(shellSingleQuote("a'b")).toBe("'a'\\''b'");
  });
});

describe("buildRegistrationScript", () => {
  const input = {
    scriptUrl: "https://example.test/api/clients/register-script",
    serverUrl: "wss://example.test/ws",
    registrationKey: "wtr_abc123",
    clientName: "remote-host",
  };

  it("emits curl, chmod, env assignments, and the run command in order", () => {
    const lines = buildRegistrationScript(input).split("\n");
    expect(lines).toEqual([
      "curl -fsSL 'https://example.test/api/clients/register-script' -o register-client-direct.sh",
      "chmod +x register-client-direct.sh",
      "WEB_TERMINAL_SERVER_URL='wss://example.test/ws' \\",
      "WEB_TERMINAL_REGISTRATION_KEY='wtr_abc123' \\",
      "WEB_TERMINAL_CLIENT_NAME='remote-host' \\",
      "./register-client-direct.sh",
    ]);
  });

  it("shell-quotes values containing single quotes so the script stays safe to paste", () => {
    const script = buildRegistrationScript({
      ...input,
      registrationKey: "wtr_a'b",
      clientName: "host';rm",
    });

    expect(script).toContain("WEB_TERMINAL_REGISTRATION_KEY='wtr_a'\\''b' \\");
    expect(script).toContain("WEB_TERMINAL_CLIENT_NAME='host'\\'';rm' \\");
  });
});
