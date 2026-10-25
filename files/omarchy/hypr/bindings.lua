-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
o.bind("SUPER + e", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- DropSpace: Drag and drop window to workspace

-- Use Super instead of Alt for window switching.
hl.unbind("ALT + TAB")
o.bind("ALT + TAB", "Next workspace", hl.dsp.focus({ workspace = "m+1" }))
hl.unbind("ALT + SHIFT + TAB")
o.bind("ALT + SHIFT + TAB", "Previous workspace", hl.dsp.focus({ workspace = "m-1" }))
o.rebind("SUPER + TAB", "Focus on next window", hl.dsp.window.cycle_next())
o.bind("SUPER + TAB", "Reveal active window on top", hl.dsp.window.bring_to_top())
o.rebind("SUPER + SHIFT + TAB", "Focus on previous window", hl.dsp.window.cycle_next({ next = false }))
o.bind("SUPER + SHIFT + TAB", "Reveal active window on top", hl.dsp.window.bring_to_top())

-- Use Ctrl+Space to switch input language.
hl.unbind("SUPER + I")
o.rebind("CTRL + SPACE", "Switch input language", "omarchy-input-method cycle")
