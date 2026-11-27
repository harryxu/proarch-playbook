# Give each configuration file one owner

On first deployment the playbook runs the dotconfig installer as the target
user. The installer owns repository setup in `~/.config` and can replace files
at tracked paths during checkout. Using the installer also applies dotconfig's
shared settings and repository hooks. If `~/.config/.git` already exists, the
playbook skips the entire installer, leaving updates to the user.

Desktop profiles apply their personal overrides after dotconfig initialization.
Omarchy owns its packaged defaults and generated theme files. Keep these paths
out of shared dotconfig to avoid collisions during the first checkout.
