# Give each configuration file one owner

Shared dotconfig is initialized directly in the target user's `~/.config` so
the deployed files can be managed with Git. The first deployment force-checks
out the configured ref and can replace files at paths tracked by that ref.
Subsequent runs skip existing Git repositories, leaving updates to the user.
This replaces the separate checkout and allowlisted copies.

Desktop profiles apply their personal overrides after dotconfig initialization.
Omarchy owns its packaged defaults and generated theme files. Keep these paths
out of shared dotconfig to avoid collisions during the first checkout.
