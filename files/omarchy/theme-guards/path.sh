# Sourced by login Bash and UWSM. Keep overrides ahead of packaged commands.
proarch_theme_bin="$HOME/.local/share/proarch/app-theme-guards/bin"
proarch_remaining_path=${PATH:-/usr/local/bin:/usr/bin}
proarch_guarded_path=$proarch_theme_bin
while :; do
  proarch_path_entry=${proarch_remaining_path%%:*}
  if [ -n "$proarch_path_entry" ] && [ "$proarch_path_entry" != "$proarch_theme_bin" ]; then
    proarch_guarded_path="$proarch_guarded_path:$proarch_path_entry"
  fi
  case "$proarch_remaining_path" in
    *:*) proarch_remaining_path=${proarch_remaining_path#*:} ;;
    *) break ;;
  esac
done
PATH=$proarch_guarded_path
export PATH
unset proarch_theme_bin proarch_remaining_path proarch_guarded_path proarch_path_entry
