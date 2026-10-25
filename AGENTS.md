# Proarch Playbook

An Ansible playbook that configures an existing Arch Linux desktop as a personal
development environment with an explicit KDE or Omarchy desktop profile.

## Structure

- `main.yml` resolves configuration, checks prerequisites, then runs shared,
  selected desktop, and optional feature tasks.
- `default.config.yml` and `profiles/` hold shared and desktop defaults.
  `config.yml.example` documents host customization; `config.yml` is ignored.
- `vars/packages.yml` holds shared package choices.
- `tasks/common/` handles shared system settings, dotconfig, and input components.
- `tasks/desktop/` owns KDE and Omarchy overrides and native session integration.
- `files/omarchy/`, `templates/omarchy/`, and `handlers/` hold personal files,
  host-dependent configuration, and session-aware updates.
- `tasks/features/` selects optional Bluetooth, Snapper, and KDE xremap tasks.
- `test.yml` performs read-only validation; `tests/verify.py` runs isolated checks.

## Working conventions

- Require `desktop_profile: kde` or `omarchy`; validate before system changes.
- Use `target_user` and the resolved `target_home`, keeping connection identity separate.
- Install Arch packages through pacman and AUR packages as `aur_builder`.
- Deploy shared dotconfig through the tracked-file allowlist with backups.
- Keep Omarchy packaged defaults and generated state under Omarchy's ownership.
  Read `docs/adr/0001-configuration-ownership.md` before changing file ownership.
- Default profile selection leaves existing software and unrelated services intact.
- Keep host customization in `config.yml`; expose optional functionality through
  feature switches and package additions documented in `config.yml.example`.

## Validation

Install collections with `ansible-galaxy collection install -r requirements.yml`.
Run syntax checks for both profiles and `python3 tests/verify.py`.
The integration suite operates only in disposable directories under `/tmp`.
A full playbook run changes the host; use `test.yml` for prerequisite checks.

## Agent skills

### Issue tracker

Track issues and specs in GitHub Issues for `harryxu/proarch-playbook`. Before issue operations, read `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. Before assigning triage state, read `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context layout: root `GLOSSARY.md` and `docs/adr/`. Before codebase exploration, read `docs/agents/domain.md`.
