#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_step() {
  local title="$1"
  shift
  echo
  echo "==> ${title}"
  "$@"
}

secret_scan() {
  local findings
  findings="$(bash -lc "cd '${ROOT_DIR}' && git grep -nE 'sk-[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE KEY' -- src backend frontend tests || true")"
  if [[ -n "${findings}" ]]; then
    echo "Potential secrets detected:"
    echo "${findings}"
    return 1
  fi
}

run_step "Secret smoke scan" secret_scan

run_step "Python integration and contract tests" \
  bash -lc "cd '${ROOT_DIR}' && pytest tests/test_bench_dataset.py tests/test_cli_command_hygiene.py tests/test_config_feature_flags.py tests/test_integration.py tests/test_graph_tracing.py -q"

if [[ "${VERIFY_SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  run_step "Frontend production build" \
    bash -lc "cd '${ROOT_DIR}/frontend' && npm run build"
fi

echo

echo "Verification complete: PASS"
