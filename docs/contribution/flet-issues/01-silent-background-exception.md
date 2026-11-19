# Desktop app exits with no diagnostics when a callback or background thread raises

> 已提交：https://github.com/flet-dev/flet/issues/7102 （2026-11-19，状态 OPEN）
> 从 #7100 拆出，独立跟踪。
> 维护者 ndonkoHenri 已回复（2026-11-19）；我方补充证据回复：
> https://github.com/flet-dev/flet/issues/7102#issuecomment-7009674369
> 回复正文归档：[01-reply-to-maintainer.md](./01-reply-to-maintainer.md)

Split out of #7100 so it can be tracked independently.

## Environment

- Flet 0.86.5, Python 3.14, Windows 11
- Packaged as a single desktop executable (no console attached)
- The app uses long-lived background workers and timer-driven UI updates

## Observed behaviour

A packaged build occasionally exited with nothing shown to the user. The last
line in the application log was:

    20:12:12 Session was garbage collected

followed by silence: no `on_disconnect`, no shutdown record, no traceback.
Try/except around individual event handlers did not capture the failure.

## Diagnosis

The exception was raised in a Flet event callback or in a background thread,
outside the code path covered by the application's normal logging. With no
console attached, Python's default handling produced nothing useful.

Installing three hooks at startup made the next failure fully visible:

- `sys.excepthook`
- `threading.excepthook`
- `asyncio.get_running_loop().set_exception_handler(...)`

After that, the next crash produced a complete stack trace in the log. Without
those hooks the failure is effectively invisible, which makes it very hard to
file a useful bug report.

## What would help

The 1.0 cookbook now documents that an un-awaited `page.run_task()` future logs
its exception through Flet. It does not say what happens to exceptions raised in
plain worker threads, or in a callback that is not a coroutine.

Could Flet either:

1. log unhandled callback / thread exceptions to the console log by default in
   desktop mode, or
2. document the recommended global-hook setup as the supported pattern?

A short note in the error-handling docs would already save a lot of blind
debugging. Optionally, emitting a pending-exception summary at session
garbage-collection time would make these silent exits reportable.

No project-specific data is included; the log line above is generic.
