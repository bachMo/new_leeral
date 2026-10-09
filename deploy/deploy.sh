#!/usr/bin/env bash
set -euo pipefail

main() {
  cd "$(dirname "$0")/.."

  git fetch --quiet origin main
  git reset --quiet --hard origin/main

  docker compose up -d --build --remove-orphans

  for _ in $(seq 1 90); do
    if curl -fsS http://127.0.0.1:8000/v1/health > /dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  curl -fsS http://127.0.0.1:8000/v1/health
  echo

  docker compose exec -T api leeral sync-prompts
  docker image prune -f > /dev/null
  docker compose ps
}

main "$@"
exit