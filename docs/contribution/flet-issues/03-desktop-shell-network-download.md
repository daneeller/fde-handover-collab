# Clean Windows machine attempts to download the desktop shell from the network at startup

> 已提交：https://github.com/flet-dev/flet/issues/7104 （2026-11-19，状态 OPEN）
> 从 #7100 拆出，独立跟踪。

Split out of #7100 so it can be tracked independently.

## Environment

- Flet 0.86.5, Python 3.14, Windows 11
- Distributed as a single desktop executable to machines with no prior Flet cache

## Observed behaviour

On a machine with no cached desktop runtime, startup stalled on a network
download and the application window did not appear. The download target was
GitHub, which is slow or unreachable in some networks. For offline/air-gapped
use this is a hard blocker, not a slow first run.

## Workaround currently required

At the very start of the program (before importing flet), probe for an existing
desktop shell and point `FLET_VIEW_PATH` at it:

1. bundled runtime inside a frozen build
2. a vendored copy shipped with the source tree
3. `site-packages/flet_desktop/app/flet`
4. `%USERPROFILE%/.flet/client/flet-desktop-*/flet`

With that in place, startup is fully offline and reliable.

## Request

- Document the desktop runtime lookup order, and the offline/bundled-runtime
  story, more prominently than it is today.
- Consider preferring an already-cached local shell over a network download by
  default, or expose a documented offline-first switch.

For anyone handing a single `.exe` to someone else, "double-click and it starts
without internet" is a baseline requirement. Right now a first run can fail for
reasons that have nothing to do with the application code.

No project-specific data is included.
