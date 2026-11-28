#!/usr/bin/env python3
"""Run selected playbook integration checks in temporary homes."""
import argparse
import configparser
import json
import os
from pathlib import Path
import pwd
import re
import runpy
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV.update(ANSIBLE_HOME='/tmp/proarch-ansible-home',
           ANSIBLE_LOCAL_TEMP='/tmp/proarch-ansible-local',
           ANSIBLE_REMOTE_TEMP='/tmp/proarch-ansible-remote',
           ANSIBLE_NOCOLOR='1', ANSIBLE_BECOME_ASK_PASS='false')
USER = pwd.getpwuid(os.geteuid()).pw_name
HYPRLAND_DEFAULTS = b'require("default.hypr.toggles")\n-- Keep this personal configuration.\n'


def command(args, **kwargs):
    result = subprocess.run(args, cwd=ROOT, env=ENV, text=True,
                            capture_output=True, **kwargs)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


def verify_hyprland_reload(work):
    """Hyprland reload handler and session context after Snapper preflight."""
    hyprland_fixture = work / 'hyprland'
    hyprland_fixture.mkdir()
    hyprctl = hyprland_fixture / 'hyprctl'
    hyprctl.write_text('''#!/bin/sh
[ "$HYPRLAND_INSTANCE_SIGNATURE" = fixture-instance ] || exit 1
printf '%s\\n' "$1" >> "$HYPRLAND_TEST_LOG"
''')
    hyprctl.chmod(0o755)
    hyprland_log = hyprland_fixture / 'commands'
    hyprland_play = hyprland_fixture / 'reload.yml'
    hyprland_play.write_text(f"""---
- hosts: all
  gather_facts: false
  vars:
    has_hyprland_session: true
    target_user: {os.getuid()}
    target_uid: {os.getuid()}
    snapper_bootloader: fixture-stop
  environment:
    PATH: "{hyprland_fixture}:{{{{ lookup('env', 'PATH') }}}}"
    HYPRLAND_TEST_LOG: "{hyprland_log}"
  tasks:
    - name: Gather facts with a Hyprland session
      ansible.builtin.setup:
        gather_subset: [min]
      environment:
        HYPRLAND_INSTANCE_SIGNATURE: fixture-instance
    # Stop after the real mount probe without requiring a particular root filesystem.
    - block:
        - ansible.builtin.import_tasks: "{ROOT / 'tasks/features/snapper_preflight.yml'}"
      rescue:
        - ansible.builtin.assert:
            that: ansible_failed_task.name in ['Require a Btrfs root filesystem for Snapper',
                                               'Validate the Snapper bootloader setting']
    - name: Notify the reload handler
      ansible.builtin.debug:
        msg: Simulate a personal configuration change
      changed_when: true
      notify: Reload Hyprland
  handlers:
    - ansible.builtin.import_tasks: "{ROOT / 'handlers/main.yml'}"
""")
    command(['env', '-u', 'HYPRLAND_INSTANCE_SIGNATURE', 'ansible-playbook',
             str(hyprland_play), '-i', 'localhost,', '-c', 'local', '-e', 'ansible_become=false'])
    assert hyprland_log.read_text().splitlines() == ['reload', 'configerrors']


def verify_snapper(work):
    """Snapper bootloader detection from EFI entries and loader metadata."""
    bootloader_probe = runpy.run_path(str(ROOT / 'files/snapper/detect-bootloader.py'))
    efi_entries = r"""
BootOrder: 0001,0002,0003
Boot0001* GRUB HD(1,GPT,...)/File(\EFI\GRUB\grubx64.efi)
Boot0002* Limine HD(1,GPT,...)/File(\EFI\limine\BOOTX64.EFI)
Boot0003* Linux HD(1,GPT,...)/File(\EFI\BOOT\BOOTX64.EFI)
"""
    for entry, expected in [('0001', 'grub'), ('0002', 'limine'), ('0003', 'unknown'),
                            ('0004', 'unknown')]:
        assert bootloader_probe['bootloader_from_efi_entries'](
            f'BootCurrent: {entry}\n' + efi_entries) == expected
    assert bootloader_probe['bootloader_from_efi_entries'](efi_entries) == 'unknown'
    loader_info = work / 'LoaderInfo'
    for product, expected in [('Limine 12.0', 'limine'), ('GRUB 2.14', 'grub'),
                              ('systemd-boot 259', 'unknown')]:
        loader_info.write_bytes(b'\x06\0\0\0' + (product + '\0').encode('utf-16-le'))
        assert bootloader_probe['detect_bootloader'](loader_info) == expected


def link_playbook_files(work):
    (work / 'profiles').symlink_to(ROOT / 'profiles', target_is_directory=True)
    (work / 'files').symlink_to(ROOT / 'files', target_is_directory=True)
    (work / 'templates').symlink_to(ROOT / 'templates', target_is_directory=True)
    (work / 'filter_plugins').symlink_to(ROOT / 'filter_plugins', target_is_directory=True)


def make_harness(work, **defaults):
    link_playbook_files(work)
    harness = work / 'verify.yml'
    harness.write_text("""---
- hosts: all
  gather_facts: false
  become: false
  vars_files:
    - """ + str(ROOT / 'default.config.yml') + """
  tasks:
    - ansible.builtin.import_tasks: """ + str(ROOT / 'tasks/configuration.yml') + """
    - ansible.builtin.set_fact:
        target_home: "{{ fixture_target_home }}"
    - ansible.builtin.copy:
        dest: "{{ result_file }}"
        content: "{{ {'profile': desktop_profile, 'features': features, 'omarchy': omarchy_settings, 'extra_packages': extra_packages, 'extra_aur_packages': extra_aur_packages} | to_json }}"
      when: verify_config | default(false)
    - ansible.builtin.include_tasks:
        file: """ + str(ROOT / 'tasks/common/dotconfig.yml') + """
        apply:
          environment:
            PATH: "{{ playbook_dir }}/dotconfig-bin:{{ lookup('env', 'PATH') }}"
      when: verify_dotconfig | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/common/user_service.yml') + """
      when: verify_user_service | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/common/sddm_autologin.yml') + """
      when: verify_sddm_login | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/extra_keybindings.yml') + """
      when: verify_xremap_entry | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/desktop/omarchy/keyboard.yml') + """
      when: verify_keyboard | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/desktop/omarchy/hyprland.yml') + """
      when: verify_hyprland | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/desktop/omarchy/wallpapers.yml') + """
      when: verify_wallpapers | default(false)
    - ansible.builtin.template:
        src: """ + str(ROOT / 'templates/omarchy/autostart.lua.j2') + """
        dest: "{{ autostart_file }}"
      when: verify_autostart | default(false)
  handlers:
    - name: Reload Hyprland
      ansible.builtin.debug:
        msg: Fixture only; never reload the live desktop.
""")
    base = dict(ansible_become=False, playbook_config_file=str(work / 'absent.yml'),
                target_user=USER, target_home=str(work / 'home'),
                result_file=str(work / 'result.json'),
                autostart_file=str(work / 'autostart.lua')) | defaults

    def run(overrides, success=True, check=False):
        variables = work / 'vars.json'
        values = base | overrides
        values['fixture_target_home'] = values.pop('target_home')
        variables.write_text(json.dumps(values))
        result = subprocess.run(['ansible-playbook', str(harness), '-i', 'localhost,',
                                 '-c', 'local', '-e', '@' + str(variables)]
                                + (['--check'] if check else []),
                                cwd=ROOT, env=ENV, text=True, capture_output=True)
        if (result.returncode == 0) != success:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout + result.stderr

    return run


def verify_config(work):
    """Profile selection, host config, override precedence and feature switches."""
    run = make_harness(work, verify_config=True)

    for profile in ['', 'gnome', '../../kde']:
        (work / 'result.json').unlink(missing_ok=True)
        output = run(dict(desktop_profile=profile), success=False)
        assert 'Set desktop_profile' in output, output
        assert not (work / 'result.json').exists(), 'Invalid selection reached a write task'

    for profile in ['kde', 'omarchy']:
        run(dict(desktop_profile=profile))
        data = json.loads((work / 'result.json').read_text())
        assert data['profile'] == profile
        assert data['features']['rime_ice'] is True
        assert 'cliphist' not in data['features']
        assert data['features']['vicinae'] is True
        assert data['features']['apfs_automount'] is False
        assert data['features']['t2_luks_keyboard_workaround'] is False
        assert 't2_usb_hotplug' not in data['features']

    # A copied example is the only host configuration needed for either profile.
    example_host = work / 'example-config.yml'
    example = (ROOT / 'config.yml.example').read_text()
    for profile in ['kde', 'omarchy']:
        example_host.write_text(example.replace('desktop_profile: omarchy', 'desktop_profile: ' + profile)
                               .replace('extra_packages: []', 'extra_packages: [jq]')
                               .replace('extra_aur_packages: []', 'extra_aur_packages: [fixture-aur]'))
        run(dict(playbook_config_file=str(example_host)))
        data = json.loads((work / 'result.json').read_text())
        assert data['profile'] == profile
        assert data['extra_packages'] == ['jq'] and data['extra_aur_packages'] == ['fixture-aur']
        assert data['features']['rime_ice'] is True
        assert data['features']['snapper'] is True
        assert data['features']['vicinae'] is True

    # Exercise the optional YAML config loader, then CLI precedence and nested merging.
    host = work / 'config.yml'
    host.write_text('desktop_profile: kde\nfeature_overrides:\n  docker: false\n')
    run(dict(playbook_config_file=str(host)))
    assert json.loads((work / 'result.json').read_text())['profile'] == 'kde'
    run(dict(playbook_config_file=str(host), desktop_profile='omarchy',
             omarchy_overrides={'shell': {'idle': {'lock': 42}, 'bar': {'layout': {'right': []}}}}))
    data = json.loads((work / 'result.json').read_text())
    assert data['profile'] == 'omarchy' and data['features']['docker'] is False
    assert data['omarchy']['shell']['idle']['lock'] == 42
    assert data['omarchy']['shell']['bar']['layout']['right'] == []
    assert data['omarchy']['shell']['bar']['background'] == 'glassy', 'Nested defaults were lost'
    assert set(data['omarchy']['shell']['bar']) == {'background', 'layout'}
    assert data['omarchy']['shell']['dock'] == {'autohide': True}
    for overrides in [{'docker': 'false'}, {'unknown_feature': True}, {'keybindings': True}]:
        run(dict(desktop_profile='omarchy', feature_overrides=overrides), success=False)
    run(dict(desktop_profile='kde', feature_overrides={'keybindings': True}))
    assert json.loads((work / 'result.json').read_text())['features']['keybindings'] is True
    run(dict(desktop_profile='omarchy',
             feature_overrides={'apfs_automount': True, 't2_usb_hotplug': False, 'cliphist': True}))
    storage_features = json.loads((work / 'result.json').read_text())['features']
    assert storage_features['apfs_automount'] and 't2_usb_hotplug' not in storage_features
    assert 'cliphist' not in storage_features
    output = run(dict(desktop_profile='kde', feature_overrides={'apfs_automount': True}),
                 success=False)
    assert 'APFS automount uses the Omarchy desktop session' in output
    run(dict(desktop_profile='omarchy', feature_overrides={'t2_luks_keyboard_workaround': True}))
    assert json.loads((work / 'result.json').read_text())['features']['t2_luks_keyboard_workaround']
    output = run(dict(desktop_profile='kde',
                      feature_overrides={'t2_luks_keyboard_workaround': True}), success=False)
    assert 'T2 LUKS keyboard workaround supports Omarchy only' in output


def verify_sddm(work):
    """SDDM autologin across desktop profiles and native drop-ins."""
    run = make_harness(work)

    sddm_config = work / 'sddm.conf'
    sddm_drop_in = work / 'sddm.conf.d/autologin.conf'
    sddm_drop_in.parent.mkdir()
    native_login = '[Autologin]\nUser=omarchy-owner\nSession=omarchy.desktop\n'
    old_config = ('[Theme]\nCurrent=silent\n[Autologin]\nUser={user}\n'
                  'Session=plasma.desktop\nRelogin=false\n')
    login_fixture = dict(verify_sddm_login=True, sddm_config_file=str(sddm_config),
                         sddm_root_unlock={'stdout': 'unknown'})
    for profile, has_drop_in, expected_session in [
        ('omarchy', True, 'omarchy.desktop'),
        ('omarchy', False, None),
        ('kde', True, None),
    ]:
        sddm_config.write_text(old_config.format(user='' if expected_session else 'stale-user'))
        if has_drop_in:
            sddm_drop_in.write_text(native_login)
        else:
            sddm_drop_in.unlink()
        run(login_fixture | dict(desktop_profile=profile))
        # SDDM reads /etc/sddm.conf after its drop-ins.
        effective_login = configparser.ConfigParser()
        effective_login.read([sddm_drop_in, sddm_config])
        assert effective_login['Theme']['Current'] == 'silent'
        assert effective_login['Autologin']['User'] == ('omarchy-owner' if expected_session else '')
        if expected_session:
            assert effective_login['Autologin']['Session'] == expected_session
        if has_drop_in:
            assert sddm_drop_in.read_text() == native_login


def verify_t2_keyboard(work):
    """T2 LUKS keyboard module filter and late drop-in."""
    # The legacy installer filter drops every listed module for every kernel.
    # The late drop-in must restore just the optional T2 driver.
    t2_filter = work / 'zz-omarchy-kernel-modules.conf'
    t2_filter.write_text("""_omarchy_absent=(t2bce_vhci thunderbolt)
_omarchy_kept=()
for _omarchy_module in "${MODULES[@]}"; do
  [[ " ${_omarchy_absent[*]} " == *" $_omarchy_module "* ]] || _omarchy_kept+=("$_omarchy_module")
done
MODULES=("${_omarchy_kept[@]}")
unset _omarchy_absent _omarchy_kept _omarchy_module
""")
    t2_workaround = ROOT / 'files/omarchy/zz-proarch-t2-luks-keyboard.conf'
    assert command(['env', 'LC_ALL=C.UTF-8', 'sort', '-Vu'],
                   input=f'{t2_workaround.name}\n{t2_filter.name}\n').splitlines() == [
                       t2_filter.name, t2_workaround.name]
    source_t2_configs = """MODULES=("$3" usbhid thunderbolt)
source "$1"
if [[ -n $2 ]]; then
  source "$2"
  source "$2"
fi
printf '%s\n' "${MODULES[@]}"
"""
    for module, drop_in, expected_modules in [
        ('t2bce_vhci', '', ['usbhid']),
        ('t2bce_vhci', str(t2_workaround), ['usbhid', 't2bce_vhci?']),
        ('t2bce_vhci?', str(t2_workaround), ['t2bce_vhci?', 'usbhid']),
    ]:
        assert command(['bash', '-ec', source_t2_configs, 'fixture', str(t2_filter),
                        drop_in, module]).splitlines() == expected_modules


def verify_bindings(work):
    """Omarchy keybindings, floating-window overrides and managed Lua deployment."""
    run = make_harness(work)

    # Deploy the module and load it before user bindings, without overwriting them.
    bindings_loader = (b'-- BEGIN PROARCH BINDINGS\nrequire("hypr.proarch_bindings")\n'
                       b'-- END PROARCH BINDINGS\n')
    personal_bindings = b'-- Keep this local shortcut.\no.rebind("SUPER + F", "Local find", "local-find")\n'
    workaround_source = (ROOT / 'files/omarchy/hypr/floating_fullscreen_workaround.lua').read_bytes()
    workaround_loader = (b'require("hypr.floating_fullscreen_workaround")'
                         b' -- Temporary fix for Omarchy #16241.\n')
    zoom_source = (ROOT / 'files/omarchy/hypr/floating_titlebar_zoom.lua').read_bytes()
    zoom_loader = b'require("hypr.floating_titlebar_zoom")\n'
    for name, initial, expected in [
        ('missing', None, bindings_loader),
        ('personal', personal_bindings, bindings_loader + personal_bindings),
    ]:
        bindings_home = work / f'bindings-{name}'
        bindings_dir = bindings_home / '.config/hypr'
        bindings_dir.mkdir(parents=True)
        local_bindings = bindings_dir / 'bindings.lua'
        managed_bindings = bindings_dir / 'proarch_bindings.lua'
        hyprland_entry = bindings_dir / 'hyprland.lua'
        workaround = bindings_dir / 'floating_fullscreen_workaround.lua'
        # Cover a fresh host and adoption of the previously installed manual loader.
        hyprland_entry.write_bytes(HYPRLAND_DEFAULTS + (workaround_loader if name == 'personal' else b''))
        if initial is not None:
            local_bindings.write_bytes(initial)
            local_bindings.chmod(0o600)
        bindings_config = dict(desktop_profile='omarchy', verify_hyprland=True,
                               target_home=str(bindings_home))
        run(bindings_config)
        assert local_bindings.read_bytes() == expected
        deployed_bindings = managed_bindings.read_bytes()
        command(['luac', '-p', str(managed_bindings)])
        assert hyprland_entry.read_bytes() == HYPRLAND_DEFAULTS + workaround_loader + zoom_loader
        assert workaround.read_bytes() == workaround_source
        zoom = bindings_dir / 'floating_titlebar_zoom.lua'
        assert zoom.read_bytes() == zoom_source
        command(['luac', '-p', str(workaround)])
        command(['luac', '-p', str(zoom)])
        entry_backups = list(bindings_dir.glob('hyprland.lua.*~'))
        expected_backups = {HYPRLAND_DEFAULTS + workaround_loader}
        if name == 'missing':
            expected_backups.add(HYPRLAND_DEFAULTS)
        assert {backup.read_bytes() for backup in entry_backups} == expected_backups
        if initial is not None:
            assert local_bindings.stat().st_mode & 0o777 == 0o600
            backups = list(bindings_dir.glob('bindings.lua.*~'))
            assert len(backups) == 1 and backups[0].read_bytes() == initial
        assert re.search(r'changed=0\b', run(bindings_config)), 'Bindings deployment is not idempotent'

        if name == 'personal':
            # Refreshing the managed file must preserve subsequent edits, including load order.
            expected += b'-- Edit after deployment.\n'
            local_bindings.write_bytes(expected)
            managed_bindings.write_text('-- Old managed contents.\n')
            run(bindings_config)
            assert local_bindings.read_bytes() == expected
            assert managed_bindings.read_bytes() == deployed_bindings
            bindings_runner = work / 'bindings-runner.lua'
            bindings_runner.write_text('''
local bindings = {}
local function bind(key, description, action)
  bindings[key] = { description = description, action = action }
end
o = { bind = bind, rebind = bind }
hl = { unbind = function() end, dsp = { window = { float = function() end } } }
package.path = arg[1] .. '/.config/?.lua;' .. package.path
dofile(arg[1] .. '/.config/hypr/bindings.lua')
assert(bindings['SUPER + R'].description == 'Reload browser tab')
assert(bindings['SUPER + F'].description == 'Local find')
assert(bindings['SUPER + e'].action == arg[2])
local clipboard = bindings['SUPER + SHIFT + V'].action
assert((type(clipboard) == 'table' and clipboard.panel or clipboard) == arg[3])
''')
            command(['lua', str(bindings_runner), str(bindings_home), 'vicinae toggle',
                     'vicinae vicinae://launch/clipboard/history'])
            run(bindings_config | {'feature_overrides': {'vicinae': False}})
            assert local_bindings.read_bytes() == expected
            command(['lua', str(bindings_runner), str(bindings_home), 'omarchy-menu toggle root',
                     'omarchy.clipboard'])


def verify_wallpapers(work):
    """Omarchy wallpaper links, theme-change hook and stable reruns."""
    run = make_harness(work)

    # Personal wallpapers must appear in the native per-theme selector, including
    # after a theme change, without changing Omarchy's generated backgrounds.
    wallpaper_home = work / 'wallpaper-home'
    wallpaper_collection = wallpaper_home / 'Pictures' / 'My "wallpapers"'
    wallpaper_source = work / "source's launch.webp"
    wallpaper_source.write_bytes(b'wallpaper fixture')
    wallpaper_name = 'launch image.webp'
    theme_state = wallpaper_home / '.local/state/omarchy/current/theme.name'
    theme_state.parent.mkdir(parents=True)
    theme_state.write_text('fixture-one\n')
    generated_background = theme_state.parent / 'theme/backgrounds/stock.webp'
    generated_background.parent.mkdir(parents=True)
    generated_background.write_bytes(b'Omarchy-owned image')
    theme_backgrounds = wallpaper_home / '.config/omarchy/backgrounds'
    first_backgrounds = theme_backgrounds / 'fixture-one'
    first_backgrounds.mkdir(parents=True)
    (first_backgrounds / wallpaper_name).write_bytes(b'previous personal image')
    personal_wallpaper = first_backgrounds / 'personal.webp'
    personal_wallpaper.write_bytes(b'keep this image')
    wallpaper_config = dict(
        desktop_profile='omarchy', verify_wallpapers=True,
        target_home=str(wallpaper_home), omarchy_overrides={
            'wallpaper_dir': str(wallpaper_collection),
            'wallpapers': [{'src': str(wallpaper_source), 'name': wallpaper_name}]})
    run(wallpaper_config)
    collection_image = wallpaper_collection / wallpaper_name
    first_image = first_backgrounds / wallpaper_name
    assert collection_image.read_bytes() == wallpaper_source.read_bytes()
    assert first_image.is_symlink() and first_image.resolve() == collection_image
    backups = list(first_backgrounds.glob(wallpaper_name + '.proarch-backup-*'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'previous personal image'
    assert personal_wallpaper.read_bytes() == b'keep this image'
    assert generated_background.read_bytes() == b'Omarchy-owned image'
    assert re.search(r'changed=0\b', run(wallpaper_config)), 'Wallpaper setup is not idempotent'
    wallpaper_hook = wallpaper_home / '.config/omarchy/hooks/theme-set.d/90-proarch-wallpapers'
    command(['bash', '-n', str(wallpaper_hook)])
    command(['bash', str(wallpaper_hook), 'fixture-two'])
    second_image = theme_backgrounds / 'fixture-two' / wallpaper_name
    assert second_image.is_symlink() and second_image.resolve() == collection_image
    # Omarchy's selector follows links and only scans files directly in this directory.
    visible = command(['find', '-L', str(second_image.parent), '-maxdepth', '1', '-type', 'f'])
    assert str(second_image) in visible.splitlines()
    assert command(['bash', str(wallpaper_hook), 'fixture-two']) == ''
    theme_state.write_text('fixture-two\n')
    assert re.search(r'changed=0\b', run(wallpaper_config))


def verify_keyboard(work):
    """Omarchy keyboard swaps, device overrides and input validation."""
    run = make_harness(work)

    # Exercise real keyboard deployment and execute its Lua against a fake API.
    keyboard_home = work / 'keyboard-home'
    keyboard_input = keyboard_home / '.config/hypr/input.lua'
    keyboard_input.parent.mkdir(parents=True)
    personal_input = '-- Personal input settings must survive.\n'
    keyboard_input.write_text(personal_input)
    keyboard_runner = work / 'keyboard-runner.lua'
    keyboard_runner.write_text('''
local options = "omarchy:shift_caps_compose,compose:ralt"
local devices = {}
hl = {
  get_config = function(key) assert(key == "input.kb_options"); return options end,
  config = function(config) options = config.input.kb_options end,
  device = function(config) devices[config.name] = config.kb_options end,
}
dofile(arg[1])
print(options)
for _, name in ipairs({"external-pc", 'apple-"keyboard"'}) do
  print(devices[name] or "inherited")
end
''')
    original_options = 'omarchy:shift_caps_compose,compose:ralt'
    swapped_options = original_options + ',altwin:swap_alt_win'
    keyboard_base = dict(desktop_profile='omarchy', verify_keyboard=True,
                         target_home=str(keyboard_home))
    for keyboard_type, overrides, expected in [
        ('mac', [], [original_options, 'inherited', 'inherited']),
        ('pc', [], [swapped_options, 'inherited', 'inherited']),
        ('mac', [{'name': 'external-pc', 'type': 'pc'}],
         [original_options, swapped_options, 'inherited']),
        ('pc', [{'name': 'apple-"keyboard"', 'type': 'mac'}],
         [swapped_options, 'inherited', original_options]),
    ]:
        selection = keyboard_base | dict(keyboard_type=keyboard_type,
                                        omarchy_keyboard_overrides=overrides)
        run(selection)
        assert keyboard_input.read_text().startswith(personal_input)
        command(['luac', '-p', str(keyboard_input)])
        assert command(['lua', str(keyboard_runner), str(keyboard_input)]).splitlines() == expected
    assert re.search(r'changed=0\b', run(selection)), 'Keyboard deployment is not idempotent'
    # Switch back to mac and remove the device exception; no stale swaps remain.
    run(keyboard_base)
    assert command(['lua', str(keyboard_runner), str(keyboard_input)]).splitlines() == [
        original_options, 'inherited', 'inherited']
    assert list(keyboard_input.parent.glob('input.lua.*~')), 'Input changes were not backed up'
    for invalid in [
        {'keyboard_type': 'windows'},
        {'omarchy_keyboard_overrides': {}},
        {'omarchy_keyboard_overrides': [{'name': '', 'type': 'pc'}]},
        {'omarchy_keyboard_overrides': [{'name': 'external-pc', 'type': 'unknown'}]},
        {'omarchy_keyboard_overrides': [{'name': 'same', 'type': 'pc'},
                                       {'name': 'same', 'type': 'mac'}]},
    ]:
        output = run(dict(desktop_profile='omarchy') | invalid, success=False)
        assert 'keyboard' in output.lower(), output


def verify_dotconfig(work):
    """Dotconfig installation, failure recovery and existing checkout detection."""
    run = make_harness(work)

    # Intercept the download so the task can use its real URL without network access.
    home = work / 'home' / '.config'
    home.parent.mkdir()
    installer = work / 'dotconfig install.sh'
    downloads = work / 'dotconfig-downloads'
    curl = work / 'dotconfig-bin' / 'curl'
    curl.parent.mkdir()
    curl.write_text(f"""#!/bin/bash
set -euo pipefail
[[ ${{@: -1}} == https://raw.githubusercontent.com/harryxu/dotconfig/refs/heads/main/install.sh ]]
while [[ $1 != --output ]]; do shift; done
echo downloaded >> {shlex.quote(str(downloads))}
cp -- {shlex.quote(str(installer))} "$2"
""")
    curl.chmod(0o755)
    calls = home.parent / 'installer-calls'
    installer_script = f"""#!/bin/bash
set -euo pipefail
[[ $HOME == {shlex.quote(str(home.parent))} && $# -eq 0 ]]
echo called >> "$HOME/installer-calls"
git init --quiet "$HOME/.config"
[[ ! -e "$HOME/fail-install" ]]
echo installed > "$HOME/.config/settings"
"""
    deploy = dict(desktop_profile='omarchy', verify_dotconfig=True)
    run(deploy, check=True)
    assert not downloads.exists() and not calls.exists() and not home.exists()
    installer.touch()
    output = run(deploy, success=False)
    assert 'without creating ~/.config/.git' in output
    installer.write_text(installer_script)
    # Upstream creates .git before later setup steps, so a failure must allow a retry.
    fail_install = home.parent / 'fail-install'
    fail_install.touch()
    run(deploy, success=False)
    assert calls.read_text().splitlines() == ['called']
    assert not (home / '.git').exists() and not (home / 'settings').exists()
    fail_install.unlink()
    run(deploy)
    assert (home / '.git').is_dir() and (home / 'settings').read_text() == 'installed\n'
    (home / 'settings').write_text('local edit\n')
    installer.unlink()  # Even the download must be skipped for an existing repository.
    assert re.search(r'changed=0\b', run(deploy))
    # Linked worktrees have a .git file pointing to their Git directory.
    (home / '.git').rename(work / 'git-dir')
    (home / '.git').write_text(f"gitdir: {work / 'git-dir'}\n")
    assert re.search(r'changed=0\b', run(deploy))
    assert downloads.read_text().splitlines() == ['downloaded'] * 3
    assert calls.read_text().splitlines() == ['called', 'called']
    assert (home / 'settings').read_text() == 'local edit\n'


def verify_xremap(work):
    """KDE-only xremap entry point, launcher and session guard."""
    run = make_harness(work)
    home = work / 'home' / '.config'
    output = run(dict(desktop_profile='omarchy', verify_xremap_entry=True),
                 success=False, check=True)
    assert 'xremap requires the KDE desktop profile.' in output

    # Exercise both the real service condition and direct startup with a harmless backend.
    launcher = work / 'home/.local/bin/xremap-launcher'
    launcher.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'files/kde/xremap-launcher', launcher)
    launcher.chmod(0o755)
    backend = work / 'home/.local/share/xremap-features/kde/bin/xremap'
    backend.parent.mkdir(parents=True)
    backend.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$XREMAP_TEST_MARKER"\n')
    backend.chmod(0o755)
    unit = configparser.ConfigParser(interpolation=None)
    unit.read(ROOT / 'files/kde/xremap.service')
    unit_commands = {
        key: shlex.split(unit['Service'][key].replace('%h', str(work / 'home')))
        for key in ['ExecCondition', 'ExecStart']
    }
    marker = work / 'xremap-invocations'
    for desktop in ['KDE', 'plasma', 'KDE:PLASMA', 'Hyprland', 'GNOME', 'COSMIC', '', 'notkde']:
        allowed = desktop in ['KDE', 'plasma', 'KDE:PLASMA']
        session_env = ENV | {'HOME': str(work / 'home'), 'XDG_CURRENT_DESKTOP': desktop,
                             'XREMAP_TEST_MARKER': str(marker)}
        marker.unlink(missing_ok=True)
        condition = subprocess.run(unit_commands['ExecCondition'], env=session_env,
                                   text=True, capture_output=True)
        assert condition.returncode == (0 if allowed else 1), (desktop, condition.stderr)
        assert not marker.exists(), 'ExecCondition started xremap'
        startup = subprocess.run(unit_commands['ExecStart'], env=session_env,
                                 text=True, capture_output=True)
        assert startup.returncode == 0, (desktop, startup.stderr)
        assert marker.exists() == allowed, f'xremap startup guard failed for {desktop!r}'
        if allowed:
            assert marker.read_text().splitlines() == [str(home / 'xremap/config.yml'), '--watch']


def verify_user_service(work):
    """Offline systemd user service enablement and stable reruns."""
    run = make_harness(work)
    home = work / 'home' / '.config'
    # Enabling a user service must also work without a running user bus.
    units = home / 'systemd/user'
    units.mkdir(parents=True)
    (units / 'proarch-fixture.service').write_text(
        '[Unit]\nDescription=Disposable fixture\n[Service]\nExecStart=/usr/bin/true\n'
        '[Install]\nWantedBy=graphical-session.target\n')
    offline = dict(desktop_profile='omarchy', verify_user_service=True,
                   user_service='proarch-fixture.service', target_uid='999999',
                   has_graphical_session=False)
    run(offline)
    assert (units / 'graphical-session.target.wants/proarch-fixture.service').is_symlink()
    assert re.search(r'changed=0\b', run(offline)), 'Offline service enable is not idempotent'


def verify_autostart(work):
    """Omarchy autostart template rendering and Lua syntax checks."""
    run = make_harness(work, verify_autostart=True)
    run(dict(desktop_profile='omarchy'))
    command(['luac', '-p', str(work / 'autostart.lua')])
    for path in (ROOT / 'files/omarchy/hypr').glob('*.lua'):
        command(['luac', '-p', str(path)])


def verify_app_themes(work):
    """Omarchy app theme opt-outs, browser policies and editor bridges."""
    link_playbook_files(work)

    # Deploy Omarchy opt-outs and release only legacy forced Chrome theme policies.
    app_home = work / 'app-home'
    policy_root = work / 'browser-policy-root'
    code_settings = app_home / '.config/Code/User/settings.json'
    code_settings.parent.mkdir(parents=True)
    original_code = '''{
  // Keep this comment and the manually chosen theme.
  "workbench.colorTheme": "Light+",
  "window.autoDetectColorScheme": true,
  "custom.url": "https://example.invalid//keep",
  "nested": {"window.autoDetectColorScheme": true},
}
'''
    code_settings.write_text(original_code)
    code_settings.chmod(0o600)
    nvim_theme = app_home / '.config/nvim/lua/plugins/theme.lua'
    nvim_theme.parent.mkdir(parents=True)
    generated_nvim = app_home / '.local/state/omarchy/current/theme/neovim.lua'
    generated_nvim.parent.mkdir(parents=True)
    generated_nvim.write_text('return { system_theme = "old" }\n')
    bridge_target = '../../../../.local/state/omarchy/current/theme/neovim.lua'
    nvim_theme.symlink_to(bridge_target)
    personal_nvim = nvim_theme.with_name('colorscheme.lua')
    personal_nvim.write_text('return { { "LazyVim/LazyVim", opts = { colorscheme = "nordfox" } } }\n')
    vimrc = app_home / '.vimrc'
    vimrc.write_text('colorscheme desert\n')
    editor_originals = {path: path.read_bytes() for path in [personal_nvim, vimrc]}
    (app_home / '.bash_profile').write_text('export KEEP_ME=yes\n')
    chrome_policy = policy_root / 'etc/opt/chrome/policies/managed/color.json'
    chrome_policy.parent.mkdir(parents=True)
    chrome_policy.write_text(json.dumps({'BrowserThemeColor': '#123456',
                                        'BrowserColorScheme': 'device', 'BrowserSignin': 0}))
    firefox_policy = policy_root / 'etc/firefox/policies/policies.json'
    firefox_policy.parent.mkdir(parents=True)
    firefox_policy.write_text(json.dumps({'policies': {'DisableTelemetry': True,
                                         'Preferences': {'browser.tabs.warnOnClose': False}}}))
    original_chrome = chrome_policy.read_bytes()
    old_chrome_backup = chrome_policy.with_name('color.json.previous~')
    old_chrome_backup.write_bytes(original_chrome)
    original_firefox = firefox_policy.read_bytes()
    app_play = work / 'apps.yml'
    app_play.write_text(json.dumps([{
        'name': 'Verify independent app themes in disposable directories',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars_files': [str(ROOT / 'default.config.yml')],
        'vars': {'desktop_profile': 'omarchy', 'target_home': str(app_home),
                 'target_user': USER, 'proarch_policy_root': str(policy_root),
                 'playbook_config_file': str(work / 'absent.yml')},
        'environment': {'HOME': str(app_home)},
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/configuration.yml')},
                  {'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/app_themes.yml')}],
    }]))

    def configure_app_themes(overrides=None):
        return command(['ansible-playbook', str(app_play), '-i', 'localhost,', '-c', 'local',
                        '-e', json.dumps({'ansible_become': False, 'desktop_profile': 'omarchy',
                                         'target_user': USER, 'playbook_config_file': str(work / 'absent.yml'),
                                         'omarchy_overrides': overrides or {}})])

    configure_app_themes()
    assert not nvim_theme.is_symlink() and not nvim_theme.exists()
    bridge_backups = list(nvim_theme.parent.glob('theme.lua.proarch-backup-*'))
    assert len(bridge_backups) == 1 and bridge_backups[0].readlink() == Path(bridge_target)
    assert generated_nvim.read_text() == 'return { system_theme = "old" }\n'
    assert all(path.read_bytes() == content for path, content in editor_originals.items())
    assert code_settings.read_text() == original_code
    assert code_settings.stat().st_mode & 0o777 == 0o600
    assert not list(code_settings.parent.glob('settings.json.*'))
    assert 'export KEEP_ME=yes' in (app_home / '.bash_profile').read_text()
    assert not (app_home / '.config/Code - Insiders').exists()
    assert not (app_home / '.mozilla').exists(), 'Created a Firefox profile unnecessarily'
    assert json.loads(chrome_policy.read_text()) == {'BrowserSignin': 0}
    chrome_backup_dir = policy_root / 'var/lib/proarch/backups/chrome-theme-policies'
    chrome_backups = list(chrome_backup_dir.glob('color.json.*~'))
    assert len(chrome_backups) == 2
    assert all(path.read_bytes() == original_chrome for path in chrome_backups)
    assert not old_chrome_backup.exists()
    # Chrome parses every policy file, including backups without a .json suffix.
    effective_chrome_policy = {}
    for policy_file in sorted(chrome_policy.parent.iterdir()):
        if policy_file.is_file():
            effective_chrome_policy.update(json.loads(policy_file.read_text()))
    assert not {'BrowserThemeColor', 'BrowserColorScheme'} & effective_chrome_policy.keys()
    assert firefox_policy.read_bytes() == original_firefox
    stable_apps = configure_app_themes()
    assert re.search(r'changed=0\b', stable_apps), stable_apps

    # Guards leave all preferences/policies unchanged under repeated theme retints.
    guard_bin = app_home / '.local/share/proarch/app-theme-guards/bin'
    fake_native = work / 'fake-native-omarchy'
    (fake_native / 'bin').mkdir(parents=True)
    native_marker = work / 'theme-retint-calls'
    for name in ['omarchy-theme-set-browser', 'omarchy-theme-set-firefox']:
        binary = fake_native / 'bin' / name
        binary.write_text('#!/bin/bash\nprintf "%s\\n" "$@" >> "$THEME_TEST_MARKER"\n')
        binary.chmod(0o755)
    app_environment = ENV | {'HOME': str(app_home), 'OMARCHY_PATH': str(fake_native),
                             'THEME_TEST_MARKER': str(native_marker),
                             'PATH': str(guard_bin) + ':' + ENV['PATH']}
    before_retint = [code_settings.read_bytes(), chrome_policy.read_bytes(), firefox_policy.read_bytes()]
    for color in ['dark', 'light']:
        for name in ['omarchy-theme-set-browser', 'omarchy-theme-set-firefox']:
            result = subprocess.run([str(guard_bin / name), color], env=app_environment,
                                    text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
    assert not native_marker.exists(), 'Browser retint guard delegated while disabled'
    assert before_retint == [code_settings.read_bytes(), chrome_policy.read_bytes(), firefox_policy.read_bytes()]
    # Omarchy may keep generating theme state; disconnected editors ignore it.
    generated_nvim.write_text('return { system_theme = "new" }\n')
    assert not nvim_theme.exists()
    assert all(path.read_bytes() == content for path, content in editor_originals.items())
    # A wrapper delegates to the packaged entry point when its flag is removed.
    browser_flag = app_home / '.local/state/omarchy/toggles/skip-browser-theme-changes'
    browser_flag.unlink()
    subprocess.run([str(guard_bin / 'omarchy-theme-set-browser'), 'literal argument'],
                   env=app_environment, check=True)
    assert native_marker.read_text() == 'literal argument\n'
    browser_flag.touch()

    # Resolve through login Bash and fish without executing any native retint.
    resolved = subprocess.run(['bash', '-lc', 'command -v omarchy-theme-set-browser'],
                              env=app_environment, text=True, capture_output=True, check=True)
    assert resolved.stdout.strip() == str(guard_bin / 'omarchy-theme-set-browser'), resolved.stdout
    if shutil.which('fish'):
        resolved = subprocess.run(['fish', '--no-config', '-c',
                                   'source "$HOME/.config/fish/conf.d/proarch-app-themes.fish"; command -s omarchy-theme-set-browser'],
                                  env=app_environment, text=True, capture_output=True, check=True)
        assert resolved.stdout.strip() == str(guard_bin / 'omarchy-theme-set-browser')
    assert code_settings.read_text() == original_code
    assert json.loads(chrome_policy.read_text()) == {'BrowserSignin': 0}
    assert firefox_policy.read_bytes() == original_firefox
    # Users may change their application theme; redeployment must leave it alone.
    # A user-created regular theme file is retained on later deployments.
    custom_nvim = 'return { { "LazyVim/LazyVim", opts = { colorscheme = "user-theme" } } }\n'
    nvim_theme.write_text(custom_nvim)
    custom_code = original_code.replace('Light+', 'User-selected dark theme')
    code_settings.write_text(custom_code)
    stable_apps = configure_app_themes()
    assert re.search(r'changed=0\b', stable_apps), stable_apps
    assert code_settings.read_text() == custom_code
    assert nvim_theme.read_text() == custom_nvim
    assert all(path.read_bytes() == content for path, content in editor_originals.items())

    # Test broken legacy links and unrelated personal links with the real tasks.
    link_cases = [
        ('legacy', '../../../omarchy/current/theme/neovim.lua', True),
        ('legacy-home', '~/.config/omarchy/current/theme/neovim.lua', True),
        ('absolute', str(app_home / '.local/state/omarchy/current/theme/neovim.lua'), True),
        ('personal', 'personal-theme.lua', False),
    ]
    fixture_homes = []
    for label, target, remove in link_cases:
        fixture_home = work / ('editor-' + label)
        link = fixture_home / '.config/nvim/lua/plugins/theme.lua'
        link.parent.mkdir(parents=True)
        # Absolute targets belong to their own fixture home.
        if label == 'absolute':
            target = str(fixture_home / '.local/state/omarchy/current/theme/neovim.lua')
        link.symlink_to(target)
        fixture_homes.append(str(fixture_home))
    bridge_play = work / 'editor-bridges.yml'
    bridge_play.write_text(json.dumps([{
        'name': 'Verify known and personal editor bridges',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'tasks': [{'ansible.builtin.include_tasks': str(ROOT / 'tasks/desktop/omarchy/neovim_theme.yml'),
                   'loop': fixture_homes, 'vars': {'target_home': '{{ item }}'}}],
    }]))
    bridge_cmd = ['ansible-playbook', str(bridge_play), '-i', 'localhost,', '-c', 'local']
    command(bridge_cmd)
    for (label, target, remove), fixture_home in zip(link_cases, fixture_homes):
        link = Path(fixture_home) / '.config/nvim/lua/plugins/theme.lua'
        assert link.is_symlink() != remove, label
        backups = list(link.parent.glob('theme.lua.proarch-backup-*'))
        assert len(backups) == int(remove), label
        if not remove:
            assert str(link.readlink()) == target
    assert re.search(r'changed=0\b', command(bridge_cmd))


def verify_shell(work):
    """Omarchy Shell layout, plugin preferences and host-owned desktop settings."""
    link_playbook_files(work)
    home = work / 'shell-home'
    fake_native = work / 'fake-native-omarchy'
    (fake_native / 'bin').mkdir(parents=True)
    native_marker = work / 'theme-retint-calls'
    for name in ['omarchy-theme-set-browser', 'omarchy-theme-set-firefox']:
        binary = fake_native / 'bin' / name
        binary.write_text('#!/bin/bash\nprintf "%s\\n" "$@" >> "$THEME_TEST_MARKER"\n')
        binary.chmod(0o755)

    # Exercise real desktop tasks with a fake Omarchy CLI, never the live desktop.
    # Fonts and monitors belong to each host, even when other preferences change.
    (home / '.config/hypr').mkdir(parents=True)
    (home / '.config/hypr/hyprland.lua').write_bytes(HYPRLAND_DEFAULTS)
    (home / '.config/omarchy').mkdir()
    fake_cli = fake_native / 'bin/omarchy'
    theme_command_marker = work / 'unexpected-theme-command'
    fake_cli.write_text('''#!/bin/bash
if [[ $1 == theme ]]; then
  printf '%s\\n' "$*" >> "$THEME_COMMAND_MARKER"
  exit 99
fi
exit 0
''')
    fake_cli.chmod(0o755)
    fake_toggle = fake_native / 'bin/omarchy-toggle-enabled'
    fake_toggle.write_text('#!/bin/bash\n[[ $1 == screensaver-off ]]\n')
    fake_toggle.chmod(0o755)
    # A missing user file starts with the installed defaults, including new fields.
    indicators = {'id': 'omarchy.indicators', 'items': ['Dnd']}
    clock = {'id': 'omarchy.clock', 'format': 'HH:mm'}
    weather = {'id': 'omarchy.weather'}
    tray = {'id': 'omarchy.tray', 'pinned': ['user-app'], 'hidden': ['other-app']}
    managed_tray = tray | {'hidden': ['other-app', 'superwhisper']}
    shell_defaults = {'version': 1, 'bar': {'background': 'opaque', 'position': 'bottom',
                      'layout': {'left': ['omarchy.menu', 'omarchy.workspaces', 'user.widget'],
                                 'centerBegin': [indicators], 'center': [clock],
                                 'centerEnd': [weather], 'right': [tray, {'id': 'omarchy.agents'}],
                                 'tray': ['user.tray', {'id': 'superwhisper.panel'}, 'omarchy.model-usage']}},
                      'dock': {'autohide': False, 'pinned': ['system-app'], 'size': 48}}
    (fake_native / 'config/omarchy').mkdir(parents=True)
    (fake_native / 'config/omarchy/shell.json').write_text(json.dumps(shell_defaults))
    shell_play = work / 'shell-preferences.yml'
    shell_play.write_text(json.dumps([{
        'name': 'Verify desktop configuration preserves host fonts, monitors and theme',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars_files': [str(ROOT / 'default.config.yml')],
        'vars': {'target_home': str(home),
                 'ansible_facts': {'env': {'PATH': str(fake_native / 'bin') + ':' + ENV['PATH'],
                                          'OMARCHY_PATH': str(fake_native)}}},
        'environment': {'HOME': str(home), 'OMARCHY_PATH': str(fake_native),
                        'THEME_TEST_MARKER': str(native_marker),
                        'THEME_COMMAND_MARKER': str(theme_command_marker),
                        'PATH': str(fake_native / 'bin') + ':' + ENV['PATH']},
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/configuration.yml')},
                  {'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/hyprland.yml')},
                  {'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/shell.yml')}],
        'handlers': [{'name': name, 'ansible.builtin.debug': {'msg': 'Fixture only'}}
                     for name in ['Reload Hyprland', 'Synchronize Omarchy bar appearance']],
    }]))
    shell_cmd = ['ansible-playbook', str(shell_play), '-i', 'localhost,', '-c', 'local',
             '-e', json.dumps({'ansible_become': False, 'desktop_profile': 'omarchy',
                              'target_user': USER, 'playbook_config_file': str(work / 'absent.yml')})]
    command(shell_cmd)
    host_owned_paths = [home / relative for relative in [
        '.config/hypr/monitors.lua',
        '.config/omarchy/shell.toml',
        '.config/fontconfig/conf.d/99-proarch-fonts.conf',
    ]]
    assert all(not path.exists() for path in host_owned_paths), 'Created host font or monitor settings'
    personal_desktop = [
        '-- Personal display configuration\nhl.env("GDK_SCALE", "2")\n'
        'hl.monitor({ output = "DP-1", mode = "3840x2160@144", position = "0x0", scale = 1.5 })\n',
        '[font]\nfamily = "User Mono"\nbase-size = 17\n\n[other]\nenabled = true\n',
        '<?xml version="1.0"?>\n<fontconfig><alias><family>monospace</family>'
        '<prefer><family>User Mono</family></prefer></alias></fontconfig>\n',
    ]
    desktop_originals = dict(zip(host_owned_paths, [text.encode() for text in personal_desktop]))
    for path, content in desktop_originals.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    shell_json = home / '.config/omarchy/shell.json'
    shell_data = json.loads(shell_json.read_text())
    assert shell_data['bar'] == {
        'background': 'glassy', 'position': 'bottom',
        'layout': {'left': ['omarchy.menu', 'omarchy.workspaces', indicators, 'user.widget'],
                   'centerBegin': [], 'center': [], 'centerEnd': [],
                   'right': [managed_tray, weather, clock], 'tray': ['user.tray']},
    }
    assert shell_data['dock'] == shell_defaults['dock'] | {'autohide': True}
    assert shell_data['plugins'] == [
        {'id': 'harryxu.dropspace'}, {'id': 'harryxu.super-switcher'}, {'id': 'harryxu.dogedock'},
    ]
    assert shell_data['disabledPlugins'] == ['omarchy.dock']
    assert shell_data['cloneSourceRestores'] == ['harryxu.dogedock']
    # Move indicators from the previous layout while preserving the selected bar.
    shell_data['bar']['id'] = 'user.bar'
    shell_data['bar']['layout']['left'].remove(indicators)
    shell_data['bar']['layout']['right'].insert(1, indicators)
    shell_json.write_text(json.dumps(shell_data))
    command(shell_cmd)
    shell_data = json.loads(shell_json.read_text())
    assert shell_data['bar']['id'] == 'user.bar'
    assert shell_data['bar']['layout']['left'][2] == indicators
    assert shell_data['bar']['layout']['right'] == [managed_tray, weather, clock]
    shell_data['bar']['layout']['right'].remove(clock)
    shell_json.write_text(json.dumps(shell_data))
    command(shell_cmd)
    restored_clock = {'id': 'omarchy.clock', 'format': 'ddd d MMM HH:mm'}
    assert json.loads(shell_json.read_text())['bar']['layout']['right'] == [
        managed_tray, weather, restored_clock,
    ]
    deployed_shell = shell_json.read_bytes()
    stable_shell = command(shell_cmd)
    assert re.search(r'changed=0\b', stable_shell), stable_shell
    assert shell_json.read_bytes() == deployed_shell
    # Hosts can opt out of layout management while retaining shared Shell preferences.
    shell_cmd += ['-e', json.dumps({'omarchy_overrides': {
        'manage_top_bar': False,
        'plugins': [
            {'id': 'harryxu.super-switcher', 'repo': 'unused',
             'settings': {'options': {'delay': 100}}},
            {'id': 'fixture.new', 'repo': 'unused'},
        ],
    }})]
    shell_data['bar'] = {'background': 'opaque', 'position': 'left', 'id': 'user.bar',
                         'layout': {'center': [{'id': 'user.clock', 'format': 'HH:mm'}],
                                    'right': ['omarchy.agents']},
                         'user-option': {'enabled': True}}
    shell_data['dock'] = {'autohide': False, 'pinned': ['user-app'], 'size': 64}
    shell_data['font'] = {'family': 'User Mono', 'base-size': 17}
    dogedock = {'id': 'harryxu.dogedock', 'options': {'size': 64}}
    switcher = {'id': 'harryxu.super-switcher', 'options': {'delay': 50, 'preview': True}}
    dropped_from_management = {'id': 'harryxu.dropspace'}
    shell_data['plugins'] = [dogedock, switcher, dropped_from_management]
    shell_data['disabledPlugins'] = ['omarchy.dock', 'fixture.disabled']
    shell_data['cloneSourceRestores'] = ['harryxu.dogedock']
    shell_json.write_text(json.dumps(shell_data))
    command(shell_cmd)
    expected_shell = shell_data | {'bar': shell_data['bar'] | {'background': 'glassy'},
                                  'dock': shell_data['dock'] | {'autohide': True}}
    expected_shell['bar']['layout'] = shell_data['bar']['layout'] | {'right': []}
    expected_shell['plugins'] = [
        dogedock, switcher | {'options': {'delay': 100, 'preview': True}},
        dropped_from_management, {'id': 'fixture.new'},
    ]
    assert json.loads(shell_json.read_text()) == expected_shell
    assert all(path.read_bytes() == content for path, content in desktop_originals.items())
    # Equivalent personal formatting does not trigger a rewrite or another backup.
    shell_json.write_text(json.dumps(expected_shell))
    deployed_shell = shell_json.read_bytes()
    backups = sorted(shell_json.parent.glob('shell.json.*~'))
    stable_shell = command(shell_cmd)
    assert re.search(r'changed=0\b', stable_shell), stable_shell
    assert shell_json.read_bytes() == deployed_shell, 'Shell preferences changed on a stable rerun'
    assert sorted(shell_json.parent.glob('shell.json.*~')) == backups
    assert all(path.read_bytes() == content for path, content in desktop_originals.items()), \
        'Desktop deployment overwrote host font or monitor settings'
    assert not theme_command_marker.exists(), 'Shell deployment queried or switched the system theme'
    assert not native_marker.exists(), 'Shell deployment retinted applications'


def commit_fixture(repo, message):
    command(['git', '-C', str(repo), 'add', '.'])
    command(['git', '-C', str(repo), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', message])


def git_fixture_environment(home):
    return {
        'HOME': str(home),
        'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_ALLOW_PROTOCOL': 'file',
    }


def verify_kde_themes(work):
    """KDE theme source updates, installers and stable reruns."""
    # Real KDE sync tasks against a local upstream; installer stubs stay inside /tmp.
    upstream = work / 'theme-upstream'
    upstream.mkdir()
    (upstream / 'version.txt').write_text('one\n')
    installer = upstream / 'install.sh'
    installer.write_text('''#!/bin/bash
set -eu
case "${PWD##*/}" in
  graphite) destination="$HOME/.local/share/plasma/desktoptheme/Graphite-nord-light" ;;
  tela) destination="$HOME/.local/share/icons/Tela-circle" ;;
  *) exit 1 ;;
esac
mkdir -p "$destination"
cp version.txt "$destination/version.txt"
printf x >> "$destination/installs"
''')
    installer.chmod(0o755)
    command(['git', 'init', '--initial-branch=main', str(upstream)])
    commit_fixture(upstream, 'Theme version one')
    first_revision = command(['git', '-C', str(upstream), 'rev-parse', 'HEAD']).strip()
    theme_home = work / 'theme-home'
    theme_play = work / 'themes.yml'
    theme_environment = git_fixture_environment(theme_home)
    theme_play.write_text(json.dumps([{
        'name': 'Verify live KDE theme updates in a disposable home',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars': {
            'target_home': str(theme_home), 'target_user': USER,
            'profile_defaults': {
                'theme_repositories': {name: str(upstream) for name in ['graphite', 'aqua', 'tela']},
            },
        },
        'environment': theme_environment,
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/kde/theme_sources.yml')}],
        'handlers': [{'ansible.builtin.import_tasks': str(ROOT / 'handlers/main.yml')}],
    }]))

    def sync_themes():
        return command(['ansible-playbook', str(theme_play), '-i', 'localhost,',
                        '-c', 'local', '-e', '{"ansible_become": false}'])

    destinations = [theme_home / '.local/share/plasma/desktoptheme/Graphite-nord-light',
                    theme_home / '.local/share/icons/Tela-circle']
    sync_themes()
    for destination in destinations:
        assert (destination / 'version.txt').read_text() == 'one\n'
        assert (destination / 'installs').read_text() == 'x', 'Initial install ran twice'
    stable_themes = sync_themes()
    assert re.search(r'changed=0\b', stable_themes), stable_themes

    # Also cover migration from a detached, previously pinned checkout.
    graphite_checkout = theme_home / '.local/share/proarch/themes/graphite'
    command(['git', '-C', str(graphite_checkout), 'checkout', '--detach', first_revision])
    (upstream / 'version.txt').write_text('two\n')
    commit_fixture(upstream, 'Theme version two')
    sync_themes()
    for destination in destinations:
        assert (destination / 'version.txt').read_text() == 'two\n'
        assert (destination / 'installs').read_text() == 'xx', 'Update did not install exactly once'
    aqua = theme_home / '.local/share/kwin/tabbox/AquaMediumIcons/version.txt'
    assert aqua.read_text() == 'two\n'
    stable_themes = sync_themes()
    assert re.search(r'changed=0\b', stable_themes), stable_themes


def verify_omarchy_plugins(work):
    """Omarchy plugin installation and preservation of existing checkouts."""
    upstream = work / 'plugin-upstream'
    upstream.mkdir()
    command(['git', 'init', '--initial-branch=main', str(upstream)])
    (upstream / 'version.txt').write_text('one\n')
    # Omarchy plugins also default to HEAD when no version is supplied.
    (upstream / 'manifest.json').write_text(json.dumps({'id': 'fixture.plugin'}))
    commit_fixture(upstream, 'Initial test plugin')
    plugin_home = work / 'plugin-home'
    plugin_play = work / 'plugin.yml'
    plugin_play.write_text(json.dumps([{
        'name': 'Verify install-only plugins in a disposable home',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars': {'target_home': str(plugin_home), 'omarchy_settings': {
            'plugins': [{'id': 'fixture.plugin', 'repo': str(upstream)}],
        }},
        'environment': git_fixture_environment(plugin_home),
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/plugins.yml')}],
        'handlers': [{'name': 'Rescan Omarchy plugins', 'ansible.builtin.debug': {
            'msg': 'Offline fixture received plugin rescan notification',
        }}],
    }]))

    def sync_plugin():
        return command(['ansible-playbook', str(plugin_play), '-i', 'localhost,', '-c', 'local'])

    sync_plugin()
    plugin_file = plugin_home / '.config/omarchy/plugins/fixture.plugin/version.txt'
    assert plugin_file.read_text() == 'one\n'
    (upstream / 'version.txt').write_text('plugin latest\n')
    commit_fixture(upstream, 'Update test plugin')
    # Existing clean installations must not update when upstream advances.
    stable_plugin = sync_plugin()
    assert re.search(r'changed=0\b', stable_plugin), stable_plugin
    assert plugin_file.read_text() == 'one\n'
    # Preserve the local edits that previously caused the entire play to fail.
    plugin_file.write_text('personal plugin changes\n')
    plugin_checkout = plugin_file.parent
    untracked_plugin_file = plugin_checkout / 'personal.qml'
    untracked_plugin_file.write_text('// Personal customization\n')
    plugin_status = command(['git', '-C', str(plugin_checkout), 'status', '--porcelain'])
    stable_plugin = sync_plugin()
    assert re.search(r'changed=0\b', stable_plugin), stable_plugin
    assert plugin_file.read_text() == 'personal plugin changes\n'
    assert untracked_plugin_file.read_text() == '// Personal customization\n'
    assert command(['git', '-C', str(plugin_checkout), 'status', '--porcelain']) == plugin_status
    # A manually installed plugin need not be a Git checkout.
    (plugin_checkout / '.git').rename(plugin_checkout / '.git.saved')
    assert re.search(r'changed=0\b', sync_plugin())


GROUPS = {
    'config': verify_config,
    'bindings': verify_bindings,
    'keyboard': verify_keyboard,
    'wallpapers': verify_wallpapers,
    'shell': verify_shell,
    'app-themes': verify_app_themes,
    'autostart': verify_autostart,
    'hyprland-reload': verify_hyprland_reload,
    'omarchy-plugins': verify_omarchy_plugins,
    'kde-themes': verify_kde_themes,
    'xremap': verify_xremap,
    'sddm': verify_sddm,
    'dotconfig': verify_dotconfig,
    'user-service': verify_user_service,
    'snapper': verify_snapper,
    't2-keyboard': verify_t2_keyboard,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='list available groups and exit')
    parser.add_argument('groups', nargs='*', metavar='GROUP',
                        help='groups to run (default: all; see --list)')
    args = parser.parse_args()
    for name in args.groups:
        if name not in GROUPS:
            parser.error(f'unknown group {name!r}; use --list to see available groups')
    if args.list:
        for name, verify in GROUPS.items():
            print(f'{name:17} {verify.__doc__}')
        return

    for name in dict.fromkeys(args.groups or GROUPS):
        print(f'RUN  {name}', flush=True)
        with tempfile.TemporaryDirectory(prefix=f'proarch-verify-{name}-', dir='/tmp') as temporary:
            GROUPS[name](Path(temporary))
        print(f'PASS {name}', flush=True)


if __name__ == '__main__':
    main()
