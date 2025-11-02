# Spec: Unified Logging for Python Projects (EARS + stencil code)

**Document Type:** Specification
**Version:** v1.0
**Status:** Draft
**Owner:** Reid Westwood
**Last Updated:** 2025-09-21

## EARS Requirements

### Definitions

* **Anchor logger**: The package-root logger (e.g., `"yourpkg"`), where handlers are attached.
* **Entry name**: A label for the *entry point* (e.g., `cli.train`, `service.api`) that determines the subfolder for logs.
* **Base log directory**: Root folder for logs, from env var `LOG_BASE_DIR`, else `./logs`.

### Functional requirements (EARS)

**Ubiquitous requirements**

* *The system shall* initialize logging via a single function `setup_logging(...)` that is safe to call multiple times (idempotent).
* *The system shall* attach handlers to the **anchor logger** (package root) and keep child loggers handler-free.
* *The system shall* write **every run** to a per-run log file stored under `BaseLogDir / EntryNameAsPath`.
* *The system shall* always attach a **file handler** at level `DEBUG`.
* *The system shall* attach a **console handler** with level controlled by a parameter or `LOG_LEVEL` env var, default `INFO`.
* *The system shall* ensure child loggers created with `logging.getLogger(__name__)` propagate to the anchor logger, so all modules write to the same file.

**Event-driven requirements**

* *When* a user runs any entry point that calls `setup_logging`, *the system shall*:

  * Resolve base log dir from `LOG_BASE_DIR` or default.
  * Create the subdirectory based on `entry_name` with dots → path segments.
  * Create a per-run logfile named `<entry>-YYYYmmdd-HHMMSS.log`.
  * Emit a one-line “Logging initialized” banner with run metadata.
* *When* `setup_logging` is called again in the same process, *the system shall* return without adding duplicate handlers.

**State-driven requirements**

* *While* the console handler level is lower than `ERROR`, *the system shall* print human-oriented console logs (pretty if Rich installed).
* *While* JSON logging is enabled, *the system shall* emit JSON-structured records to the file handler.

**Optional (“where … may …”)**

* *Where* `rich` is installed, *the system may* use `RichHandler` for improved console formatting and tracebacks.
* *Where* `python-json-logger` is installed and JSON logging is enabled, *the system may* format file logs as JSON.
* *Where* multi-processing or high throughput is required, *the system may* provide a `setup_queue_logging(...)` variant using `QueueHandler`/`QueueListener`.

**Scriptability & ergonomics**

* *The system shall* allow runnable modules (`if __name__ == "__main__":`) to call `setup_logging(logger_namespace="yourpkg", entry_name="tools.some_tool")` to produce logs in a matching subfolder.
* *The system shall* accept console level via parameter, CLI, or `LOG_LEVEL`, with precedence: parameter > env > default.
* *The system shall* store resolved `log_dir` and `log_file` on the anchor logger for discovery.

### Non-functional requirements

* **Idempotency**: Multiple calls do not duplicate handlers or create extra files in a single process.
* **Discoverability**: Folder layout must be predictable and human-legible (`/Base/cli/train/...`).
* **Performance**: Logging must not materially degrade throughput; queue-based variant available when needed.
* **Portability**: Works without Rich/JSON libs; degrades gracefully to stdlib formatters.
* **Safety**: Never configure global logging implicitly on import; only inside entry points or explicit calls.

### Acceptance criteria

* Calling `setup_logging("yourpkg", "cli.train")` produces:

  * `BASE/cli/train/cli.train-<timestamp>.log` and console output per `LOG_LEVEL`.
  * Messages from any `logging.getLogger(__name__)` in `yourpkg.*` appear in that same file.
* Running a module directly with a `__main__` guard + `setup_logging("yourpkg","tools.some_tool")` produces logs under `BASE/tools/some_tool/...`.
* Re-invoking `setup_logging(...)` in the same process does not add a second file/console handler.
* Uninstalling `rich`/`python-json-logger` still yields valid text logs.

---

## Python Stencil (drop-in)

> Replace `yourpkg` with your package name. Files shown as paths with contents.

### `yourpkg/__init__.py`

```python
# Avoid “No handler could be found” warnings when imported as a library
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())
```

### `yourpkg/logging_setup.py`

```python
from __future__ import annotations
import logging, logging.config, os, pathlib
from datetime import datetime

try:
    from rich.logging import RichHandler  # pip install rich
    _HAS_RICH = True
except Exception:
    _HAS_RICH = False

try:
    from pythonjsonlogger import jsonlogger  # pip install python-json-logger
    _HAS_JSON = True
except Exception:
    _HAS_JSON = False


def setup_logging(
    logger_namespace: str = "yourpkg",           # where handlers attach
    entry_name: str | None = None,               # subfolder key (dots -> dirs); default = logger_namespace
    base_dir_env: str = "LOG_BASE_DIR",          # env var for root log dir
    default_base_dir: str | os.PathLike = "./logs",
    console_level: str | None = None,            # e.g., "INFO", "DEBUG"; else LOG_LEVEL; default INFO
    json_file: bool = True                       # if True and json logger available, use JSON file logs
) -> dict:
    """
    Idempotent logging initializer.

    - File handler (DEBUG) + Console handler (configurable), attached to `logger_namespace`
    - Base dir from env or default, subfolder from `entry_name` with dots -> directories
    - Per-run file name: <entry>-YYYYmmdd-HHMMSS.log
    - Returns dict with resolved paths
    """
    anchor = logging.getLogger(logger_namespace)

    # Idempotency: detect our managed handlers
    for h in anchor.handlers:
        if getattr(h, "_managed_by_setup_logging", False):
            return {
                "log_dir": getattr(anchor, "_log_dir", None),
                "log_file": getattr(anchor, "_log_file", None),
                "logger_namespace": logger_namespace,
            }

    # Resolve levels and paths
    level_str = (console_level or os.getenv("LOG_LEVEL") or "INFO").upper()
    base_dir = pathlib.Path(os.getenv(base_dir_env, str(default_base_dir))).expanduser().resolve()

    entry = entry_name or logger_namespace
    subpath = pathlib.Path(*entry.split("."))
    log_dir = (base_dir / subpath)
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"{entry}-{run_id}.log"

    # --- File handler (always on) ---
    if json_file and _HAS_JSON:
        formatter_file = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(process)d %(threadName)s",
            rename_fields={"levelname": "level", "asctime": "time"}
        )
    else:
        formatter_file = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter_file)
    fh._managed_by_setup_logging = True  # sentinel

    # --- Console handler ---
    if _HAS_RICH:
        ch = RichHandler(rich_tracebacks=True, show_path=False)
        formatter_console = logging.Formatter("%(message)s")
    else:
        ch = logging.StreamHandler()
        formatter_console = logging.Formatter("%(levelname)s %(name)s - %(message)s")

    ch.setLevel(level_str)
    ch.setFormatter(formatter_console)
    ch._managed_by_setup_logging = True

    # Attach to anchor
    anchor.setLevel(logging.DEBUG)
    anchor.addHandler(fh)
    anchor.addHandler(ch)
    anchor.propagate = False  # avoid double emission if root also has handlers

    # Stash metadata
    anchor._log_dir = str(log_dir)     # type: ignore[attr-defined]
    anchor._log_file = str(log_file)   # type: ignore[attr-defined]

    # Friendly banner
    anchor.info("Logging initialized", extra={"run_id": run_id, "log_file": str(log_file)})

    return {"log_dir": str(log_dir), "log_file": str(log_file), "logger_namespace": logger_namespace}


# Optional: queue-based setup for multiprocessing/high-throughput
def setup_queue_logging(
    logger_namespace: str = "yourpkg",
    entry_name: str | None = None,
    **kwargs
) -> tuple[dict, "logging.handlers.QueueListener"]:
    """
    Sets anchor to a QueueHandler and starts a QueueListener with the same file/console handlers.
    Returns (info_dict, listener). Call listener.stop() on graceful shutdown.
    """
    import queue
    from logging.handlers import QueueHandler, QueueListener

    info = setup_logging(logger_namespace, entry_name, **kwargs)
    anchor = logging.getLogger(logger_namespace)

    # Build final handlers (mirror of setup_logging), then replace anchor handlers with queue
    final_handlers = anchor.handlers[:]  # capture configured handlers
    q = queue.SimpleQueue()
    qh = QueueHandler(q)
    qh._managed_by_setup_logging = True

    # Replace anchor handlers with queue handler
    for h in list(anchor.handlers):
        anchor.removeHandler(h)
    anchor.addHandler(qh)

    listener = QueueListener(q, *final_handlers, respect_handler_level=True)
    listener.start()
    return info, listener
```

### `yourpkg/some_module.py`

```python
import logging
logger = logging.getLogger(__name__)

def do_work():
    logger.debug("starting work in some_module")
    logger.info("doing important stuff")
    logger.warning("just a heads up")
```

### `tools/some_tool.py` (runnable module)

```python
import logging
from yourpkg.logging_setup import setup_logging

logger = logging.getLogger(__name__)

def main():
    logger.info("Tool starting")
    # ... your tool logic ...
    logger.info("Tool done")

if __name__ == "__main__":
    # Choose a friendly entry_name for foldering
    setup_logging(logger_namespace="yourpkg", entry_name="tools.some_tool")
    main()
```

### `scripts/cli.py` (argparse entry point)

```python
import argparse, logging
from yourpkg.logging_setup import setup_logging

log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", default=None, help="DEBUG|INFO|WARNING|ERROR")
    parser.add_argument("--entry", default="cli.main", help="Entry name for log subfolder")
    args = parser.parse_args()

    setup_logging(logger_namespace="yourpkg", entry_name=args.entry, console_level=args.log_level)
    log.info("CLI booted")
    # ... run your app ...

if __name__ == "__main__":
    main()
```

---

## How to use

* **Environment**:

  * `LOG_BASE_DIR=/var/log/myapp`
  * `LOG_LEVEL=DEBUG` (optional)
* **Entry points**:

  * Service: `setup_logging("yourpkg", "service.api")`
  * Trainer: `setup_logging("yourpkg", "cli.train")`
  * Tool: `setup_logging("yourpkg", "tools.some_tool")`

All modules just `logger = logging.getLogger(__name__)`—no handlers.


