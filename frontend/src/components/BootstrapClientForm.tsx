import { useState } from "react";

import { readClientAgentServerUrl } from "../apiBase";
import { useI18n } from "../i18n";
import type { BootstrapClientInput } from "../types";

type BootstrapClientFormProps = {
  isSubmitting: boolean;
  onSubmit: (payload: BootstrapClientInput) => void;
};

function defaultServerUrl(): string {
  return readClientAgentServerUrl();
}

export function BootstrapClientForm({ isSubmitting, onSubmit }: BootstrapClientFormProps) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("22");
  const [username, setUsername] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [serverUrl, setServerUrl] = useState(defaultServerUrl);

  return (
    <form
      className="bootstrap-form"
      data-onboarding-id="remote-bootstrap-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          name: name.trim(),
          host: host.trim(),
          port: Number(port),
          username: username.trim(),
          private_key: privateKey,
          passphrase: passphrase === "" ? null : passphrase,
          server_url: serverUrl.trim()
        });
      }}
    >
      <h3>{t("bootstrap.title")}</h3>
      <p className="muted">
        {t("bootstrap.description")}
      </p>
      <label htmlFor="bootstrap-client-name">{t("bootstrap.name")}</label>
      <input
        id="bootstrap-client-name"
        required
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Production host"
      />

      <label htmlFor="bootstrap-client-host">{t("bootstrap.host")}</label>
      <input
        id="bootstrap-client-host"
        required
        value={host}
        onChange={(event) => setHost(event.target.value)}
        placeholder="example.com"
      />

      <label htmlFor="bootstrap-client-port">{t("bootstrap.port")}</label>
      <input
        id="bootstrap-client-port"
        required
        type="number"
        min="1"
        max="65535"
        value={port}
        onChange={(event) => setPort(event.target.value)}
      />

      <label htmlFor="bootstrap-client-username">{t("bootstrap.username")}</label>
      <input
        id="bootstrap-client-username"
        required
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        placeholder="deploy"
      />

      <label htmlFor="bootstrap-client-private-key">{t("bootstrap.privateKey")}</label>
      <textarea
        id="bootstrap-client-private-key"
        required
        rows={8}
        value={privateKey}
        onChange={(event) => setPrivateKey(event.target.value)}
        placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
      />

      <label htmlFor="bootstrap-client-passphrase">{t("bootstrap.passphrase")}</label>
      <input
        id="bootstrap-client-passphrase"
        type="password"
        value={passphrase}
        onChange={(event) => setPassphrase(event.target.value)}
        placeholder={t("bootstrap.optional")}
      />

      <label htmlFor="bootstrap-client-server-url">{t("bootstrap.serverUrl")}</label>
      <input
        id="bootstrap-client-server-url"
        required
        value={serverUrl}
        onChange={(event) => setServerUrl(event.target.value)}
      />

      <div className="bootstrap-form-actions">
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("bootstrap.submitting") : t("bootstrap.submit")}
        </button>
      </div>
    </form>
  );
}
