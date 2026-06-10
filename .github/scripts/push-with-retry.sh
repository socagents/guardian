#!/usr/bin/env bash
# Pushes one or more docker image refs with retry, designed for
# transient i/o timeout failures during `docker push` to ghcr.io.
#
# Background: the self-hosted runner sits in a no-external-IP GCP
# VM behind Cloud NAT. Cloud NAT occasionally throttles concurrent
# egress connections during large blob uploads, causing one of the
# parallel layer pushes to time out and fail the whole step. Re-running
# the push usually succeeds because most layers are already on the
# registry from the first attempt — only the failed blob retries.
#
# Strategy: try each push up to 5 times with 10-second sleeps between
# attempts. Total worst-case for a single image: 5 attempts × ~3 min =
# 15 min. With three tag pushes per image and four images, the upper
# bound is high but the typical case (1 attempt each) is unchanged.
#
# Usage:
#   .github/scripts/push-with-retry.sh ghcr.io/org/img:1.2.0 \
#                                       ghcr.io/org/img:1.2 \
#                                       ghcr.io/org/img:latest
#
# Exit code: 0 if every push eventually succeeds, 1 if any push
# fails 5 times in a row.

set -euo pipefail

MAX_ATTEMPTS="${PUSH_MAX_ATTEMPTS:-5}"
SLEEP_BETWEEN="${PUSH_SLEEP_BETWEEN:-10}"

push_with_retry() {
  local img="$1"
  local attempt
  for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    if docker push "$img"; then
      if [[ $attempt -gt 1 ]]; then
        echo "::notice::push of $img succeeded on attempt $attempt"
      fi
      return 0
    fi
    if [[ $attempt -lt $MAX_ATTEMPTS ]]; then
      # ::warning:: surfaces in the GitHub Actions UI as a yellow
      # annotation — useful signal that something flaked even when
      # the run ultimately succeeds.
      echo "::warning::push of $img failed (attempt $attempt/$MAX_ATTEMPTS); retrying in ${SLEEP_BETWEEN}s"
      sleep "$SLEEP_BETWEEN"
    fi
  done
  echo "::error::push of $img failed $MAX_ATTEMPTS times — giving up"
  return 1
}

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <image:tag> [<image:tag>...]" >&2
  exit 1
fi

for img in "$@"; do
  push_with_retry "$img"
done
