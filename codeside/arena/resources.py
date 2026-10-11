"""Read child CPU time (user + kernel), never referee or wall-clock time.

Windows uses a job memory ceiling; Linux uses RLIMIT_AS. These are local
resource guards, not filesystem/network sandboxes. Unsupported hosts fail closed.
"""
import os
import sys

MEMORY_LIMIT = 256 * 1024 * 1024


class ProcessResources:
    def __init__(self, proc, memory_bytes=MEMORY_LIMIT):
        self.proc = proc
        self.job = None
        if sys.platform == "win32":
            import ctypes as c
            from ctypes import wintypes as w
            self.c = c
            self.k = c.WinDLL("kernel32", use_last_error=True)
            self.k.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
            self.k.GetProcessTimes.restype = w.BOOL
            self.k.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
            self.k.CreateJobObjectW.restype = w.HANDLE
            self.k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
            self.k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
            self.k.CloseHandle.argtypes = [w.HANDLE]
            self.k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
            class Basic(c.Structure):
                _fields_ = [("process_time", c.c_longlong), ("job_time", c.c_longlong),
                            ("flags", w.DWORD), ("min_ws", c.c_size_t), ("max_ws", c.c_size_t),
                            ("active", w.DWORD), ("affinity", c.c_size_t),
                            ("priority", w.DWORD), ("scheduling", w.DWORD)]
            class Extended(c.Structure):
                _fields_ = [("basic", Basic), ("io", c.c_ulonglong * 6),
                            ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
                            ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]
            limits = Extended()
            limits.basic.flags = 0x2000 | 0x100 | 0x8  # close kills job; memory; one process
            limits.basic.active = 1
            limits.process_memory = memory_bytes
            self.job = self.k.CreateJobObjectW(None, None)
            if not self.job:
                raise c.WinError(c.get_last_error())
            try:
                if not self.k.SetInformationJobObject(self.job, 9, c.byref(limits), c.sizeof(limits)):
                    raise c.WinError(c.get_last_error())
                if not self.k.AssignProcessToJobObject(self.job, int(proc._handle)):
                    raise c.WinError(c.get_last_error())
            except Exception:
                self.close()
                raise
            self.backend = "GetProcessTimes(user+kernel)"
        elif sys.platform.startswith("linux"):
            import resource
            resource.prlimit(proc.pid, resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            self.hz = os.sysconf("SC_CLK_TCK")
            self.backend = "procfs(utime+stime)"
        else:
            raise RuntimeError("资源计量仅支持 Windows 和 Linux；当前系统不能执行比赛")

    def cpu_ms(self):
        if sys.platform == "win32":
            from ctypes import wintypes as w
            times = [w.FILETIME() for _ in range(4)]
            if not self.k.GetProcessTimes(int(self.proc._handle), *(self.c.byref(t) for t in times)):
                raise self.c.WinError(self.c.get_last_error())
            return sum((t.dwHighDateTime << 32) | t.dwLowDateTime for t in times[2:]) / 10000
        with open(f"/proc/{self.proc.pid}/stat", encoding="ascii") as f:
            return self.linux_cpu_ms(f.read(), self.hz)

    @staticmethod
    def linux_cpu_ms(stat, hz):
        fields = stat.rsplit(")", 1)[1].split()  # field 3 onwards; comm may contain spaces/parentheses
        return (int(fields[11]) + int(fields[12])) * 1000 / hz

    def terminate(self):
        if self.job:
            self.k.TerminateJobObject(self.job, 1)
        else:
            try:
                os.killpg(self.proc.pid, 9)
            except ProcessLookupError:
                pass

    def close(self):
        if self.job:
            self.k.CloseHandle(self.job)
            self.job = None
