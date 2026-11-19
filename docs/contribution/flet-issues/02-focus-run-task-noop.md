# control.focus() wrapped in page.run_task() silently does nothing in a web session

> 已提交：https://github.com/flet-dev/flet/issues/7103 （2026-11-19，状态 OPEN）
> 从 #7100 拆出，独立跟踪。

Split out of #7100 so it can be tracked independently.

## Environment

- Flet 0.86.5, Python 3.14
- Web session used for UI verification; desktop mode also available

## Repro (minimal, generic)

In an async keyboard handler for a custom field group, move focus to the next
field on Space:

```python
# Inside an async keyboard event handler:
try:
    # This silently does nothing in a web session - no exception, no log,
    # focus simply stays on the current field:
    page.run_task(lambda: next_field.focus())

    # This works:
    # await next_field.focus()
except Exception:
    logger.debug("focus failed", exc_info=True)
```

The exception handler never fired. A side-channel marker confirmed the handler
itself ran; only the focus transfer was lost.

Calling `await next_field.focus()` directly in the async handler worked
immediately, in the same session.

## Expected

Either:

- `page.run_task()` is a valid wrapper for control methods, in which case
  `focus()` should take effect (or raise a catchable error), or
- it is not valid for methods that need the session/async context, in which case
  the docs should say that focus-related calls must be awaited directly.

The silent no-op is the costly part: there is no signal that the call was
dropped.

## Question for maintainers

Does 1.0 still show this behaviour? I pinned 0.86.5 and have not verified main.
If it is already fixed, a changelog note would still help people on pinned
versions. If not, I am happy to turn the snippet above into a fully runnable
minimal app.

No project-specific data is included; names are generic.
