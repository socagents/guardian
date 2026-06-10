#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"

cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: scripts/agent_lifecycle.sh <command>

Commands:
  start       Start the Guardian agent runtime with Docker Compose.
  stop        Stop the Guardian agent runtime.
  restart     Restart the Guardian agent runtime.
  status      Show Compose service status.
  health      Run local health probes against the Compose network ports.
  logs        Follow Compose logs.
  apply-setup Copy first-run setup values into .env and recreate the stack.
EOF
}

health_probe() {
  name="$1"
  url="$2"
  if curl -fsS --max-time 5 "$url" >/dev/null; then
    printf '%s ok %s\n' "$name" "$url"
  else
    printf '%s failed %s\n' "$name" "$url" >&2
    return 1
  fi
}

command="${1:-}"
case "$command" in
  start)
    docker compose -f "$COMPOSE_FILE" up -d
    ;;
  stop)
    docker compose -f "$COMPOSE_FILE" down
    ;;
  restart)
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d
    ;;
  status)
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  health)
    health_probe guardian-mcp http://localhost:8080/ping/
    health_probe guardian-agent http://localhost:3000/api/auth/status
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" logs -f
    ;;
  apply-setup)
    generated_env="$ROOT_DIR/.guardian-agent/.env.generated"
    if [ ! -f "$generated_env" ]; then
      printf 'No generated setup env found at %s\n' "$generated_env" >&2
      exit 1
    fi
    cp "$generated_env" "$ROOT_DIR/.env"
    chmod 600 "$ROOT_DIR/.env"
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate
    ;;
  *)
    usage
    exit 2
    ;;
esac
