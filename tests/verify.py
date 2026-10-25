#!/usr/bin/env python3
"""Exercise configuration gates and real dotconfig copies in temporary homes."""
import json
import os
from pathlib import Path
import re
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

    def run(overrides, success=True):
        variables = work / 'vars.json'
        variables.write_text(json.dumps(base | overrides))
        result = subprocess.run(['ansible-playbook', str(harness), '-i', 'localhost,',
                                 '-c', 'local', '-e', '@' + str(variables)],
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
    for overrides in [{'docker': 'false'}, {'unknown_feature': True}, {'cliphist': True}]:
        run(dict(desktop_profile='omarchy', feature_overrides=overrides), success=False)

    # A real local Git source and a disposable existing home: backups, allowlist, idempotence.
    source = work / 'source'
    for name, text in {'nvim/init.lua': 'return {}\n', 'git/config': '[core]\n  editor = nvim\n',
                       'omarchy/shell.json': 'must not deploy\n'}.items():
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
                  dotconfig_repo=str(source), dotconfig_source_dir=str(work / 'checkout'),
                  dotconfig_paths=['nvim', 'git'])
    run(deploy)
    assert (home / 'nvim/init.lua').read_text() == 'return {}\n'
    backups = list((home / 'nvim').glob('init.lua.*~'))
    assert len(backups) == 1 and backups[0].read_text() == 'personal previous content\n'
    assert (home / 'omarchy/shell.json').read_text() == 'desktop sentinel\n'
    assert (home / '.git/sentinel').read_text() == 'existing repository\n'
    second = run(deploy)
    assert re.search(r'changed=0\b', second), second
    assert len(list((home / 'nvim').glob('init.lua.*~'))) == 1
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
    print('PASS: explicit selection, both profiles, override precedence, invalid settings,')
    print('      real allowlist copies, per-file backups, preserved desktop/repository,')
    print('      second-run idempotence, offline service enable and Lua parsing. No live configuration changed.')
