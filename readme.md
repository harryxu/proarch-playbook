# Proarch Playbook

Configure a personal Arch Linux development environment with an explicitly
selected **KDE** or **Omarchy** desktop profile. Both profiles share Git,
Neovim, fish, terminal preferences, development tools, fonts, ordinary
applications, Docker, and SSH. Install the base desktop before running this
playbook; the Omarchy profile customizes an existing Omarchy installation.

## Configure and run

Install Ansible on a maintained Arch Linux system, then install the collections:

```sh
sudo pacman -S --needed ansible
ansible-galaxy collection install -r requirements.yml
cp config.yml.example config.yml
```

Edit `config.yml` and choose the target desktop:

```yaml
desktop_profile: omarchy  # or kde; required
```

`config.yml` is ignored by Git. The example and shared defaults are committed.
The playbook stops before system changes if the profile is missing or invalid.
An explicit command-line choice also works:

```sh
ansible-playbook main.yml -e desktop_profile=kde
```

Validate the installed environment, preview supported changes, then apply:

```sh
ansible-playbook test.yml
ansible-playbook main.yml --check --diff
ansible-playbook main.yml
```

Check mode is a preview, not a complete first-install simulation: a checkout or
package skipped by check mode cannot supply files or tools for later tasks.
Recheck after prerequisites exist. Privilege escalation uses the existing
Ansible password prompt. Set `target_user` explicitly when the connection user
is not the intended desktop user; the user's home is resolved from the system
account database rather than assumed to be `/home/<name>`.

Profile selection configures the chosen environment. It does not uninstall
another desktop, disable existing unrelated services, or migrate a running
session. SDDM switching is opt-in with `kde_manage_display_manager: true`; it
enables the next login without stopping the current display manager.

## Configuration layers

Defaults are resolved in this order: shared defaults, profile defaults, then
host overrides. Dictionaries merge recursively; ordered lists such as bar
widgets and plugins replace the default list. Package additions concatenate
and deduplicate.

```yaml
desktop_profile: omarchy
target_user: harry
feature_overrides:
  docker: true
  bluetooth: false
  snapper: false
  keybindings: false
extra_packages: []
extra_aur_packages: []
omarchy_gdk_scale: 2
omarchy_monitors:
  - output: ""
    mode: preferred
    position: auto
    scale: 2
omarchy_overrides:
  shell:
    idle:
      lock: 600
```

| Feature | KDE default | Omarchy default |
| --- | --- | --- |
| Docker, SSH, shared dotconfig | Enabled | Enabled |
| Fcitx5 / Rime components | Enabled | Enabled |
| Rime Ice personal preference | Enabled, preserving the old playbook | Disabled, preserving the current Omarchy input scheme |
| Standalone cliphist and Vicinae services | Enabled, preserving the old playbook | Disabled; Omarchy supplies these integrations |
| Bluetooth configuration | Opt-in | Opt-in; existing Omarchy services remain intact |
| Snapper + GRUB integration | Opt-in | Opt-in only on a compatible Btrfs/GRUB host |
| KDE xremap integration | Opt-in | Unsupported; use Hyprland integration |

`false` skips a feature; it does not remove existing packages or undo earlier
configuration. Before reusing a home previously configured by the old playbook,
disable its standalone cliphist/Vicinae services if moving to Omarchy. These
are session migration actions rather than automatic profile cleanup. The old
playbook-owned Fcitx desktop autostart is recognized and disabled when native
input integration is configured.

xremap is installed only with `desktop_profile: kde` and
`feature_overrides.keybindings: true`. Its task entry point also requires KDE,
including when referenced directly from extras. Its configuration is deployed
only by the KDE profile. The launcher and systemd `ExecCondition` check the
current session's `XDG_CURRENT_DESKTOP` for a KDE/Plasma token, so an enabled
service skips startup in Hyprland, GNOME, other desktops, and headless sessions.
The service stops with the graphical session; it does not continually restart
when the desktop condition is unmet.

For multiple hosts, put `desktop_profile`, `target_user`, and host-specific
overrides in inventory host variables instead of a local `config.yml`.
A local config takes precedence over inventory values; command-line `-e`
values take precedence over both.

## Configuration ownership and backups

Shared dotconfig still comes from `harryxu/dotconfig`, with its configuration
contents unchanged. It is checked out separately under
`~/.local/share/proarch/dotconfig`. Only tracked files under `dotconfig_paths`
(and the selected profile's additional paths) are copied into `~/.config`.
Existing files receive Ansible per-file backups before replacement. Files
outside this allowlist and any existing `~/.config/.git` are preserved.

Each path has one owner: shared dotconfig manages application preferences;
the desktop profile manages its overrides; Omarchy owns packaged defaults
and generated theme files. See `docs/adr/0001-configuration-ownership.md`.
The playbook leaves package updates to normal Arch/Omarchy maintenance and
does not refresh package databases independently of a full system update.

## Captured Omarchy preferences

The profile is based on **Omarchy 4.5.0rc1-1**, using Hyprland Lua and the
Quickshell `shell.json` layout. Preflight checks the version family and required
files. Review compatibility before overriding `omarchy_overrides.version_pattern`
for a newer Omarchy release.

The maintained configuration includes:

- Personal bindings, zero window gaps, resize borders, and DropSpace autostart.
- Glassy top bar, world clocks, dock pins, a ten-minute lock, and disabled screensaver.
- Nord theme selection, Shell font size 12, and a monospace fontconfig preference.
- The current `keyboard-us` / Rime profile and nine candidates per page.
- Pinned user-owned plugins, with the obsolete `dropspace` activation entry removed.

| Plugin | Source | Pinned commit |
| --- | --- | --- |
| `harryxu.dropspace` | https://github.com/harryxu/omarchy-dropspace | `4ca53457a12f6f48e21c83cc46d01808fbd43095` |
| `io.github.matt-aaz.quick-capture` | https://github.com/Matt-aaz/omarchy-quick-capture | `9822a7200a047d389705b81cef12c37e90e0849a` |

`omarchy_overrides.plugins` replaces the complete plugin list; each entry
requires `id`, `repo` (HTTPS), and `version` (full commit). Optional `settings`
are merged into that plugin's Shell activation entry. Local uncommitted plugin
edits are preserved: Git refuses to overwrite them. Removing an entry disables
its activation without deleting its source directory.

The installed `hyprland.lua` bootstrap is retained and checked for the required
personal imports. Displays use portable scale 1 defaults; the supplied local
example uses this machine's scale 2. Theme selection uses Omarchy's headless
mode to avoid retinting shared app configuration. The playbook does not run
`omarchy font set`, which would edit shared terminal preferences.

Only actual personal overrides are captured. The current menu file is an empty
example and current Hooks are supplied by Omarchy/owe, so they are left to their
owners. Add maintained menu JSONC files under `files/omarchy/extensions/`.
Add hook scripts under `files/omarchy/hooks/` and register them, for example:

```yaml
omarchy_overrides:
  hooks:
    - event: theme-set
      name: 90-personal-theme-sync
```

Do not capture backups, plugin caches, clipboard history, notification history,
or the entire Omarchy state directory. Screen saver preference is restored
through an explicit on/off command; bar glass state is synchronized from Shell
configuration. No files under `/usr/share/omarchy` are modified.

Hyprland reload and error validation run only after configuration changes and
only when the target user's current Hyprland session is available. User services
are enabled for future sessions even without a live bus, and started only in an
active graphical session. Shell JSON and plugin code hot-reload normally;
headless provisioning takes effect on the next login.

## Layout and checks

```text
main.yml                 shared tasks, selected desktop, optional features
profiles/                KDE and Omarchy defaults
vars/packages.yml        shared package choices
tasks/configuration.yml  config loading, merging and selection validation
tasks/preflight.yml      user, platform and desktop capability checks
tasks/common/            packages, services, dotconfig and input components
tasks/desktop/           desktop-specific preferences and integrations
tasks/features/          optional legacy integrations
files/omarchy/           maintained personal files
templates/omarchy/       host-dependent displays, autostart and fonts
handlers/                change-triggered session updates
```

Use `--tags common`, `--tags dotconfig`, `--tags desktop`, or `--tags features`
after initial provisioning. Read-only selection and prerequisite checks always
run. `extras.yml` remains an optional local extension, but desktop selection
belongs in `config.yml`, not extras. `tasks/kde.yml` and `tasks/fcitx5.yml` remain
compatibility entry points; configuration is now resolved by `main.yml` first.

With Ansible, Git, Python, the required collections, and Lua's `luac` installed:

```sh
ansible-playbook main.yml --syntax-check -e desktop_profile=kde
ansible-playbook main.yml --syntax-check -e desktop_profile=omarchy
python3 tests/verify.py
```

The integration checks use disposable local Git repositories and homes under
`/tmp`. They cover required selection, both profiles, override precedence,
invalid settings, actual allowlisted copies and backups, untouched desktop
files and existing Git metadata, second-run idempotence, and Lua parsing.
They do not install packages, start services, or alter live configuration.
