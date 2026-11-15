"""Merge Ansible-managed plugin settings into Omarchy's activation list."""

from collections.abc import Mapping

from ansible.utils.vars import merge_hash


def merge_omarchy_plugins(current, managed):
    entries = list(current) if isinstance(current, list) else []
    positions = {}
    for index, entry in enumerate(entries):
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
            positions.setdefault(entry["id"], index)

    for plugin in managed:
        plugin_id = plugin["id"]
        settings = {**plugin.get("settings", {}), "id": plugin_id}
        if plugin_id in positions:
            index = positions[plugin_id]
            entries[index] = merge_hash(entries[index], settings)
        else:
            positions[plugin_id] = len(entries)
            entries.append(settings)
    return entries


def apply_dogedock_replacement(config, managed):
    plugin_id = "harryxu.dogedock"
    stock_id = "omarchy.dock"
    disabled = config.get("disabledPlugins", [])
    if not any(plugin["id"] == plugin_id for plugin in managed):
        return config
    if plugin_id in disabled or stock_id in disabled:
        return config

    # Match Omarchy's clone activation so disabling DogeDock restores the stock Dock.
    restores = config.get("cloneSourceRestores", [])
    return {
        **config,
        "disabledPlugins": [*disabled, stock_id],
        "cloneSourceRestores": restores if plugin_id in restores else [*restores, plugin_id],
    }


class FilterModule:
    def filters(self):
        return {
            "merge_omarchy_plugins": merge_omarchy_plugins,
            "apply_dogedock_replacement": apply_dogedock_replacement,
        }
