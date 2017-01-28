import os

cdef extern from "<time.h>":
    struct timespec:
        long tv_sec
        long tv_nsec

    ctypedef int clockid_t

    int clock_gettime(clockid_t clock_id, timespec* ts)

    clockid_t CLOCK_MONOTONIC_COARSE

cpdef float monotonic():
    cdef timespec ts
    err = clock_gettime(CLOCK_MONOTONIC_COARSE, &ts)
    if err:
        raise OSError(os.strerror(err))
    return ts.tv_sec + ts.tv_nsec / 1000000000.0
