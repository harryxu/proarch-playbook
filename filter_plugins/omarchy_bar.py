"""Apply the Omarchy profile's widget placement to existing Shell settings."""

from collections.abc import Mapping


def widget_id(entry):
    return entry.get("id") if isinstance(entry, Mapping) else entry


def place_omarchy_bar_widgets(config):
    bar = dict(config.get("bar", {}))
    layout = dict(bar.get("layout", {}))
    center_sections = ("centerBegin", "center", "centerEnd")
    left = layout.get("left", [])
    right = layout.get("right", [])
    center = [entry for section in center_sections for entry in layout.get(section, [])]
    visible_widgets = left + right + center
    indicators = [entry for entry in visible_widgets if widget_id(entry) == "omarchy.indicators"]
    clocks = [entry for entry in visible_widgets if widget_id(entry) == "omarchy.clock"]
    relocated_ids = {"omarchy.indicators", "omarchy.clock"}
    left = [entry for entry in left if widget_id(entry) not in relocated_ids]
    right = [entry for entry in right + center if widget_id(entry) not in relocated_ids]
    after_workspaces = next(
        (index + 1 for index, entry in enumerate(left) if widget_id(entry) == "omarchy.workspaces"),
        len(left),
    )

    layout["left"] = left[:after_workspaces] + indicators + left[after_workspaces:]
    layout["right"] = right + clocks
    for section in center_sections:
        layout[section] = []
    return {**config, "bar": {**bar, "id": "proarch.bar", "layout": layout}}


def apply_omarchy_bar_visibility(config, hide_superwhisper, disable_agents):
    bar = config.get("bar", {})
    if "layout" not in bar:
        return config

    excluded_widgets = set()
    if hide_superwhisper:
        excluded_widgets.add("superwhisper.panel")
    if disable_agents:
        excluded_widgets.update(("omarchy.agents", "omarchy.model-usage"))

    def hide_native_icon(entry):
        if not hide_superwhisper or widget_id(entry) != "omarchy.tray":
            return entry
        tray = dict(entry) if isinstance(entry, Mapping) else {"id": entry}
        hidden = tray.get("hidden", [])
        if "superwhisper" not in hidden:
            tray["hidden"] = [*hidden, "superwhisper"]
        return tray

    layout = {
        section: [hide_native_icon(entry) for entry in entries
                  if widget_id(entry) not in excluded_widgets]
        for section, entries in bar["layout"].items()
    }
    return {**config, "bar": {**bar, "layout": layout}}


class FilterModule:
    def filters(self):
        return {
            "place_omarchy_bar_widgets": place_omarchy_bar_widgets,
            "apply_omarchy_bar_visibility": apply_omarchy_bar_visibility,
        }
