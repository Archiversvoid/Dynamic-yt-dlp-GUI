"""One running copy of the app.

Closing the window hides Dynamic in the system tray instead of quitting, so the next launch can bring
that copy back - instantly - instead of starting a second, independent one.

How: the first copy owns a named mutex and a named event (both plain Windows kernel objects, created
by the launcher before anything heavy loads). A later launch finds the mutex taken, signals the event
and exits; a thread in the running copy waits on that event and asks the window to show itself.
Only kernel32 is used - no Qt module, no server - so it behaves the same from a terminal and from a
compiled .exe.
"""
import os
import re
import sys
import time

_MUTEX = None          # kept alive for the life of the process
_EVENT = None
_K32 = None


def instance_key():
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    return "DynamicApp_" + re.sub(r"[^A-Za-z0-9_]", "_", user)


def _k32():
    global _K32
    if _K32 is None:
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        vp, ci, cu = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32
        k.CreateMutexW.restype, k.CreateMutexW.argtypes = vp, [vp, ci, ctypes.c_wchar_p]
        k.CreateEventW.restype, k.CreateEventW.argtypes = vp, [vp, ci, ci, ctypes.c_wchar_p]      # auto-reset, initially not signalled
        k.OpenEventW.restype, k.OpenEventW.argtypes = vp, [cu, ci, ctypes.c_wchar_p]
        k.SetEvent.restype, k.SetEvent.argtypes = ci, [vp]
        k.WaitForSingleObject.restype, k.WaitForSingleObject.argtypes = cu, [vp, cu]
        k.CloseHandle.restype, k.CloseHandle.argtypes = ci, [vp]
        _K32 = k
    return _K32


def _create_mutex():
    """True if this process created the mutex (first copy), False if it already existed."""
    global _MUTEX, _EVENT
    import ctypes
    k = _k32()
    handle = k.CreateMutexW(None, 0, "Local\\" + instance_key())
    if ctypes.get_last_error() == 183:                       # ERROR_ALREADY_EXISTS
        if handle:
            k.CloseHandle(handle)
        return False
    _MUTEX = handle
    _EVENT = k.CreateEventW(None, 0, 0, "Local\\" + instance_key() + "_show")      # created now, so a second launch can signal even while we are still starting
    return True


def _signal_running_instance():
    """Ask the running copy to show itself. True if the signal was delivered."""
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)    # let it take focus: we were just launched by the user
    except Exception:
        pass
    try:
        k = _k32()
        handle = k.OpenEventW(0x0002, 0, "Local\\" + instance_key() + "_show")      # EVENT_MODIFY_STATE
        if not handle:
            return False
        k.SetEvent(handle)
        k.CloseHandle(handle)
        return True
    except Exception:
        return False


def wait_for_wake():
    """Blocks until another launch signals this copy. False = can't wait (no event), so the caller stops."""
    if _EVENT is None:
        return False
    try:
        return _k32().WaitForSingleObject(_EVENT, 0xFFFFFFFF) == 0
    except Exception:
        return False


def claim_or_wake(timeout=10.0, create_mutex=None, signal=None, sleep=time.sleep, clock=time.monotonic):
    """True  -> this process is the main copy: carry on starting.
    False -> a copy was already running and has been asked to show itself: exit now.

    If the other copy exists but can't be reached for `timeout` seconds (it may be hung), start normally
    rather than do nothing."""
    if create_mutex is None:
        if sys.platform != "win32":
            return True
        create_mutex = _create_mutex
    signal = signal or _signal_running_instance
    if create_mutex():
        return True
    deadline = clock() + timeout
    while True:                                              # the other copy may have only just created its event
        if signal():
            return False
        if clock() >= deadline:
            return True
        sleep(0.2)
