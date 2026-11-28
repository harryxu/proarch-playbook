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
- Bootstrap shared dotconfig directly in `target_home/.config`; skip existing Git repositories.
- Keep Omarchy packaged defaults and generated state under Omarchy's ownership.
  Read `docs/adr/0001-configuration-ownership.md` before changing file ownership.
- Default profile selection leaves existing software and unrelated services intact.
- Keep host customization in `config.yml`; expose optional functionality through
  feature switches and package additions documented in `config.yml.example`.

## Validation

Install collections with `ansible-galaxy collection install -r requirements.yml`.
For Ansible changes, run syntax checks for both profiles. Prefer focused
integration checks with `python3 tests/verify.py GROUP [GROUP ...]` and select
the groups that cover the changed configuration. Use `python3 tests/verify.py --list`
or the [test group guide](readme.md#layout-and-checks) to find them.
Run the full suite with `python3 tests/verify.py` when the change may affect
behavior beyond the selected groups or when the user requests it.
The integration suite operates only in disposable directories under `/tmp`.
A full playbook run changes the host; use `test.yml` for prerequisite checks.

## Project rules

You may write files in the project directory and the system temporary directory (such as `/tmp`) without prior approval. Before creating, modifying, moving, or deleting files elsewhere, tell the user which paths and operations are involved and obtain their explicit approval. This rule also applies to indirect changes through symlinks, scripts, or commands.



## Agent skills

### Omarchy workaround retirement

Read [Omarchy #16241 retirement](docs/agents/omarchy-16241-retirement.md) when
checking whether the floating-window workaround can be removed.

### Issue tracker

Track issues and specs in GitHub Issues for `harryxu/proarch-playbook`. Before issue operations, read `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. Before assigning triage state, read `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context layout: root `GLOSSARY.md` and `docs/adr/`. Before codebase exploration, read `docs/agents/domain.md`.
