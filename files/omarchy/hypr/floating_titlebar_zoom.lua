local M = {}
local workspace_tag = "omarchy-floating-workspace"
local restore_prefix = "proarch-titlebar-zoom-"

local function set_geometry(window, x, y, width, height)
  hl.dispatch(hl.dsp.window.resize({ window = window, x = width, y = height }))
  hl.dispatch(hl.dsp.window.move({ window = window, x = x, y = y }))
end

function M.toggle(address)
  local window = hl.get_window("address:" .. address)
  if not window or not window.mapped or not window.floating then
    return
  end

  local monitor = window.monitor
  if not monitor then
    return
  end

  local on_floating_workspace = false
  local restore
  for _, tag in ipairs(window.tags) do
    if tag == workspace_tag then
      on_floating_workspace = true
    elseif tag:sub(1, #restore_prefix) == restore_prefix then
      restore = tag
    end
  end
  if not on_floating_workspace then
    return
  end

  -- The stock maximize button can still put this window in maximized mode.
  if window.fullscreen == 1 then
    hl.dispatch(hl.dsp.window.fullscreen({ window = window, mode = "maximized", action = "unset" }))
    return
  elseif window.fullscreen ~= 0 then
    return
  end

  local width, height = monitor.width / monitor.scale, monitor.height / monitor.scale
  if monitor.transform % 2 == 1 then
    width, height = height, width
  end

  -- Coordinates and reserved areas are in logical pixels. The window geometry
  -- excludes its server-side titlebar and borders.
  local reserved = monitor.reserved
  local border = hl.get_config("general.border_size")
  local titlebar = hl.get_config("plugin.hyprbars.bar_height")
  local left = math.ceil(reserved.left + border)
  local top = math.ceil(reserved.top + border + titlebar)
  width = math.floor(width - reserved.right - border) - left
  height = math.floor(height - reserved.bottom - border) - top
  if width < 1 or height < 1 then
    return
  end

  if restore then
    local monitor_id, x, y, w, h = restore:sub(#restore_prefix + 1):match("^(%d+)_(-?%d+)_(-?%d+)_(%d+)_(%d+)$")
    if monitor_id then
      hl.dispatch(hl.dsp.window.tag({ window = window, tag = "-" .. restore }))
      x, y, w, h = tonumber(x), tonumber(y), tonumber(w), tonumber(h)
      if tonumber(monitor_id) ~= monitor.id then
        -- Keep the titlebar reachable after moving to another display.
        w, h = math.min(w, width), math.min(h, height)
        x = math.max(left, math.min(x, left + width - w))
        y = math.max(top, math.min(y, top + height - h))
      end
      set_geometry(window, monitor.x + x, monitor.y + y, w, h)
      return
    end
  end

  local at, size = window.at, window.size
  -- Store the original geometry on the window, so it survives config reloads
  -- and is discarded when that window closes.
  local tag = ("%s%d_%d_%d_%d_%d"):format(restore_prefix, monitor.id, at.x - monitor.x, at.y - monitor.y, size.x, size.y)
  hl.dispatch(hl.dsp.window.tag({ window = window, tag = "+" .. tag }))
  set_geometry(window, monitor.x + left, monitor.y + top, width, height)
end

local function override_double_click()
  if hl.plugin.hyprbars and hl.get_config("plugin.hyprbars.workspace_tag") == workspace_tag then
    hl.config({ plugin = { hyprbars = {
      on_double_click = [[hyprctl eval 'require("hypr.floating_titlebar_zoom").toggle("%WINDOW%")']],
    } } })
  end
end

-- Omarchy can configure titlebars lazily when the first workspace starts
-- floating. Reapply only the double-click override after that configuration.
if o and o.workspace_mode then
  local workspace_mode = o.workspace_mode
  o.workspace_mode = function(spec)
    workspace_mode(spec)
    override_double_click()
  end
  override_double_click()
end

return M
