"""Opt-in AC-only queue execution; no credentials and no model calls."""
import os
import subprocess
import threading


def enabled(environ=None):
    return (os.environ if environ is None else environ).get('PPTX_WORKER_AC_ONLY') == '1'


def keep_awake(pid=None, popen=None):
    """macOS: hold an idle-sleep assertion for this worker's lifetime.

    Used when the worker may run on battery. `caffeinate -i -w PID` exits by
    itself when the worker exits; closing the lid still sleeps the Mac.
    """
    if not os.path.exists('/usr/bin/caffeinate'):
        return None
    try:
        return (subprocess.Popen if popen is None else popen)(
            ['/usr/bin/caffeinate', '-i', '-w', str(pid or os.getpid())],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None


def power_source(run=None):
    try:
        result = (subprocess.run if run is None else run)(
            ['/usr/bin/pmset', '-g', 'batt'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            # Charging percentage is not the power source (100% may be on AC).
            first = result.stdout.splitlines()[0] if result.stdout else ''
            if "'AC Power'" in first:
                return 'ac'
            if "'Battery Power'" in first:
                return 'battery'
    except (OSError, subprocess.TimeoutExpired):
        pass
    return 'unknown'


def may_start():
    return not enabled() or power_source() == 'ac'


def watch(stop, interrupt, *, source=power_source, interval=5):
    """Interrupt at existing lease checkpoints, never kill model processes here."""
    def loop():
        while not stop.is_set():
            if source() != 'ac':
                interrupt.set()
                stop.set()
                return
            stop.wait(interval)
    thread = threading.Thread(target=loop, name='pptx-ac-power', daemon=True)
    thread.start()
    return thread
