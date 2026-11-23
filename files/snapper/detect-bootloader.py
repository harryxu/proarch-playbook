#!/usr/bin/env python3
"""Identify the current bootloader from UEFI runtime information."""
import os
from pathlib import Path
import re
import subprocess


LOADER_INFO = Path('/sys/firmware/efi/efivars/LoaderInfo-4a67b082-0a4c-41cf-b6c7-440b29bb8c4f')


def bootloader_from_efi_entries(entries):
    current = re.search(r'^BootCurrent:[ \t]*([0-9a-f]{4})$', entries, re.I | re.M)
    if not current:
        return 'unknown'

    entry = re.search(rf'^Boot{current[1]}\*?[ \t]+(.*)$', entries, re.I | re.M)
    if not entry:
        return 'unknown'

    path = re.search(r'\bFile\(([^)]+)\)', entry[1], re.I)
    if not path:
        return 'unknown'

    parts = path[1].lower().replace('\\', '/').split('/')
    filename = parts[-1]
    if re.fullmatch(r'grub[\w-]*\.efi', filename):
        return 'grub'
    if re.fullmatch(r'limine[\w-]*\.efi', filename):
        return 'limine'
    if 'limine' in parts[:-1] and re.fullmatch(r'boot[\w-]+\.efi', filename):
        return 'limine'
    return 'unknown'


def detect_bootloader(loader_info):
    try:
        # efivarfs prefixes the UTF-16LE value with four attribute bytes.
        product = loader_info.read_bytes()[4:].decode('utf-16-le').strip('\0').strip()
    except (OSError, UnicodeError):
        product = ''

    if product:
        # The running loader's report takes precedence if firmware chainloaded it.
        name = product.split()[0].lower()
        return name if name in ('grub', 'limine') else 'unknown'

    try:
        result = subprocess.run(
            ['efibootmgr', '--verbose'], capture_output=True, text=True,
            encoding='utf-8', errors='replace', env={**os.environ, 'LC_ALL': 'C'},
        )
    except OSError:
        return 'unknown'

    return bootloader_from_efi_entries(result.stdout) if result.returncode == 0 else 'unknown'


if __name__ == '__main__':
    print(detect_bootloader(LOADER_INFO))
