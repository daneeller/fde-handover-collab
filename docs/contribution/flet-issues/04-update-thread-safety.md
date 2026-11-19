#7107 已提交：https://github.com/flet-dev/flet/issues/7107（2026-11-19，状态 OPEN）

# Page.update() thread-safety is undocumented and run_thread() is widely misread as a "back to UI thread" bridge

Follow-up context: #7100, #7101 (merged), #7102, and the docstring rework in #7106.

## Summary

While auditing a desktop app on Flet 0.86.5, I verified from the installed package source that:

1. `page.run_thread(fn)` does **not** run `fn` on the event-loop / UI thread. It does
   `loop.call_soon_threadsafe(loop.run_in_executor, self.executor, ...)` — i.e. `fn`
   runs on an **executor (pool) thread**, with `_context_page` restored for contextvars.
2. `page.update()` → `session.patch_control(...)` executes **synchronously on the
   calling thread**, and `messaging/session.py` contains **no lock at all**
   (no `threading` import, no `Lock`/`RLock` anywhere in the module).

Combined consequence: a pool thread calling `page.update()` races with the event-loop
thread doing the same. Both mutate the session index (`__index` bookkeeping, mount
handling, message send) without synchronization. In practice this surfaces as the
classic "update occasionally does nothing" symptom.

This is easy to get wrong because the name `run_thread` reads as "hand this back to
the UI thread" — a misreading I have seen repeatedly in community code, and one my
own project codified into a lint rule ("UI updates must go through `page.run_thread`")
that *believed* it was fixing the race while it did not. #7106 already reworked the
`run_thread` docstring to say return values are dropped, which helps, but the
thread-safety contract of `update()` itself is still undocumented.

## Is this still true in 1.x?

I checked `main` before filing:

- `Page.update()` → `__update()` → `session.patch_control(c)` — still synchronous on
  the calling thread (`controls/page.py`, `def update` / `__update`).
- The new updates scheduler (`Session.schedule_update` → `__pending_updates` +
  `__updates_scheduler`) exists, but it is only wired to reactive component state
  changes (`__notify`), not to explicit `page.update()` calls.
- `messaging/session.py` on `main` still has no lock.

So explicit `page.update()` from a worker thread remains unserialized in 1.x.

## What I would suggest

Any of these would resolve it, roughly in order of preference:

1. **Document the contract**: `Page.update()` must be called from the event-loop
   thread; from other threads use `page.run_task(...)` (which is implemented via
   `asyncio.run_coroutine_threadsafe` and is safe from any thread). A short section
   in the async-apps cookbook next to the threading table from #7101 would fit well.
2. **Marshal instead of documenting**: make `update()` schedule the patch onto the
   loop (e.g. via the existing updates scheduler) instead of patching inline. This
   would also make the scheduler path the single write path.
3. At minimum, say explicitly in `run_thread()`'s docstring: "handlers run on a
   worker thread; do not call `page.update()` or mutate controls there".

## Repro sketch

```python
def worker():
    while True:
        time.sleep(1)
        page.update()   # runs on executor thread, concurrent with the loop

page.run_thread(worker)
```

With enough event traffic on the loop thread, occasional lost/unapplied updates or
index inconsistencies occur; there is no error, which makes it very hard to debug.

Happy to provide more detail on the 0.86.5 source lines if useful.
