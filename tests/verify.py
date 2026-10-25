#!/usr/bin/env python3
"""Exercise configuration gates and real dotconfig copies in temporary homes."""
import configparser
import json
import os
from pathlib import Path
import re
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


def command(args, **kwargs):
    result = subprocess.run(args, cwd=ROOT, env=ENV, text=True,
                            capture_output=True, **kwargs)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


with tempfile.TemporaryDirectory(prefix='proarch-verify-') as temporary:
    work = Path(temporary)
    (work / 'profiles').symlink_to(ROOT / 'profiles', target_is_directory=True)
    (work / 'files').symlink_to(ROOT / 'files', target_is_directory=True)
    (work / 'templates').symlink_to(ROOT / 'templates', target_is_directory=True)
    harness = work / 'verify.yml'
    harness.write_text("""---
- hosts: all
  gather_facts: false
  become: false
  vars_files:
    - """ + str(ROOT / 'default.config.yml') + """
  tasks:
    - ansible.builtin.import_tasks: """ + str(ROOT / 'tasks/configuration.yml') + """
    - ansible.builtin.copy:
        dest: "{{ result_file }}"
        content: "{{ {'profile': desktop_profile, 'features': features, 'omarchy': omarchy_settings} | to_json }}"
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/common/dotconfig.yml') + """
      when: verify_dotconfig | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/common/user_service.yml') + """
      when: verify_user_service | default(false)
    - ansible.builtin.include_tasks: """ + str(ROOT / 'tasks/extra_keybindings.yml') + """
      when: verify_xremap_entry | default(false)
    - ansible.builtin.template:
        src: """ + str(ROOT / 'templates/omarchy/monitors.lua.j2') + """
        dest: "{{ render_file }}"
      when: desktop_profile == 'omarchy'
    - ansible.builtin.template:
        src: """ + str(ROOT / 'templates/omarchy/autostart.lua.j2') + """
        dest: "{{ autostart_file }}"
      when: desktop_profile == 'omarchy'
""")
    user = command(['id', '-un']).strip()
    base = dict(ansible_become=False, playbook_config_file=str(work / 'absent.yml'),
                target_user=user, target_home=str(work / 'home'),
                result_file=str(work / 'result.json'), render_file=str(work / 'monitors.lua'),
                autostart_file=str(work / 'autostart.lua'))

    def run(overrides, success=True, check=False):
        variables = work / 'vars.json'
        variables.write_text(json.dumps(base | overrides))
        result = subprocess.run(['ansible-playbook', str(harness), '-i', 'localhost,',
                                 '-c', 'local', '-e', '@' + str(variables)]
                                + (['--check'] if check else []),
                                cwd=ROOT, env=ENV, text=True, capture_output=True)
        if (result.returncode == 0) != success:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout + result.stderr

    for profile in ['', 'gnome', '../../kde']:
        (work / 'result.json').unlink(missing_ok=True)
        output = run(dict(desktop_profile=profile), success=False)
        assert 'Set desktop_profile' in output, output
        assert not (work / 'result.json').exists(), 'Invalid selection reached a write task'

    for profile in ['kde', 'omarchy']:
        run(dict(desktop_profile=profile))
        data = json.loads((work / 'result.json').read_text())
        assert data['profile'] == profile
        assert data['features']['rime_ice'] == (profile == 'kde')
        assert data['features']['cliphist'] == (profile == 'kde')
        assert data['features']['vicinae'] == (profile == 'kde')

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
    assert data['omarchy']['shell']['bar']['layout']['left'], 'Nested defaults were lost'
    for overrides in [{'docker': 'false'}, {'unknown_feature': True},
                      {'cliphist': True}, {'keybindings': True}]:
        run(dict(desktop_profile='omarchy', feature_overrides=overrides), success=False)
    run(dict(desktop_profile='kde', feature_overrides={'keybindings': True}))
    assert json.loads((work / 'result.json').read_text())['features']['keybindings'] is True
    output = run(dict(desktop_profile='omarchy', verify_xremap_entry=True),
                 success=False, check=True)
    assert 'xremap requires the KDE desktop profile.' in output

    # A real local Git source and a disposable existing home: backups, allowlist, idempotence.
    source = work / 'source'
    for name, text in {'nvim/init.lua': 'return {}\n', 'git/config': '[core]\n  editor = nvim\n',
                       'nvim/space name.lua': 'return "space"\n',
                       'nvim/line\nbreak.lua': 'return "newline"\n',
                       'omarchy/shell.json': 'must not deploy\n',
                       'xremap/config.yml': 'modmap: []\n'}.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    command(['git', 'init', '--initial-branch=main', str(source)])
    command(['git', '-C', str(source), 'add', '.'])
    command(['git', '-C', str(source), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', 'Fixture'])
    home = work / 'home' / '.config'
    (home / 'nvim').mkdir(parents=True)
    (home / 'nvim/init.lua').write_text('personal previous content\n')
    (home / 'omarchy').mkdir()
    (home / 'omarchy/shell.json').write_text('desktop sentinel\n')
    (home / '.git').mkdir()
    (home / '.git/sentinel').write_text('existing repository\n')
    deploy = dict(desktop_profile='omarchy', verify_dotconfig=True,
                  dotconfig_repo=str(source), dotconfig_source_dir=str(work / 'checkout'))
    run(deploy)
    assert (home / 'nvim/init.lua').read_text() == 'return {}\n'
    assert (home / 'nvim/space name.lua').read_text() == 'return "space"\n'
    assert (home / 'nvim/line\nbreak.lua').read_text() == 'return "newline"\n'
    backups = list((home / 'nvim').glob('init.lua.*~'))
    assert len(backups) == 1 and backups[0].read_text() == 'personal previous content\n'
    assert (home / 'omarchy/shell.json').read_text() == 'desktop sentinel\n'
    assert (home / '.git/sentinel').read_text() == 'existing repository\n'
    assert not (home / 'xremap/config.yml').exists(), 'Omarchy deployed KDE configuration'
    second = run(deploy)
    assert re.search(r'changed=0\b', second), second
    assert len(list((home / 'nvim').glob('init.lua.*~'))) == 1
    run(deploy | {'desktop_profile': 'kde'})
    assert (home / 'xremap/config.yml').read_text() == 'modmap: []\n'

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
    for name in ['monitors.lua', 'autostart.lua']:
        command(['luac', '-p', str(work / name)])
    for path in (ROOT / 'files/omarchy/hypr').glob('*.lua'):
        command(['luac', '-p', str(path)])

    # Deploy only Omarchy opt-outs; application files must remain byte-for-byte intact.
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
    original_firefox = firefox_policy.read_bytes()
    app_play = work / 'apps.yml'
    app_play.write_text(json.dumps([{
        'name': 'Verify independent app themes in disposable directories',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars_files': [str(ROOT / 'default.config.yml')],
        'vars': {'desktop_profile': 'omarchy', 'target_home': str(app_home),
                 'target_user': user, 'proarch_policy_root': str(policy_root),
                 'playbook_config_file': str(work / 'absent.yml')},
        'environment': {'HOME': str(app_home)},
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/configuration.yml')},
                  {'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/app_themes.yml')}],
    }]))

    def configure_app_themes(overrides=None):
        return command(['ansible-playbook', str(app_play), '-i', 'localhost,', '-c', 'local',
                        '-e', json.dumps({'ansible_become': False, 'desktop_profile': 'omarchy',
                                         'target_user': user, 'playbook_config_file': str(work / 'absent.yml'),
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
    assert chrome_policy.read_bytes() == original_chrome
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
    # A playbook-triggered theme restore must use the same guards before login.
    # Exercise the real Shell tasks with a fake Omarchy CLI, never the live desktop.
    (app_home / '.config/fontconfig/conf.d').mkdir(parents=True)
    fake_cli = fake_native / 'bin/omarchy'
    fake_cli.write_text('''#!/bin/bash
case "$1 $2" in
  'theme current') echo old-theme ;;
  'theme set') omarchy-theme-set-browser "$3" ;;
esac
''')
    fake_cli.chmod(0o755)
    fake_toggle = fake_native / 'bin/omarchy-toggle-enabled'
    fake_toggle.write_text('#!/bin/bash\nexit 1\n')
    fake_toggle.chmod(0o755)
    restore_play = work / 'restore-theme.yml'
    restore_play.write_text(json.dumps([{
        'name': 'Verify the actual theme restoration uses guards',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars_files': [str(ROOT / 'default.config.yml')],
        'vars': {'target_home': str(app_home),
                 'ansible_facts': {'env': {'PATH': str(fake_native / 'bin') + ':' + ENV['PATH']}}},
        'environment': {'HOME': str(app_home), 'OMARCHY_PATH': str(fake_native),
                        'THEME_TEST_MARKER': str(native_marker),
                        'PATH': str(fake_native / 'bin') + ':' + ENV['PATH']},
        'tasks': [{'ansible.builtin.import_tasks': str(ROOT / 'tasks/configuration.yml')},
                  {'ansible.builtin.import_tasks': str(ROOT / 'tasks/desktop/omarchy/shell.yml')}],
        'handlers': [{'name': name, 'ansible.builtin.debug': {'msg': 'Fixture only'}}
                     for name in ['Reload Hyprland', 'Synchronize Omarchy bar appearance']],
    }]))
    command(['ansible-playbook', str(restore_play), '-i', 'localhost,', '-c', 'local',
             '-e', json.dumps({'ansible_become': False, 'desktop_profile': 'omarchy',
                              'target_user': user, 'playbook_config_file': str(work / 'absent.yml')})])
    assert native_marker.read_text() == 'literal argument\n', 'Playbook theme restore bypassed guards'
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
    assert chrome_policy.read_bytes() == original_chrome
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
    command(['git', '-C', str(upstream), 'add', '.'])
    command(['git', '-C', str(upstream), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', 'Theme version one'])
    first_revision = command(['git', '-C', str(upstream), 'rev-parse', 'HEAD']).strip()
    theme_home = work / 'theme-home'
    theme_play = work / 'themes.yml'
    theme_environment = {
        'HOME': str(theme_home),
        'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_ALLOW_PROTOCOL': 'file',
    }
    theme_play.write_text(json.dumps([{
        'name': 'Verify live KDE theme updates in a disposable home',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars': {
            'target_home': str(theme_home), 'target_user': user,
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
    # Omarchy plugins also default to HEAD when no version is supplied.
    (upstream / 'manifest.json').write_text(json.dumps({'id': 'fixture.plugin'}))
    command(['git', '-C', str(upstream), 'add', 'manifest.json'])
    command(['git', '-C', str(upstream), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', 'Add test plugin manifest'])
    plugin_home = work / 'plugin-home'
    plugin_play = work / 'plugin.yml'
    plugin_play.write_text(json.dumps([{
        'name': 'Verify plugin default latest checkout in a disposable home',
        'hosts': 'all', 'gather_facts': False, 'become': False,
        'vars': {'target_home': str(plugin_home), 'omarchy_settings': {
            'plugins': [{'id': 'fixture.plugin', 'repo': str(upstream)}],
        }},
        'environment': theme_environment | {'HOME': str(plugin_home)},
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
    command(['git', '-C', str(upstream), 'add', 'version.txt'])
    command(['git', '-C', str(upstream), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', 'Update test plugin'])
    sync_plugin()
    assert plugin_file.read_text() == 'plugin latest\n'
    stable_plugin = sync_plugin()
    assert re.search(r'changed=0\b', stable_plugin), stable_plugin
    # Also cover migration from a detached, previously pinned checkout.
    graphite_checkout = theme_home / '.local/share/proarch/themes/graphite'
    command(['git', '-C', str(graphite_checkout), 'checkout', '--detach', first_revision])
    (upstream / 'version.txt').write_text('two\n')
    command(['git', '-C', str(upstream), 'add', 'version.txt'])
    command(['git', '-C', str(upstream), '-c', 'user.name=Fixture', '-c',
             'user.email=fixture@example.invalid', 'commit', '-m', 'Theme version two'])
    sync_themes()
    for destination in destinations:
        assert (destination / 'version.txt').read_text() == 'two\n'
        assert (destination / 'installs').read_text() == 'xx', 'Update did not install exactly once'
    aqua = theme_home / '.local/share/kwin/tabbox/AquaMediumIcons/version.txt'
    assert aqua.read_text() == 'two\n'
    stable_themes = sync_themes()
    assert re.search(r'changed=0\b', stable_themes), stable_themes
    print('PASS: explicit selection, both profiles, override precedence, invalid settings,')
    print('      real allowlist copies, per-file backups, preserved desktop/repository,')
    print('      KDE-only xremap entry, configuration, launcher and service condition,')
    print('      latest KDE sources, source-change installation and stable reruns,')
    print('      default-latest Omarchy plugin clone/update and stable reruns,')
    print('      Omarchy retint opt-outs, Neovim bridge backups, preserved Vim/editor themes,')
    print('      second-run idempotence, offline service enable and Lua parsing. No live configuration changed.')
