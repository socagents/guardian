#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.vm"
STATE_DIR="${ROOT_DIR}/.phantom-tunnels"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
else
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

: "${VM_NAME:?VM_NAME is required}"
: "${VM_ZONE:?VM_ZONE is required}"
: "${VM_PROJECT:?VM_PROJECT is required}"
: "${VM_LOCAL_SSH_PORT:=2222}"

SSH_LOCAL_PORT="${PHANTOM_SSH_LOCAL_PORT:-${VM_LOCAL_SSH_PORT}}"
AGENT_LOCAL_PORT="${PHANTOM_AGENT_LOCAL_PORT:-3000}"
MCP_LOCAL_PORT="${PHANTOM_MCP_LOCAL_PORT:-8080}"
DISABLE_CONNECTION_CHECK="${PHANTOM_TUNNEL_DISABLE_CONNECTION_CHECK:-true}"

mkdir -p "${STATE_DIR}"

# name remote_port local_port
TUNNELS=(
  "ssh 22 ${SSH_LOCAL_PORT}"
  "agent 3000 ${AGENT_LOCAL_PORT}"
  "mcp 8080 ${MCP_LOCAL_PORT}"
)

pid_file() {
  echo "${STATE_DIR}/$1.pid"
}

log_file() {
  echo "${STATE_DIR}/$1.log"
}

pid_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

port_listening() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

start_tunnel() {
  local name="$1"
  local remote_port="$2"
  local local_port="$3"
  local pf
  local lf
  local pid=""

  pf="$(pid_file "${name}")"
  lf="$(log_file "${name}")"

  if [[ -f "${pf}" ]]; then
    pid="$(cat "${pf}")"
    if pid_alive "${pid}"; then
      echo "${name}: already running on localhost:${local_port} (pid ${pid})"
      return 0
    fi
    rm -f "${pf}"
  fi

  if port_listening "${local_port}"; then
    echo "${name}: localhost:${local_port} is already in use; leaving it alone"
    return 0
  fi

  echo "${name}: opening localhost:${local_port} -> ${VM_NAME}:${remote_port}"
  local gcloud_args=(
    compute start-iap-tunnel "${VM_NAME}" "${remote_port}"
    --local-host-port="localhost:${local_port}"
    --zone="${VM_ZONE}"
    --project="${VM_PROJECT}"
  )

  if [[ "${DISABLE_CONNECTION_CHECK}" == "true" ]]; then
    gcloud_args+=(--iap-tunnel-disable-connection-check)
  fi

  pid="$(
    LOG_FILE="${lf}" python3 - "${gcloud_args[@]}" <<'PY'
import os
import subprocess
import sys

with open(os.environ["LOG_FILE"], "ab", buffering=0) as log:
    proc = subprocess.Popen(
        ["gcloud", *sys.argv[1:]],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
print(proc.pid)
PY
  )"
  echo "${pid}" > "${pf}"
  for _ in {1..20}; do
    if ! pid_alive "${pid}"; then
      break
    fi
    if port_listening "${local_port}"; then
      echo "${name}: ready (pid ${pid})"
      return 0
    fi
    sleep 0.5
  done

  if ! pid_alive "${pid}"; then
    echo "${name}: tunnel failed; see ${lf}" >&2
    rm -f "${pf}"
    return 1
  fi

  echo "${name}: tunnel did not start listening on localhost:${local_port}; see ${lf}" >&2
  kill "${pid}" >/dev/null 2>&1 || true
  rm -f "${pf}"
  return 1
}

stop_tunnel() {
  local name="$1"
  local pf
  local pid=""

  pf="$(pid_file "${name}")"
  if [[ ! -f "${pf}" ]]; then
    echo "${name}: not tracked"
    return 0
  fi

  pid="$(cat "${pf}")"
  if pid_alive "${pid}"; then
    kill "${pid}" >/dev/null 2>&1 || true
    echo "${name}: stopped pid ${pid}"
  else
    echo "${name}: stale pid ${pid}"
  fi
  rm -f "${pf}"
}

status_tunnel() {
  local name="$1"
  local remote_port="$2"
  local local_port="$3"
  local pf
  local pid=""

  pf="$(pid_file "${name}")"
  if [[ -f "${pf}" ]]; then
    pid="$(cat "${pf}")"
    if pid_alive "${pid}"; then
      echo "${name}: up localhost:${local_port} -> ${remote_port} (pid ${pid})"
      return 0
    fi
  fi

  if port_listening "${local_port}"; then
    echo "${name}: localhost:${local_port} is listening but not tracked here"
  else
    echo "${name}: down localhost:${local_port} -> ${remote_port}"
  fi
}

for_each_tunnel() {
  local action="$1"
  local entry
  local name
  local remote_port
  local local_port

  for entry in "${TUNNELS[@]}"; do
    read -r name remote_port local_port <<< "${entry}"
    "${action}" "${name}" "${remote_port}" "${local_port}"
  done
}

http_smoke() {
  local name="$1"
  local port="$2"
  local path="${3:-/}"
  local code

  code="$(curl -k -sS -m 8 -o /dev/null -w '%{http_code}' "http://localhost:${port}${path}" || true)"
  if [[ "${code}" == "000" ]]; then
    echo "${name}: fail on http://localhost:${port}${path}"
    return 1
  fi
  echo "${name}: HTTP ${code}"
}

smoke() {
  local failed=0

  start || failed=1

  http_smoke "phantom-mcp" "${MCP_LOCAL_PORT}" "/api/v1/stream/mcp" || failed=1
  http_smoke "phantom-agent" "${AGENT_LOCAL_PORT}" "/" || failed=1

  return "${failed}"
}

start() {
  for_each_tunnel start_tunnel
}

stop() {
  for_each_tunnel stop_tunnel
}

status() {
  for_each_tunnel status_tunnel
}

case "${1:-status}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    stop
    start
    ;;
  status)
    status
    ;;
  smoke)
    smoke
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|smoke}" >&2
    exit 2
    ;;
esac
