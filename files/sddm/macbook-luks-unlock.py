#!/usr/bin/env python3
"""Recognize the passphrase-only mkinitcpio boot used by Omarchy on Intel Macs."""
from pathlib import Path
import re
import subprocess


def read_efi(name):
    path = Path(f'/sys/firmware/efi/efivars/{name}-4a67b082-0a4c-41cf-b6c7-440b29bb8c4f')
    return path.read_bytes()[4:].decode('utf-16-le').rstrip('\0')


def output(*argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.DEVNULL)


def uses_luks_passphrase():
    dmi = Path('/sys/class/dmi/id')
    if not (dmi / 'sys_vendor').read_text().strip().startswith('Apple'):
        return False
    if not (dmi / 'product_name').read_text().startswith('MacBook'):
        return False

    args = Path('/proc/cmdline').read_text().split()
    if any(arg.startswith(('cryptkey=', 'initrd=')) for arg in args):
        return False
    crypt_devices = [arg.removeprefix('cryptdevice=') for arg in args if arg.startswith('cryptdevice=')]
    if len(crypt_devices) != 1:
        return False
    _, mapping, *_ = crypt_devices[0].split(':')
    if not mapping:
        return False

    # Require the boot-time LUKS mapping to be the mounted root, not a data disk.
    root = output('findmnt', '--noheadings', '--nofsroot', '--output', 'SOURCE', '--mountpoint', '/').strip()
    if root != f'/dev/mapper/{mapping}':
        return False
    if not any(
        name.read_text().strip() == mapping and name.with_name('uuid').read_text().startswith('CRYPT-LUKS')
        for name in Path('/sys/class/block').glob('dm-*/dm/name')
    ):
        return False

    # The encrypt hook also tries an implicit keyfile. Check the booted UKI's
    # initramfs before assuming the absence of cryptkey= means a password prompt.
    partuuid = read_efi('StubDevicePartUUID').lower()
    image = '/' + read_efi('StubImageIdentifier').replace('\\', '/').lstrip('/')
    if not re.fullmatch(r'/EFI/Linux/[\w.-]+\.efi', image):
        return False

    for mount in ('/boot', '/efi', '/boot/efi'):
        if not Path(mount).is_mount():
            continue
        partition = output('findmnt', '--noheadings', '--output', 'PARTUUID', '--mountpoint', mount).strip().lower()
        if partition and partition == partuuid:
            members = {
                line.removeprefix('./')
                for line in output('lsinitcpio', '--list', '--nocolor', mount + image).splitlines()
            }
            # Omarchy can pass both styles of LUKS arguments. The mkinitcpio
            # encrypt hook ignores rd.luks.*; only the systemd generator uses them.
            return 'hooks/encrypt' in members and not members & {
                'crypto_keyfile.bin',
                'etc/crypttab',
                'usr/lib/systemd/system-generators/systemd-cryptsetup-generator',
            }
    return False


if __name__ == '__main__':
    try:
        print('passphrase' if uses_luks_passphrase() else 'unknown')
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('unknown')
