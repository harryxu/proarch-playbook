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


class FilterModule:
    def filters(self):
        return {"merge_omarchy_plugins": merge_omarchy_plugins}
