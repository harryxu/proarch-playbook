# Prountu

Configure an Arch Linux desktop into a suitable development environment for programmers.

## Usage

### [Installing Ansible](https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-arch-linux) on Arch Linux.

```shell
sudo pacman -S ansible
```

### Run Ansible commands inside this directory.

- `ansible-galaxy install -r requirements.yml`
- `ansible-playbook main.yml`

## Install optional packages.

### OneDrive

```
yay -S onedrive-abraunegg onedrivegui
```
