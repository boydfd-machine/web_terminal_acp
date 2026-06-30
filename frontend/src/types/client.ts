export type ClientRuntime = "local" | "remote";

export type ClientStatus = "ONLINE" | "OFFLINE" | "ERROR";

export type Client = {
  id: string;
  name: string;
  status: ClientStatus;
  hostname: string | null;
  install_path: string | null;
  version: string | null;
  last_update_at: string | null;
  runtime: ClientRuntime;
  last_seen_at: string | null;
  connected_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BootstrapClientInput = {
  name: string;
  host: string;
  port: number;
  username: string;
  private_key: string;
  passphrase: string | null;
  server_url: string;
};

export type BootstrapClientResult = {
  client_id: string;
  name: string;
  status: ClientStatus;
  reused: boolean;
};

export type AuthStatus = {
  enabled: boolean;
  mode?: "disabled" | "password" | "keycloak";
  keycloak?: KeycloakPublicConfig | null;
};

export type LoginResult = {
  token: string;
  refresh_token?: string | null;
  enabled: boolean;
};

export type KeycloakPublicConfig = {
  base_url: string;
  realm: string;
  client_id: string;
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint: string;
};

export type AuthCaptcha = {
  captcha_id: string;
  image_base64: string;
  ttl_seconds: number;
};

export type ClientRegistrationKeyResult = {
  id: string;
  key: string;
  label: string | null;
  created_at: string | null;
};

export type ClientUpdateResult = {
  client_id: string;
  job_id: string;
  status: "STARTED";
  method: string;
};
