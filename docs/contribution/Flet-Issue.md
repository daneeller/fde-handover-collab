Desktop 0.86.x: silent callback crashes, ambiguous run_thread/run_task semantics, and focus() no-op via run_task
================================================================================================================

> 已提交：https://github.com/flet-dev/flet/issues/7100 （2026-11-19，状态 OPEN）
> 提交前已做脱敏检查：不含项目名、业务场景、架构设计理念或真实源码。

Hi Flet team,

I have been maintaining a Python desktop application on Flet 0.86.5 for several
months. It runs on Windows with Python 3.14, uses background workers, periodic
timers and a system-tray callback, and is also opened in a web session for UI
verification. During that time I hit a handful of runtime and documentation
problems that cost a lot of debugging time. They are collected here as one
feedback issue so the details are not lost. I am happy to split them into
separate issues if that is more useful.

Environment
-----------

- Flet 0.86.5 (pinned), Python 3.14, Windows 11
- Desktop mode via `ft.run` (imperative API), plus a web session used for screenshots
- Packaged with PyInstaller; the tray integration uses pystray

1. Uncaught exceptions in callbacks / background threads terminate the app silently
------------------------------------------------------------------------------------

**Symptom.** A packaged build occasionally exited with no error shown to the
user. The application log ended with:

    20:12:12 Session was garbage collected

and then stopped: no `on_disconnect`, no shutdown record, no cleanup, no
traceback. Plain `try/except` around individual handlers did not catch it.

**Suspected cause.** An unhandled exception raised inside a Flet event callback
or inside a background thread. Neither path reached the application's normal
logging.

**Workaround I had to add.** Three global hooks installed at startup:

- `sys.excepthook`
- `threading.excepthook`
- `asyncio.get_running_loop().set_exception_handler(...)`

After that, the next crash produced a full stack trace in the log. Before that,
the failure was effectively invisible.

**Request.** Could Flet either install a diagnostic exception hook by default in
desktop mode, or document the recommended pattern for capturing exceptions from
event callbacks and user-spawned background threads? A short note in the
"error handling" docs would already help a lot. Logging a pending exception
summary when a session is garbage-collected would also make these failures much
easier to report.

2. `page.run_thread` vs `page.run_task`: the threading contract is easy to misread
---------------------------------------------------------------------------------

**Observation.** A lot of community examples (and code produced by AI assistants)
treat `page.run_thread` as "dispatch back onto the UI/session thread". In my
testing on 0.86.x it behaves the opposite way: it submits the callable to a
background thread pool, and it does **not** guarantee execution in the UI
session context. I also found that `page.update()` does not appear to take a
single global lock, so calling it from arbitrary threads is not safe even though
it often appears to work in small examples.

**Consequence.** Copying the common pattern — calling `page.run_thread` from a
`threading.Timer` callback or from a tray callback and then mutating controls —
can still produce threading bugs. The correct approach seems to be: do work off
the UI thread, then marshal only the UI mutation back to the session via
`page.run_task` (or an equivalent session-aware path).

**Request.** Please document explicitly, in one place:

- which thread `run_thread` executes on,
- which thread `run_task` executes on,
- whether `page.update()` is safe to call outside the session thread,
- the officially recommended pattern for "background work -> UI update".

This is the single most confusing part of the API for a solo developer, because
getting it wrong does not fail loudly — it fails intermittently.

3. `control.focus()` wrapped in `page.run_task` silently does nothing in a web session
---------------------------------------------------------------------------------------

**Repro (simplified).** In an async keyboard event handler of a custom input
widget, advancing focus to the next field:

    # Does not work — no exception, focus just stays where it was:
    page.run_task(lambda: next_field.focus())

    # Works:
    await next_field.focus()

Observed in a web session on 0.86.5. I verified it by adding a `_nav["idx"]`
marker: the index advanced, but the browser focus did not move.

**Request.** If `focus()` is only valid when awaited directly inside the async
handler, that should be documented. If `run_task` is supposed to be a valid
wrapper for control methods, this looks like a bug — it fails silently, which
is the hardest kind to diagnose.

4. First desktop launch on a clean Windows machine tries to download the Flet view shell
-----------------------------------------------------------------------------------------

**Symptom.** On a machine with no cached desktop runtime, startup hung on a
GitHub download and the app never showed a window. To make startup reliable I
had to locate an existing `flet.exe` at the earliest possible moment and set
`FLET_VIEW_PATH` myself, probing the bundled directory, the local vendor copy,
`site-packages`, and `%USERPROFILE%/.flet/client/flet-desktop-*/flet`.

**Request.** Please document the desktop runtime lookup order and the offline /
bundled-runtime story more prominently, and consider preferring an already
cached local shell over a network download by default. For students handing a
single `.exe` to a teacher, "double click and it starts without internet" is a
hard requirement.

5. Painting a splash frame requires an explicit event-loop yield
----------------------------------------------------------------

**Symptom.** With `page.add(splash); page.update()` followed immediately by
several hundred milliseconds of setup work, the splash never appeared — the
window opened with the main UI already in place. It only rendered reliably after
yielding explicitly (a `run_task` with `await asyncio.sleep(0.08)` before the
heavy build).

**Request.** A short note on when `page.update()` actually flushes to the
screen, and whether a "update then yield" helper exists or should exist, would
save a lot of trial and error for cold-start screens.

Summary of suggested improvements
----------------------------------

- Built-in or documented global exception hooks for desktop apps
- One authoritative table of `run_thread` / `run_task` / `page.update()` thread semantics
- Clarify or fix `focus()` when called through `run_task`
- Offline-first desktop runtime discovery, with the lookup order documented
- Clarify frame-flush timing around `page.update()`

I can contribute a short documentation PR covering items 2 and 5 if that would
be useful — those two are pure docs and I already have the notes.

Thanks for the framework. The Python-only UI model made this project possible
for one person; the points above are all about making the last 10% (packaging,
threading, crash diagnostics) less painful.

---

No project-specific or personal data is included in this report; all examples
are generic and were rewritten for this issue.
