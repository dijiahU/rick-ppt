import builtins
import importlib.util
import sys
import types
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'skills/pptx/scripts/pptx_core/portable_lock.py'


def load_windows_variant(monkeypatch):
    held = set()
    fake = types.SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0)

    def locking(fd, mode, size):
        key = Path(f'/proc/fd/{fd}').name
        if mode == fake.LK_UNLCK:
            held.discard(key)
        elif key in held:
            raise OSError('locked')
        else:
            held.add(key)
    fake.locking = locking
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == 'fcntl':
            raise ImportError(name)
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setitem(sys.modules, 'msvcrt', fake)
    spec = importlib.util.spec_from_file_location('portable_lock_win', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_fallback_locks_and_reports_contention(monkeypatch, tmp_path):
    lock = load_windows_variant(monkeypatch)
    with (tmp_path / '.lock').open('a+') as stream:
        stream.write('x'); stream.flush()
        lock.flock(stream, lock.LOCK_EX)
        with pytest.raises(BlockingIOError):
            lock.flock(stream, lock.LOCK_EX | lock.LOCK_NB)
        lock.flock(stream, lock.LOCK_UN)
        lock.flock(stream.fileno(), lock.LOCK_EX | lock.LOCK_NB)
        assert stream.tell() == 1  # file position is restored


def test_posix_uses_real_fcntl():
    spec = importlib.util.spec_from_file_location('portable_lock_posix', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import fcntl
    assert module.flock is fcntl.flock
