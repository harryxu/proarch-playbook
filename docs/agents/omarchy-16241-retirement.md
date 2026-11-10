# Retire the Omarchy #16241 workaround

Run this procedure when asked whether the floating-window workaround can be
removed. It covers refocusing a maximized or fullscreen window in a floating
workspace by clicking it or switching windows.

1. **Verify the stable release.** Read the
   [Omarchy issue](https://github.com/omacom/omarchy/issues/16241), its linked
   fixes, and the [latest stable release](https://github.com/omacom/omarchy/releases/latest).
   Identify the stable tag and cite release notes or tagged source showing
   that it contains the fix. For a Hyprland fix, also verify that the Omarchy
   stable channel ships a Hyprland build containing that fix. The
   [proposed Alt+Tab change](https://github.com/omacom/omarchy/pull/16412)
   covers a subset of the behavior. Require evidence that clicking a window
   also works before retiring the focus hook. If the evidence is missing or
   the fix is available only on a development or prerelease channel, keep the
   workaround and report the latest stable version and the missing evidence.
2. **Update the target.** Run `omarchy channel current`, `omarchy version`,
   and `pacman -Q omarchy hyprland`. If the target needs the verified stable
   update, run `omarchy update` in the target user's Omarchy terminal on the
   stable channel. Follow the updater prompts and resume after any requested
   reboot. Check the installed versions again and use `hyprctl version` to
   confirm that the running compositor has the required fix when it ships
   through Hyprland. Keep the workaround if the fixed build has yet to reach
   the target or the update fails. [Official update procedure](https://github.com/omacom/omarchy/blob/quattro/docs/update-process.md)
3. **Remove and verify on the target.** Resolve the desktop user's home and
   back up `~/.config/hypr/hyprland.lua` and
   `~/.config/hypr/floating_fullscreen_workaround.lua` if present. Remove
   the `require("hypr.floating_fullscreen_workaround")` line and its
   trailing comment from `hyprland.lua`. In that user's graphical session,
   run `hyprctl reload` and `hyprctl configerrors`. On a floating workspace
   with two or more windows, maximize one, focus another, and refocus the
   maximized one by clicking its exposed area and by using the window
   switcher. Repeat with true fullscreen. The focused window must appear
   in front both ways. If config validation or the behavior check fails,
   restore the loader, reload, and keep the repository deployment. After the
   checks pass, delete the installed workaround Lua file.
4. **Remove the deployment from Proarch.** Delete
   `tasks/desktop/omarchy/floating_fullscreen_workaround.yml` and its
   import from `tasks/desktop/omarchy/hyprland.yml`. Delete
   `files/omarchy/hypr/floating_fullscreen_workaround.lua` and its
   deployment assertions and fixtures in `tests/verify.py`. Remove the
   pointer in `AGENTS.md` and this runbook. Search the checkout and the
   target's active Hyprland configuration for `floating_fullscreen_workaround`
   and `16241` to verify removal. Run the syntax checks for both profiles and
   `python3 tests/verify.py`. Report the verified stable release and the
   target and repository changes.
