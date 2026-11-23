#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

bootstrap_sudo=sudo
case ${1-} in
  --install-password-sudo)
    if (( $# != 1 )); then
      printf 'Usage: %s --install-password-sudo\n' "$0" >&2
      exit 2
    fi
    exec sudo /usr/bin/bash "$PWD/files/sudo/install.sh"
    ;;
  --password-sudo)
    shift
    if [[ ! -x /usr/local/bin/proarch-playbook-sudo || ! -r /etc/pam.d/proarch-playbook-sudo ]]; then
      printf 'Run %s --install-password-sudo first.\n' "$0" >&2
      exit 1
    fi
    bootstrap_sudo=/usr/local/bin/proarch-playbook-sudo
    export ANSIBLE_SUDO_EXE=$bootstrap_sudo
    ;;
esac

if ! command -v ansible-playbook >/dev/null 2>&1 || ! command -v ansible-galaxy >/dev/null 2>&1; then
  printf 'Ansible tools are missing. Installing Ansible...\n'
  if (( EUID == 0 )); then
    pacman -S --needed ansible
  else
    "$bootstrap_sudo" pacman -S --needed ansible
  fi
fi

printf 'Checking and installing roles and collections from requirements.yml...\n'
ansible-galaxy install -r requirements.yml

if [[ ! -f config.yml ]]; then
  printf 'config.yml not found. Run cp config.yml.example config.yml, edit the configuration, then run ./start.sh again.\n' >&2
  exit 1
fi

exec ansible-playbook main.yml "$@"
