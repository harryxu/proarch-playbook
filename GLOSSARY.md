# Proarch Playbook

Personal Arch Linux environments share development tools while retaining the
desktop behavior appropriate to each machine.

## Language

**Desktop profile**:
A selected set of desktop-specific preferences and integrations, currently KDE
or Omarchy. A profile describes the environment to configure, rather than a
request to uninstall another desktop.
_Avoid_: desktop migration, detected desktop

**Shared configuration**:
Personal development tools, applications, and preferences intended to remain
consistent across desktop profiles.
_Avoid_: desktop defaults

**Host customization**:
A machine's explicit differences from shared configuration and its desktop
profile, such as display scaling or enabled optional features.
_Avoid_: desktop profile
