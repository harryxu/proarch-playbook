#!/usr/bin/bash
set -euo pipefail

if (( EUID != 0 )); then
  printf 'This installer must run as root.\n' >&2
  exit 1
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
staged_file=
trap 'if [[ -n $staged_file ]]; then /usr/bin/rm -f -- "$staged_file"; fi' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

install_file() {
  local source=$1 destination=$2 mode=$3
  staged_file=$(/usr/bin/mktemp "${destination%/*}/.proarch-playbook.XXXXXX")
  /usr/bin/install -o root -g root -m "$mode" -- "$source" "$staged_file"
  if [[ $destination == /etc/sudoers.d/* ]]; then
    /usr/bin/visudo -cf "$staged_file"
  fi
  /usr/bin/mv -fT -- "$staged_file" "$destination"
  staged_file=
}

/usr/bin/visudo -c
install_file pam.conf /etc/pam.d/proarch-playbook-sudo 0644
install_file sudoers.conf /etc/sudoers.d/proarch-playbook 0440
sudoers_status=$(LC_ALL=C /usr/bin/visudo -c)
if [[ $sudoers_status != *'/etc/sudoers.d/proarch-playbook: parsed OK'* ]]; then
  printf 'The active sudoers policy does not include /etc/sudoers.d/proarch-playbook.\n' >&2
  exit 1
fi
install_file proarch-playbook-sudo /usr/local/bin/proarch-playbook-sudo 0755
printf 'Password mode is ready. Run ./start.sh --password-sudo.\n'
