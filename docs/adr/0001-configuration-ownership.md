# Give each configuration file one owner

Shared dotconfig is deployed from an explicit allowlist, with backups before
replacing existing files. Desktop profiles own their personal overrides, while
Omarchy owns its packaged defaults and generated theme files. This replaces
checking out a repository forcibly over the whole configuration directory:
whole-directory deployment is simpler, but can overwrite desktop integration
and unrelated personal changes. Existing dotconfig repositories remain in place;
profile selection configures the chosen environment without removing another.
