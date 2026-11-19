#7109 已提交：https://github.com/flet-dev/flet/issues/7109（2026-11-19，状态 OPEN）

# Exceptions in run_task() background tasks are logged under the concurrent.futures logger, not the flet logger (0.86.x; follow-up to #7102)

Follow-up to #7102 (unhandled exceptions in callbacks / background threads). This is
the one remaining finding from that thread I could pin down precisely with logs.

## What happens

In 0.86.5, `Page.run_task()` schedules via `asyncio.run_coroutine_threadsafe(...)` and
attaches `_on_completion` to the returned concurrent.futures.Future:

```python
# flet/controls/page.py (0.86.5)
def _on_completion(f):
    try:
        exception = f.exception()
        if exception:
            raise exception
    except CancelledError:
        ...
```

When nobody awaits the future, that re-raised exception happens inside the Future's
**done-callback**, i.e. inside `concurrent.futures`. Python's executor machinery
catches it and logs it through its *own* logger:

```
ERROR [concurrent.futures] exception calling callback for <Future at 0x... exception=TypeError(...)>
  File "concurrent/futures/_base.py", line 334, in _invoke_callbacks
  File "flet/controls/page.py", line 870, in _on_completion
    raise exception
  ... (application frames) ...
TypeError: ...
```

(Real log from a packaged desktop app, verified today.)

## Consequence

The exception is recorded under the `concurrent.futures` logger, **not** `flet`.
Any app that configures handlers/levels per logger — e.g.
`logging.getLogger("flet").setLevel(WARNING)` or filtering by logger name — will
not see these errors at all. In my case a `flet`-only log channel showed nothing
while the full-stack file log caught it, which is why it took a while to find.

## Suggestion

In `_on_completion`, instead of relying on the executor's fallback logging of
done-callback exceptions, catch the exception explicitly and pass it through Flet's
own reporting path (e.g. `logger.exception(...)` on the `flet` logger, or
`page.error(...)`), mirroring what happens for handler exceptions.

Pseudo-diff:

```python
def _on_completion(f):
    try:
        exception = f.exception()
        if exception:
            raise exception
    except CancelledError:
        ...
    except Exception:
        logger.exception("Unhandled exception in background task started by run_task()")
```

I don't have a 1.x checkout running to confirm whether the same pattern exists
there; if the completion-callback design changed, feel free to close this as
already addressed.
