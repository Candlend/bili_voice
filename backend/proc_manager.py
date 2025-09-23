import subprocess
from typing import Optional, List


_tracked_procs: List[subprocess.Popen] = []

# ---------------- Public API ----------------

def start_process(cmd: list[str], cwd: Optional[str] = None) -> subprocess.Popen:
    """
    Start an external process and attach it to a Windows Job Object so it will be
    terminated automatically when the parent exits. On non-Windows, it just starts normally.
    """
    proc = subprocess.Popen(cmd, cwd=cwd)
    _tracked_procs.append(proc)
    return proc


def cleanup_process(proc: Optional[subprocess.Popen]):
    """
    Gracefully terminate a process, escalating to kill if needed.
    """
    if not proc:
        return
    try:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    finally:
        try:
            if proc in _tracked_procs:
                _tracked_procs.remove(proc)
        except Exception:
            pass


def cleanup_all():
    """
    Cleanup all tracked processes.
    """
    for p in list(_tracked_procs):
        try:
            cleanup_process(p)
        except Exception:
            pass
