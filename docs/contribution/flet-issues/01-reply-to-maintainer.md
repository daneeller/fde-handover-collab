Thanks - that explanation matches what I see now that I have file logging in place, and I have a
concrete trace that confirms both of your points.

## Packaging

Neither `flet pack` nor `flet build windows`: I use **PyInstaller directly** with a custom `.spec`
and `console=False`. So there is no console attached by default.

However, I do install a `RotatingFileHandler` on the root logger at startup, so anything the `flet`
logger emits does reach a file. In my case "logs lost to stderr" is therefore not the explanation -
the file simply contains no fatal trace, because there is no fatal exception.

## What actually happens

Real sequence from one session (application frames elided, identifiers shortened):

```
2026-11-18 18:01:54 ERROR [concurrent.futures] exception calling callback for
                   <Future at 0x... state=finished raised TypeError>
Traceback (most recent call last):
  File ".../concurrent/futures/_base.py", line 334, in _invoke_callbacks
    callback(self)
  File ".../site-packages/flet/controls/page.py", line 870, in _on_completion
    raise exception
  ... (application frames) ...
TypeError: Container.__init__() got an unexpected keyword argument 'constraints'
2026-11-18 18:02:10 INFO [flet] Session was garbage collected: 5cCM...
```

Two things follow:

1. **The app did not exit.** It kept running for another 16 seconds until the session ended, and a
   new process then started normally. That confirms your point that an exception raised in a
   coroutine started by `page.run_task()` does not terminate the app.
2. **`Session was garbage collected` came after the exception, at INFO level.** In my original report
   I read the end of the log as the cause; it is the symptom of the window/client closing. Your
   explanation is correct.

The exception itself was an application-side bug (a control constructor received a keyword the
0.86.5 widget does not accept), so it is not a Flet defect - but it is a clean example of the
reporting path.

## One difference worth noting

You said Flet logs the exception with its traceback through the `flet` logger at ERROR level. On
0.86.5 what I actually observe is the **`concurrent.futures`** logger, not `flet`, because the
exception is re-raised inside `Page._on_completion` (`controls/page.py:870`), which runs as a
`Future` callback. And as you predicted, `threading.excepthook` never sees it.

Practical consequence: filtering on the `flet` logger misses these entirely - I only found this
trace by grepping for `Traceback`. If `_on_completion` logged through the `flet` logger (or a single
dedicated logger), these would show up next to the rest of the app's errors. Is that something 1.x
changed? If not, I can open a focused issue for the logger attribution rather than mixing it into
this one.

## Answer to your question

The log above is from the first exit after I added file logging, and it shows no fatal trace - the
client process ended normally. So for my case your hypothesis holds: the earlier "silent exit" was
the window/client closing, not an unhandled Python exception.

I will keep file logging on. If a genuinely uncaught exception shows up, I will post the trace here
with the same level of detail. Happy to re-test on 1.x if that would help narrow the
`concurrent.futures` vs `flet` logging question.
