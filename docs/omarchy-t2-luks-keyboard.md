# T2 MacBook keyboard at LUKS unlock

An affected Omarchy installation accepts input from an external USB keyboard
at the first disk-unlock prompt and recognizes the built-in keyboard after
boot. The installer-generated `zz-omarchy-kernel-modules.conf` filters
`t2bce_vhci` out of both kernels' initramfs when one installed kernel lacks it.
That leaves the driver out of the `linux-t2` unified kernel image (UKI) even
though the T2 kernel provides it. [Omarchy #17755](https://github.com/omacom/omarchy/issues/17755)

The workaround uses mkinitcpio's optional-module suffix. The playbook adds
`t2bce_vhci?` in `/etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf`,
after the installer filter. mkinitcpio includes the module and its
dependencies for `linux-t2` and skips it on kernels that lack it. This keeps
`apple-t2.conf` and the installer filter intact, including its treatment of
other modules. Two reporters confirmed built-in keyboard input at LUKS
unlock using the optional suffix. Another confirmed the per-kernel filter
approach, which is also proposed for the installer.
[Optional suffix and cold boot](https://github.com/omacom/omarchy/issues/17755#issuecomment-6720671830),
[optional suffix with the installer filter intact](https://github.com/omacom/omarchy/issues/17755#issuecomment-6841564019),
[per-kernel filter](https://github.com/omacom/omarchy/issues/17755#issuecomment-6692487413)

## Enable and verify

On an affected host with `desktop_profile: omarchy`, add this key to the
existing `feature_overrides` mapping in `config.yml`.

```yaml
feature_overrides:
  t2_luks_keyboard_workaround: true
```

The task checks for Apple T2 hardware, an installed `linux-t2` with the driver,
and its existing Limine UKI under `/boot/EFI/Linux/`. Preview and apply just this
workaround with the dedicated tag.

```sh
ansible-playbook main.yml --tags t2_luks_keyboard --check --diff
ansible-playbook main.yml --tags t2_luks_keyboard
```

If the current UKI lacks the driver or its dependencies for the installed
kernel, the task runs `limine-mkinitcpio linux-t2`. It checks the image again
because Limine's wrapper can succeed after skipping a failed build. If
verification fails, fix the reported build problem and rerun the task before
rebooting. On the next cold boot, select `linux-t2` and unlock the disk with
the built-in keyboard. Keep the external USB keyboard available for that test.

## Remove after the official fix

1. Upgrade to an Omarchy release with a repair for **existing installations**.
   Check that the fix reached this host. An ISO-only fix applies to new
   installations. As of 2026-11-14, both existing-install repair proposals
   and the installer proposal are open.
   [Omarchy #17164](https://github.com/omacom/omarchy/pull/17164),
   [Omarchy #18035](https://github.com/omacom/omarchy/pull/18035),
   [omarchy-iso #408](https://github.com/omacom/omarchy-iso/pull/408)
2. Set `feature_overrides.t2_luks_keyboard_workaround` to `false` or remove
   the key from `config.yml`. This stops Ansible from redeploying the drop-in.
   Move the drop-in out of mkinitcpio's `*.conf` load set and rebuild the T2 UKI.

   ```sh
   sudo mv /etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf \
     /etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf.disabled
   sudo limine-mkinitcpio linux-t2
   ```

3. Verify the rebuilt image before rebooting. Use the `linux-t2` UKI path from
   `/boot/limine.conf` if the name differs from the Omarchy default. All three
   modules should appear. The build configuration should have no Proarch
   workaround header, and `lsinitcpio -a` should mark `t2bce_vhci` as
   `[explicit]`.

   ```sh
   uki=/boot/EFI/Linux/omarchy_linux-t2.efi
   sudo lsinitcpio -l "$uki" | grep -E '/t2bce_(core|dma|vhci)\.ko(\.[^[:space:]]+)?$'
   sudo lsinitcpio -a "$uki" | grep -E 't2bce[-_]vhci \[explicit\]'
   sudo lsinitcpio -c "$uki"
   ```

   If the rebuild fails, a check fails, or the old workaround still appears
   in the embedded build configuration, restore the drop-in and rebuild
   before rebooting.

   ```sh
   sudo mv /etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf.disabled \
     /etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf
   sudo limine-mkinitcpio linux-t2
   sudo lsinitcpio -l "$uki" | grep -E '/t2bce_(core|dma|vhci)\.ko(\.[^[:space:]]+)?$'
   ```

4. After a cold boot using the built-in keyboard, delete
   `/etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf.disabled` and any
   Ansible backups of that file's original `.conf` path that you no longer need.
   Leave the Omarchy-owned `apple-t2.conf`, installer filter, and any
   upstream migration files under Omarchy's management.

   ```sh
   sudo rm /etc/mkinitcpio.conf.d/zz-proarch-t2-luks-keyboard.conf.disabled
   find /etc/mkinitcpio.conf.d -maxdepth 1 -name 'zz-proarch-t2-luks-keyboard.conf.*~' -print
   ```

Once all affected hosts have retired the workaround, remove the task import
from `tasks/features/main.yml`, its implementation and drop-in under
`tasks/desktop/omarchy/` and `files/omarchy/`, and the feature key, validation,
test cases, and documentation references from the playbook.
