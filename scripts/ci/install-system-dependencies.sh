#!/usr/bin/env bash
set -euo pipefail

# Packages every CI job needs: the explicitly requested set plus the base
# tools that tests and scripts assume are present. rsync is required by
# scripts/sync-to-github.sh, which is exercised by the open-source release
# sync unit test.
BASE_PACKAGES=(rsync)
PACKAGES=("${BASE_PACKAGES[@]}" "$@")

APT_CACHE_ROOT="${APT_CACHE_ROOT:-$HOME/.cache/uv/apt}"
APT_ARCHIVES_DIR="$APT_CACHE_ROOT/archives"
APT_LISTS_DIR="$APT_CACHE_ROOT/lists"
APT_LOCK_FILE="$APT_CACHE_ROOT/install.lock"
APT_NEXUS_MODE="${APT_NEXUS_MODE:-auto}"
APT_NEXUS_BASE_URL="${APT_NEXUS_BASE_URL:-}"
NEXUS_SOURCES_FILE="/etc/apt/sources.list.d/web-terminal-ci-nexus.sources"

DISABLED_SOURCES=()

default_gateway_from_proc() {
  local hex
  hex="$(awk '$2 == "00000000" {print $3; exit}' /proc/net/route 2>/dev/null || true)"
  if [[ ${#hex} -ne 8 ]]; then
    return 1
  fi
  printf "%d.%d.%d.%d\n" "0x${hex:6:2}" "0x${hex:4:2}" "0x${hex:2:2}" "0x${hex:0:2}"
}

restore_extra_apt_sources() {
  local source
  for source in "${DISABLED_SOURCES[@]}"; do
    if [[ -e "$source.web-terminal-ci-disabled" ]]; then
      mv "$source.web-terminal-ci-disabled" "$source"
    fi
  done
  rm -f "$NEXUS_SOURCES_FILE"
}

disable_source() {
  local source="$1"
  if [[ -e "$source" && ! -e "$source.web-terminal-ci-disabled" ]]; then
    mv "$source" "$source.web-terminal-ci-disabled"
    DISABLED_SOURCES+=("$source")
  fi
}

disable_extra_apt_sources() {
  local source
  for source in /etc/apt/sources.list.d/*; do
    [[ -e "$source" ]] || continue
    case "$(basename "$source")" in
      debian.sources|ubuntu.sources|web-terminal-ci-nexus.sources)
        ;;
      *)
        disable_source "$source"
        ;;
    esac
  done
}

nexus_url_for_current_os() {
  # shellcheck disable=SC1091
  . /etc/os-release
  local gateway repo
  gateway="$(default_gateway_from_proc || true)"
  gateway="${gateway:-172.17.0.1}"

  case "${ID:-}" in
    ubuntu)
      repo="apt-proxy-ubuntu"
      ;;
    *)
      return 1
      ;;
  esac

  printf "%s\n" "${APT_NEXUS_BASE_URL:-http://$gateway:8081/repository/$repo}"
}

configure_nexus_apt_sources() {
  if [[ "$APT_NEXUS_MODE" == "0" || "$APT_NEXUS_MODE" == "false" || "$APT_NEXUS_MODE" == "never" ]]; then
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi

  # shellcheck disable=SC1091
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    return 1
  fi

  local codename nexus_url release_url
  codename="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
  if [[ -z "$codename" ]]; then
    return 1
  fi

  nexus_url="$(nexus_url_for_current_os)"
  release_url="${nexus_url%/}/dists/$codename/Release"
  if ! curl -fsSI --max-time 2 "$release_url" >/dev/null; then
    return 1
  fi

  disable_source "/etc/apt/sources.list.d/ubuntu.sources"
  cat >"$NEXUS_SOURCES_FILE" <<EOF
Types: deb
URIs: ${nexus_url%/}/
Suites: $codename $codename-updates $codename-backports $codename-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
  echo "Using Nexus apt proxy: ${nexus_url%/}/"
}

prepare_apt_cache() {
  mkdir -p "$APT_ARCHIVES_DIR/partial" "$APT_LISTS_DIR/partial"
  chmod -R a+rX "$APT_ARCHIVES_DIR" "$APT_LISTS_DIR"

  rm -f /etc/apt/apt.conf.d/docker-clean
  printf '%s\n' \
    'Binary::apt::APT::Keep-Downloaded-Packages "true";' \
    'APT::Keep-Downloaded-Packages "true";' \
    >/etc/apt/apt.conf.d/keep-downloaded-packages
}

apt_options() {
  printf "%s\n" \
    "-o" "Dir::Cache=$APT_CACHE_ROOT" \
    "-o" "Dir::Cache::archives=$APT_ARCHIVES_DIR" \
    "-o" "Dir::State::lists=$APT_LISTS_DIR" \
    "-o" "APT::Sandbox::User=root" \
    "-o" "Acquire::Retries=3"
}

install_packages() {
  mapfile -t options < <(apt_options)
  echo "Using apt archives cache: $APT_ARCHIVES_DIR"
  echo "Using apt lists cache: $APT_LISTS_DIR"
  apt-get "${options[@]}" update
  DEBIAN_FRONTEND=noninteractive apt-get "${options[@]}" install -y --no-install-recommends "${PACKAGES[@]}"
}

main() {
  trap restore_extra_apt_sources EXIT
  prepare_apt_cache
  disable_extra_apt_sources
  configure_nexus_apt_sources || true

  if command -v flock >/dev/null 2>&1; then
    exec 9>"$APT_LOCK_FILE"
    flock 9
  fi

  install_packages
}

main "$@"
