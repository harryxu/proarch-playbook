-- Run from the repository root: lua tests/verify_app_window_cycle.lua
local bindings, active, windows, focused = {}, nil, {}, {}
local raised = 0
local function noop() end
o = { bind = function(key, _, action) bindings[key] = action end }
o.rebind = o.bind
hl = {
  unbind = noop,
  get_active_window = function() return active end,
  get_windows = function() return windows end,
  dsp = {
    focus = function(options) return { focus = options.window } end,
    window = {
      cycle_next = noop,
      bring_to_top = function() return { raise = true } end,
    },
  },
  dispatch = function(action)
    if action.raise then raised = raised + 1; return end
    focused[#focused + 1] = action.focus
    for _, window in ipairs(windows) do
      if action.focus == 'address:' .. window.address then active = window end
    end
  end,
}
dofile('files/omarchy/hypr/bindings.lua')

local function window(id, class, workspace)
  return { stable_id = id, address = tostring(id), class = class or 'chrome',
    mapped = true, hidden = false, accepts_input = true,
    workspace = { id = workspace or 1 } }
end
local first, second, third = window(1), window(2), window(3, 'chrome', 2)
local hidden, unmapped, no_input = window(4), window(5), window(6)
hidden.hidden, unmapped.mapped, no_input.accepts_input = true, false, false
windows = { third, window(7, 'code'), hidden, second, window(8, 'chrome', -1),
  first, unmapped, no_input }
active = first
for _, expected in ipairs({ second, third, first }) do
  bindings['SUPER + grave']()
  assert(active == expected, 'Forward cycle must reach all same-app windows and wrap')
end
bindings['SUPER + SHIFT + grave']()
assert(active == third, 'Reverse cycle must wrap')
assert(raised == 4, 'Each focused window must be raised')

local count = #focused
for _, current in ipairs({ window(9, 'single'), window(10, '') }) do
  active = current
  bindings['SUPER + grave']()
end
active = nil
bindings['SUPER + grave']()
assert(#focused == count, 'Missing matches or active application must be a no-op')
windows, active = { first }, first
bindings['SUPER + grave']()
assert(#focused == count, 'A single window must be a no-op')
print('PASS: same-app window cycling, reverse, wrap, filtering and empty/single window cases')
