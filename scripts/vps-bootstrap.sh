#!/usr/bin/env bash
set -euo pipefail

SERVICE_USER="${UAB_SERVICE_USER:-uabrain}"
PROJECT_ROOT="${UAB_PROJECT_ROOT:-/opt/ultra-agents-brain}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-/opt/ultra-agents-brain/hermes}"
HERMES_SKILLS_DIR="${HERMES_SKILLS_DIR:-/opt/ultra-agents-brain/hermes/skills}"
HERMES_STATE_DIR="${HERMES_STATE_DIR:-/var/lib/ultra-agents-brain/hermes}"
SECOND_BRAIN_DIR="${SECOND_BRAIN_DIR:-/srv/second-brain}"
LOG_DIR="${UAB_LOG_DIR:-/var/log/ultra-agents-brain}"

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root or with sudo." >&2
    exit 1
  fi
}

install_packages() {
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl gnupg git gh jq ripgrep sqlite3 ufw \
    docker.io docker-compose-v2 tailscale
}

ensure_user() {
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
  usermod -aG docker "$SERVICE_USER"
}

create_directories() {
  mkdir -p "$PROJECT_ROOT" "$HERMES_CONFIG_DIR" "$HERMES_SKILLS_DIR" "$HERMES_STATE_DIR" "$SECOND_BRAIN_DIR" "$LOG_DIR"
  chown -R "$SERVICE_USER:$SERVICE_USER" "$HERMES_CONFIG_DIR" "$HERMES_STATE_DIR" "$SECOND_BRAIN_DIR" "$LOG_DIR"
}

configure_firewall() {
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
}

enable_services() {
  systemctl enable --now docker
  systemctl enable --now tailscaled
}

main() {
  require_root
  install_packages
  ensure_user
  create_directories
  configure_firewall
  enable_services

  cat <<EOF
Bootstrap complete.

Next steps:
1. Copy this repo to $PROJECT_ROOT.
2. Create $PROJECT_ROOT/.env from .env.example and fill secrets on the VPS only.
3. Run: tailscale up
4. Run: systemctl enable --now ultra-agents-brain.service
EOF
}

main "$@"
