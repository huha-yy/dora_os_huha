#!/usr/bin/env bash
# Ensure MINIMAX_API_KEY is in the environment.
# config.json leaves api_key null; the chatbot reads ${MINIMAX_API_KEY}.
#
# ~/.bashrc returns immediately in non-interactive shells (see its "case $-"
# guard), so we read the export line directly instead of sourcing the whole file.
if [[ -z "${MINIMAX_API_KEY:-}" && -f "${HOME}/.bashrc" ]]; then
  line="$(grep -E '^[[:space:]]*export[[:space:]]+MINIMAX_API_KEY=' "${HOME}/.bashrc" | tail -1 || true)"
  if [[ -n "${line}" ]]; then
    eval "${line}"
  fi
fi
