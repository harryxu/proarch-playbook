#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! command -v ansible-playbook >/dev/null 2>&1 || ! command -v ansible-galaxy >/dev/null 2>&1; then
  printf 'Ansible tools are missing. Installing Ansible...\n'
  if (( EUID == 0 )); then
    pacman -S --needed ansible
  else
    sudo pacman -S --needed ansible
  fi
fi

printf 'Checking and installing roles and collections from requirements.yml...\n'
ansible-galaxy install -r requirements.yml

if [[ ! -f config.yml ]]; then
  printf 'config.yml not found. Run cp config.yml.example config.yml, edit the configuration, then run ./start.sh again.\n' >&2
  exit 1
fi

exec ansible-playbook main.yml "$@"
