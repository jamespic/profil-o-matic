import os

from posix.time cimport timespec, clock_gettime, CLOCK_MONOTONIC_COARSE

cpdef float monotonic():
    cdef timespec ts
    err = clock_gettime(CLOCK_MONOTONIC_COARSE, &ts)
    if err:
        raise OSError(os.strerror(err))
    return ts.tv_sec + ts.tv_nsec / 1000000000.0
