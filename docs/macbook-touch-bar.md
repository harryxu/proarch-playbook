# MacBook Pro Touch Bar function keys

Set `hid_appletb_kbd` to `mode=1` to show F1 through F12 by default. With
`fntoggle=Y`, holding Fn switches to brightness, volume, and other media
controls; releasing Fn restores the function keys.

The MacBookPro15,2 running Omarchy uses this driver. The playbook does not
manage this host setting.

## Check the current settings

```sh
modinfo -p hid_appletb_kbd
cat /sys/bus/hid/drivers/hid-appletb-kbd/*/mode
cat /sys/module/hid_appletb_kbd/parameters/fntoggle
```

Mode `1` shows function keys by default. Mode `2` shows media controls by
default. The checked host had `mode=2` and `fntoggle=Y`.

`hid_apple fnmode=2` controls a separate driver. An existing setting can stay
in place; use `hid_appletb_kbd mode=1` for this Touch Bar.

## Try it for the current boot

```sh
echo 1 | sudo tee /sys/bus/hid/drivers/hid-appletb-kbd/*/mode
```

The change takes effect immediately and lasts until reboot. Replace `1` with
`2` to restore media controls immediately.

The writable `mode` attribute belongs to the HID device. The module parameter
at `/sys/module/hid_appletb_kbd/parameters/mode` is read-only.

## Keep the setting after reboot

Create or edit `/etc/modprobe.d/touchbar.conf` and add:

```text
options hid_appletb_kbd mode=1
```

On this mkinitcpio-based setup, rebuild the initramfs, then reboot:

```sh
sudo mkinitcpio -P
```

After reboot, check the device's `mode` again and test the Touch Bar with and
without Fn. The mode should be `1`.

To restore media controls as the default, change the configuration to
`mode=2`, rebuild the initramfs, and reboot. Use the temporary command with
`2` if the current session should change as well.

The mode values, writable device attribute, and Fn behavior are defined in
the [Linux Touch Bar keyboard driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-appletb-kbd.c).
