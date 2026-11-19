#7108 已提交：https://github.com/flet-dev/flet/issues/7108（2026-11-19，状态 OPEN）

# Session.schedule_update() is documented as queueable but uses asyncio.Event.set(), which is not thread-safe (1.x)

Found while verifying thread-safety behavior on `main` for a separate report about
`Page.update()` (thread-safety contract).

## Summary

In `sdk/python/packages/flet/src/flet/messaging/session.py` (main):

```python
self.__updates_ready: asyncio.Event = asyncio.Event()   # line ~61
self.__pending_updates: set[BaseControl] = set()        # line ~62

def schedule_update(self, control: BaseControl):
    """
    Queues a control for update by the background scheduler.
    ...
    """
    self.__pending_updates.add(control)
    self.__updates_ready.set()
```

Two problems if `schedule_update()` is called from a non-loop thread (which the
docstring "Queues a control for update by the background scheduler" does not forbid):

1. `asyncio.Event.set()` is explicitly documented as **not thread-safe**; it must be
   called from the thread running the event loop. Calling it from a worker thread
   can fail to wake the loop (the loop is blocked in the selector and never sees the
   internal wakeup), so the scheduler task never drains `__pending_updates` — the
   update is lost until some unrelated event wakes the loop.
2. `set.add()` from a foreign thread races with `__pending_updates.clear()` /
   `list(...)` in `__updates_scheduler` on the loop thread. Each operation is
   GIL-atomic, but the *sequence* (add → clear → add) can interleave so the newly
   added control is cleared before being processed.

Currently `schedule_update` is only called from reactive component notification
paths on the loop thread, so this is latent rather than live — but the method is
public and its docstring invites exactly this use, especially given that
`page.update()` has no documented thread requirement (see my other report).

## Suggestion

Either:

- make it thread-safe: `loop.call_soon_threadsafe(self.__updates_ready.set)` (and
  note that `set.add` + `Event` wake ordering still needs care — a small
  `threading.Lock` around add/set is the cheap fix), or
- document that `schedule_update()` must only be called from the event-loop thread.

## Environment

- Observed on `main` branch source (flet-dev/flet, messaging/session.py).
- Not version-specific to any release I run; filing against 1.x line.
