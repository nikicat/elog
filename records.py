import sys
import logging

try:
    import cffi
except ImportError:
    cffi = None


##### Private objects #####
_linux_syscall_lib = None


##### Public classes #####
class LogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self.tid = _gettid()


##### Private methods #####
def _gettid():
    if sys.platform.startswith("linux") and cffi is not None:
        return _linux_gettid()
    else:
        return None

def _linux_gettid():
    global _linux_syscall_lib
    if _linux_syscall_lib is None:
        ffi = cffi.FFI()
        ffi.cdef("int syscall(int number);")
        lib = ffi.verify("""
                #include <unistd.h>
                #include <sys/syscall.h>
            """)
        _linux_syscall_lib = lib
    # 186 - Linux-specific syscall gettid()
    tid = _linux_syscall_lib.syscall(186) # pylint: disable=E1101
    return tid

