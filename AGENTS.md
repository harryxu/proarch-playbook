# Proarch Playbook

An Ansible playbook that configures a fresh Arch Linux system into a programmer-friendly desktop environment.

## What it does

- Installs core CLI tools (fish, neovim, tmux, zellij, lazygit, fzf, bat, eza, ripgrep, etc.)
- Sets up dev runtimes: Go, Node.js, Rust
- Installs desktop apps: Zed, Ghostty, Chrome (AUR), VS Code (AUR)
- Clones dotconfig from `harryxu/dotconfig` into `~/.config`
- Configures Docker (via `geerlingguy.docker` role) and Starship prompt
- Sets fish as the default shell and installs CJK/nerd fonts
- Optionally applies extras via `extras.yml` (not committed)

## Project Structure

```
main.yml              # Main playbook entry point
default.config.yml    # Default variables
requirements.yml      # External Ansible Galaxy roles
extras.yml.example    # Template for personal extras
tasks/
  setup_aur.yml       # Sets up yay and aur_builder user
  fcitx5.yml          # Chinese input method (fcitx5)
  cliphist.yml        # Clipboard history service
  kde.yml             # KDE Plasma desktop configuration
  gnome.yml           # GNOME desktop configuration
  extra_*.yml         # Optional extras (bluetooth, snapper, keybindings)
roles/                # Ansible Galaxy roles (docker, starship, timezone)
files/                # Static config files copied to the target system
inventory/            # Ansible inventory (hosts)
```

## Usage

```shell
# Install Ansible
sudo pacman -S ansible

# Install required roles
ansible-galaxy install -r requirements.yml

# Run the playbook
ansible-playbook main.yml
```

## Notes for AI Agents

- All tasks target Arch Linux; package management uses `pacman` and `yay` (AUR).
- AUR packages are installed as the `aur_builder` user (set up in `tasks/setup_aur.yml`).
- Desktop environment tasks (KDE/GNOME) are in separate task files and not included in `main.yml` by default — include them manually or via `extras.yml`.
- `files/` contains static configs (e.g., SDDM themes) that are copied verbatim.
