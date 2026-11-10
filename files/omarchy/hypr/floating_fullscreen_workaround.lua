-- Temporary workaround for https://github.com/omacom/omarchy/issues/16241
hl.on("window.active", function(window)
  if not window or not window.floating or window.fullscreen == 0 or not window.workspace then
    return
  end

  local floating_workspace = false
  for _, tag in ipairs(window.tags) do
    if tag == "omarchy-floating-workspace" then
      floating_workspace = true
      break
    end
  end
  if not floating_workspace then
    return
  end

  -- Hyprland keeps other floating windows above fullscreen after focus returns.
  -- Lower them from top to bottom to clear that flag and retain their order.
  local windows = hl.get_windows()
  for i = #windows, 1, -1 do
    local other = windows[i]
    if other.address ~= window.address and other.floating and not other.pinned
        and other.workspace and other.workspace.id == window.workspace.id then
      hl.dispatch(hl.dsp.window.alter_zorder({ mode = "bottom", window = other }))
    end
  end
end)
