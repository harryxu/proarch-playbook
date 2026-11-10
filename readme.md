# Proarch Playbook

Configure a personal Arch Linux development environment with an explicitly
selected **KDE** or **Omarchy** desktop profile. Both profiles share Git,
Neovim, fish, terminal preferences, development tools, font packages, ordinary
applications, Docker, and SSH. Install the base desktop before running this
playbook; the Omarchy profile customizes an existing Omarchy installation.

## Configure and run

Install Ansible on a maintained Arch Linux system, then install the collections:

```sh
sudo pacman -S --needed ansible
ansible-galaxy collection install -r requirements.yml
cp config.yml.example config.yml
```

Edit `config.yml` to choose the target desktop, optional features, additional
packages, and machine-specific settings. This is the only host configuration
file needed after cloning:

```yaml
desktop_profile: omarchy  # or kde; required
```

`config.yml` is ignored by Git. The example and shared defaults are committed.
The playbook stops before system changes if the profile is missing or invalid.
After editing `config.yml`, you can use the bootstrap script:

```sh
./start.sh
```

It installs Ansible through pacman when needed, installs the roles and collections
declared in `requirements.yml`, checks that `config.yml` exists, then runs
`ansible-playbook main.yml`. If the config is missing, it prints setup instructions
and exits. Run the script as your desktop user; it uses sudo only to install
Ansible. Additional arguments are forwarded to the playbook, for example
`./start.sh --check --diff`.

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
omarchy_overrides:
  shell:
    idle:
      lock: 600
```

| Feature | KDE default | Omarchy default |
| --- | --- | --- |
| Docker, SSH, shared dotconfig | Enabled | Enabled |
| Fcitx5 / Rime components | Enabled | Enabled |
| Rime Ice personal preference | Enabled | Enabled |
| Standalone cliphist and Vicinae services | Enabled, preserving the old playbook | Disabled; Omarchy supplies these integrations |
| Bluetooth configuration | Opt-in | Opt-in; existing Omarchy services remain intact |
| Snapper + GRUB integration | Opt-in | Opt-in only on a compatible Btrfs/GRUB host |
| KDE xremap integration | Opt-in | Unsupported; use Hyprland integration |
| USB APFS automount | Unsupported by this playbook | Opt-in, read-only |
| Intel Titan Ridge USB hotplug workaround on matching T2 Macs | Automatic | Automatic |

`false` skips a feature; it does not remove existing packages or undo earlier
configuration. Before reusing a home previously configured by the old playbook,
disable its standalone cliphist/Vicinae services if moving to Omarchy. These
are session migration actions rather than automatic profile cleanup. The old
playbook-owned Fcitx desktop autostart is recognized and disabled when native
input integration is configured.

xremap is installed only with `desktop_profile: kde` and
`feature_overrides.keybindings: true`. Its task entry point also requires KDE,
including when its task file is imported directly. Its configuration is deployed
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
and generated theme files. The Omarchy profile manages the GTK/Qt application and
Fcitx candidate fonts. Terminal/monospace fonts, Shell font sizes, monitor
layouts, and display scaling remain under each host's control.
See `docs/adr/0001-configuration-ownership.md`.
The playbook leaves package updates to normal Arch/Omarchy maintenance and
does not refresh package databases independently of a full system update.

To make a MacBook Pro Touch Bar show function keys by default, follow
[Touch Bar function keys](docs/macbook-touch-bar.md).

### USB drives

The playbook detects the Apple T2 chip and Intel Titan Ridge xHCI controllers
(`8086:15ec`) on the target's PCI bus. When both are present, it keeps those
controllers out of runtime suspend to allow USB hotplug. This can increase idle
power use. Remove any old `t2_usb_hotplug` entry from `feature_overrides`.
Hardware detection now controls the workaround.

To explicitly configure read-only APFS mounting on Omarchy, add this option to
the existing `feature_overrides` in `config.yml`.

```yaml
feature_overrides:
  apfs_automount: true
```

`apfs_automount` uses Omarchy's existing desktop automounter after login.
It loads the running kernel's APFS module and defaults USB APFS mounts to
read-only through UDisks. The open-source kernel driver requires an
unencrypted APFS volume. If the running kernel lacks the module, add
`linux-apfs-rw-dkms` and the headers for that kernel to `extra_packages`
and run the full playbook to install them first.

To apply only the removable storage tasks, use the dedicated tag.

```sh
ansible-playbook main.yml --tags removable_storage
```

## Captured Omarchy preferences

The profile is based on **Omarchy 4.5.0rc1-1**, using Hyprland Lua and the
Quickshell `shell.json` layout. Preflight checks the version family and required
files. Review compatibility before overriding `omarchy_overrides.version_pattern`
for a newer Omarchy release.

The maintained configuration includes:

- Personal bindings, zero window gaps, resize borders, and DropSpace autostart.
- [Omasnap](https://github.com/omacom/omasnap) screenshots on **Super+Ctrl+A**,
  replacing the audio panel shortcut. Flameshot is installed only by the KDE
  profile; existing packages are not automatically removed.
- Glassy top bar, world clocks, dock pins, a ten-minute lock, and disabled screensaver.
- The system theme is selected manually in Omarchy and is never changed by
  this playbook.
- SpaceX Starship launch wallpapers from the stock Tokyo Night and Starship
  themes are stored in `~/Pictures/Wallpapers` and linked into each theme's
  user backgrounds during setup and after theme changes. See
  [Omarchy wallpapers](docs/omarchy-wallpapers.md) for usage and configuration.
- The current `keyboard-us` / Rime profile and nine candidates per page.
- `nwg-look` for graphical GTK preferences, GTK/Qt font `Noto Sans CJK SC 11`,
  and Fcitx candidate font `Noto Sans CJK SC 12`. Override `gtk_font` and
  `fcitx_font` under `omarchy_overrides` in `config.yml` for a particular host.
  Only the font keys are updated; existing GTK settings and Fcitx themes are
  preserved, with per-file backups before changes. The GTK font is also stored
  in dconf, as used by `nwg-look`; its module dependencies are installed with
  the Omarchy profile. Fcitx font changes use the existing reload handler and
  apply only when the input method feature is enabled.
- Qt applications use Omarchy's existing `gtk3` platform theme to read the GTK
  font family and size. The playbook explicitly sets `QT_QPA_PLATFORMTHEME=gtk3`
  in `~/.config/uwsm/env.d/90-proarch-qt-font`; no separate Qt font value is
  needed. Log out and back in after deploying the session environment, then
  reopen applications. Applications that explicitly choose their own font
  retain that choice.
- User-owned plugins installed only when missing, with the obsolete `dropspace` activation entry removed.

| Plugin | Source | Default version |
| --- | --- | --- |
| `harryxu.dropspace` | https://github.com/harryxu/omarchy-dropspace | `HEAD` |
| `harryxu.super-switcher` | https://github.com/harryxu/omarchy-super-switcher | `HEAD` |

Super Switcher enables macOS-style application switching with `Super+Tab` and
`Super+Shift+Tab`. The plugin registers these shortcuts at runtime.

`omarchy_overrides.plugins` replaces the complete plugin list; each entry
requires `id` and `repo` (HTTPS). `version` is optional and defaults to `HEAD`
for the initial installation; an explicit branch, tag, or commit can be selected.
An existing `manifest.json` marks the plugin as installed, so later runs skip
Git operations entirely, preserving its installed version and local edits.
Manifest IDs are still validated. Update existing plugins separately; changing
`version` does not update an installed plugin. Optional `settings` are merged
into that plugin's Shell activation entry. Removing an entry disables its
activation without deleting its source directory.

The installed `hyprland.lua` bootstrap is retained and checked for the required
personal imports. The playbook deploys its bindings as
`~/.config/hypr/proarch_bindings.lua` and manages the import at the top of
`~/.config/hypr/bindings.lua`. Add host-specific bindings below that block and
use `o.rebind(...)` to replace a shortcut defined by Omarchy or Proarch.

Configure terminal/monospace fonts through Omarchy and displays
in the host's Hyprland monitor configuration. The playbook leaves existing
terminal/monospace fonts, Shell font settings, monitor configuration, and display
scaling unchanged, including values deployed by earlier versions. It does not
run `omarchy font set`.

Only actual personal overrides are captured. The current menu file is an empty
example. The playbook installs its wallpaper hook alongside the existing
Omarchy/owe hooks. Add maintained menu JSONC files under `files/omarchy/extensions/`.
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

## Independent application themes

The Omarchy profile defaults to `independent_app_themes: true`. It prevents
Omarchy's theme switch from retinting VS Code, browsers and Neovim. Each
application's selected theme and automatic light/dark preference remain under its own control.
Ansible does not edit VS Code settings or browser preferences, and does not
select a theme or light/dark mode for these applications. For Chrome, it backs
up Omarchy's existing `/etc/opt/chrome/policies/managed/color.json` and removes
only `BrowserThemeColor` and `BrowserColorScheme`, retaining unrelated keys.
Backups are stored under `/var/lib/proarch/backups/chrome-theme-policies`,
not in Chrome's policy directories: Chrome loads all regular files there, even
Ansible backup files ending in `~`. Existing `color.json.*~` and
`color.json.proarch-backup-*` backups are moved to that external backup directory.
These mandatory entries otherwise keep Chrome's theme locked even after future
Omarchy retints are blocked. No policy file is created when it is absent.
Restart Chrome or reload its policies at `chrome://policy` after deployment.

```yaml
omarchy_overrides:
  independent_app_themes: true
```

Omarchy 4.5 supplies the VS Code opt-out but no Chromium opt-out. User-owned
guards intercept the browser retint command using a dedicated PATH directory;
login Bash, UWSM, fish, and personal Hyprland autostart load that directory.
The Omarchy theme picker launches login Bash, so it reads the guard immediately
after deployment. Existing terminals need a new shell, and direct session
launches receive the environment after login or the managed Hyprland reload.
The Chromium retint command is shared by Chrome, Chromium, Edge, and Brave,
so the guard skips that shared retint step. Firefox has no dedicated retint step
in this Omarchy version; its guard supports a future matching command.

Neovim's stock Omarchy integration is a `lua/plugins/theme.lua` symlink to
Omarchy's generated `neovim.lua`. The playbook renames only known current and
legacy Omarchy links to a backup with a non-`.lua` suffix, so LazyVim stops
loading them. Broken known links are handled as well. Regular Lua files and
links to personal themes are preserved. No replacement colorscheme is selected;
shared Neovim configuration and personal theme choices remain in control.
The current Omarchy version has no Vim theme-sync step, so Vim configuration is
left untouched. Custom editor code that explicitly imports Omarchy theme state
remains user-controlled and must be disconnected in that custom configuration.

Choose themes and light/dark behavior inside each application. If an application
is configured to follow the system, that application can still react to the OS
color preference. Existing application settings and unrelated browser policies
are retained. Packaged Omarchy files are never patched.

`independent_app_themes: false` stops managing this feature; like other optional
features, it does not remove previously deployed opt-out flags or guards,
or restore a disconnected Neovim theme link.

## Layout and checks

```text
main.yml                 shared tasks, selected desktop, optional features
profiles/                KDE and Omarchy defaults
vars/packages.yml        shared package choices
tasks/configuration.yml  config loading, merging and selection validation
tasks/preflight.yml      user, platform and desktop capability checks
tasks/common/            packages, services, dotconfig and input components
tasks/desktop/           desktop-specific preferences and integrations
tasks/features/          optional integrations
files/omarchy/           maintained personal files
templates/omarchy/       personal autostart and keyboard integration
handlers/                change-triggered session updates
```

Use `--tags common`, `--tags dotconfig`, `--tags desktop`, or `--tags features`
after initial provisioning. Read-only selection and prerequisite checks always
run. All host customization belongs in `config.yml`: select built-in integrations
with `feature_overrides` and add software with `extra_packages` or
`extra_aur_packages`. `tasks/kde.yml` and `tasks/fcitx5.yml` remain
compatibility entry points; configuration is now resolved by `main.yml` first.

With Ansible, Git, Python, the required collections, and Lua's `luac` installed:

```sh
ansible-playbook main.yml --syntax-check -e desktop_profile=kde
ansible-playbook main.yml --syntax-check -e desktop_profile=omarchy
ansible-lint --offline
python3 tests/verify.py
```

The integration checks use disposable local Git repositories and homes under
`/tmp`. They cover required selection, both profiles, override precedence,
invalid settings, actual allowlisted copies and backups, untouched desktop
files and existing Git metadata, second-run idempotence, latest KDE theme
updates without duplicate installation, and Lua parsing.
They do not install packages, start services, or alter live configuration.

Install `ansible-lint` separately to run lint checks. `.ansible-lint.yml` adds
file classifications for the examples. Its project-wide `skip_list` contains
only `latest[git]`, allowing Git tasks to follow upstream without inline
exceptions. Other lint rules remain enabled.
Shared dotconfig and KDE theme Git checkouts synchronize upstream by default.
Omarchy plugins are cloned only when missing and are left untouched afterward.
Explicit version overrides remain supported for their initial installation.
KDE theme repositories synchronize upstream `HEAD` on each run. Graphite and
Tela are installed on first use and reinstalled when their source changes;
AquaMediumIcons runs directly from its updated checkout.
Unchanged sources do not trigger reinstallation, and local Git edits are preserved.
