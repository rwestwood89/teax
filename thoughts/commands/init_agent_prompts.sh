#!/usr/bin/env bash
set -euo pipefail

# Resolve script directory
script_source="${BASH_SOURCE[0]:-$0}"
script_dir="$(cd -- "$(dirname -- "${script_source}")" >/dev/null 2>&1 && pwd -P)"

# Ensure the script resides in thoughts/commands/
commands_dir_name="$(basename "${script_dir}")"
thoughts_dir="$(dirname "${script_dir}")"
thoughts_dir_name="$(basename "${thoughts_dir}")"
if [[ "${commands_dir_name}" != "commands" || "${thoughts_dir_name}" != "thoughts" ]]; then
  echo "This script must be located in thoughts/commands/. Current: ${script_dir}" >&2
  exit 1
fi

# Copy all .md files under thoughts/commands/agent_commands/ to ~/.codex/prompts
# only if ~/.codex exists. Otherwise, inform user to install Codex first.
agent_cmds_dir="${script_dir}/agent_commands"
if [[ -d "${HOME}/.codex" ]]; then
  mkdir -p "${HOME}/.codex/prompts"

  # Enable nullglob so the glob expands to empty when no matches are found
  shopt -s nullglob
  md_files=("${agent_cmds_dir}"/*.md)
  if (( ${#md_files[@]} > 0 )); then
    cp -v "${md_files[@]}" "${HOME}/.codex/prompts/"
  else
    echo "No .md files found in ${agent_cmds_dir} to copy." >&2
  fi
  shopt -u nullglob
else
  echo "~/.codex not found. Please install Codex first, then re-run this script." >&2
fi

# Create required relative directories inside the sibling thoughts/ directory
mkdir -p \
  "${thoughts_dir}/tickets" \
  "${thoughts_dir}/specs" \
  "${thoughts_dir}/plans" \
  "${thoughts_dir}/designs"

echo "Initialization complete."


