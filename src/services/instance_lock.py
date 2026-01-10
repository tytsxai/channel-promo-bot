import errno
import os
from contextlib import suppress

try:
    import fcntl
except ImportError:  # pragma: no cover - fcntl not available on Windows
    fcntl = None  # type: ignore[assignment]


class InstanceLockError(RuntimeError):
    """Raised when instance lock cannot be acquired."""


def acquire_instance_lock(path: str) -> object:
    if fcntl is None:
        raise InstanceLockError("File locking is not supported on this platform")

    lock_dir = os.path.dirname(path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise InstanceLockError("Another instance is already running") from exc
        raise

    try:
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        os.fsync(handle.fileno())
    except Exception:
        # Best effort only; lock is already held.
        pass

    return handle


def release_instance_lock(handle: object | None) -> None:
    if handle is None:
        return
    with suppress(Exception):
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[arg-type]
    with suppress(Exception):
        handle.close()  # type: ignore[call-arg]
