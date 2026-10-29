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

-- Replace the Quake console shortcuts with macOS-style app window switching.
local function cycle_app_window(step)
  local active = hl.get_active_window()
  if not active or active.class == "" then return end

  local windows = {}
  for _, window in ipairs(hl.get_windows()) do
    if window.class == active.class and window.mapped and not window.hidden
      and window.accepts_input and window.workspace and window.workspace.id >= 0 then
      windows[#windows + 1] = window
    end
  end
  if #windows < 2 then return end

  -- A stable order allows repeated presses to reach every window.
  table.sort(windows, function(a, b) return a.stable_id < b.stable_id end)
  for index, window in ipairs(windows) do
    if window.address == active.address then
      local target = windows[(index - 1 + step) % #windows + 1]
      hl.dispatch(hl.dsp.focus({ window = "address:" .. target.address }))
      hl.dispatch(hl.dsp.window.bring_to_top())
      return
    end
  end
end

o.rebind("SUPER + grave", "Next window of current application", function() cycle_app_window(1) end)
o.rebind("SUPER + SHIFT + grave", "Previous window of current application", function() cycle_app_window(-1) end)

-- Use Ctrl+Space to switch input language.
hl.unbind("SUPER + I")
o.rebind("CTRL + SPACE", "Switch input language", "omarchy-input-method cycle")

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
