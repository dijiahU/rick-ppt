"""fcntl.flock subset that also works on Windows (msvcrt byte-range lock).

On macOS/Linux the real fcntl module is used unchanged. On Windows, flock()
locks the first byte of the lock file; LOCK_SH is treated as exclusive.
"""
import os
import time

try:
    from fcntl import LOCK_EX, LOCK_NB, LOCK_SH, LOCK_UN, flock  # noqa: F401
except ImportError:  # Windows
    import msvcrt

    LOCK_SH, LOCK_EX, LOCK_NB, LOCK_UN = 1, 2, 4, 8

    def flock(target, operation):
        fd = target if isinstance(target, int) else target.fileno()
        position = os.lseek(fd, 0, os.SEEK_CUR)
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if operation & LOCK_UN:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                return
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    if operation & LOCK_NB:
                        raise BlockingIOError('lock is held by another process') from None
                    time.sleep(0.05)
        finally:
            os.lseek(fd, position, os.SEEK_SET)
