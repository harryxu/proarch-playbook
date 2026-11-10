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
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- Replace the audio panel shortcut with Omasnap's smart screenshot picker.
o.rebind("SUPER + CTRL + A", "Screenshot", "omasnap")

-- Move the clipboard manager to Super+Shift+V.
hl.unbind("SUPER + CTRL + V")
o.bind("SUPER + SHIFT + V", "Clipboard manager", { panel = "omarchy.clipboard" })

-- DropSpace: Drag and drop window to workspace

-- Use Ctrl+Space to switch input language.
hl.unbind("SUPER + I")
o.rebind("CTRL + SPACE", "Switch input language", "omarchy-input-method cycle")

-- Replace Super+F (full screen) with Ctrl+F in the focused application.
o.rebind("SUPER + F", "Find", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "F", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "F", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)

-- Reload the current tab when a browser window has focus.
local browser_classes = {
  ["google-chrome"] = true,
  ["google-chrome-stable"] = true,
  ["com.google.chrome"] = true,
  chromium = true,
  ["org.chromium.chromium"] = true,
  firefox = true,
  ["firefox-esr"] = true,
  ["org.mozilla.firefox"] = true,
}

o.bind("SUPER + R", "Reload browser tab", function()
  local active = hl.get_active_window()
  if not active or not browser_classes[active.class:lower()] then
    return { ok = false }
  end

  local window = "address:" .. active.address
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "R", state = "down", window = window }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "R", state = "up", window = window }))
  end, { timeout = 50, type = "oneshot" })
end, { auto_consuming = true })

-- Replace Super+S with Ctrl+S in the focused application.
-- Match Omarchy's explicit down/up forwarding to avoid stuck synthetic keys.
o.rebind("SUPER + S", "Save", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "S", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "S", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)

-- Replace Super+W (close window) with Ctrl+W in the focused application.
o.rebind("SUPER + W", "Close tab", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "W", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "W", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)

-- Move floating/tiling to Alt (Option)+F and use Super+T for a new tab.
o.bind("ALT + F", "Toggle window floating/tiling", hl.dsp.window.float({ action = "toggle" }))
o.rebind("SUPER + T", "New tab", function()
  local active = hl.get_active_window()
  if not active then return end

  -- Chrome uses Ctrl+T; Ctrl+Shift+T would reopen a closed tab there.
  local mods = active.class == "com.mitchellh.ghostty" and "CTRL SHIFT" or "CTRL"
  hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = "T", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = "T", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)

-- Forward Super+Z as Ctrl+Z in the focused application.
o.bind("SUPER + Z", "Undo", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "Z", state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "Z", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)
