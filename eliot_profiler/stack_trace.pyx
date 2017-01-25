from cpython.object cimport PyObject, PyTypeObject, PyObject_TypeCheck

cdef extern from "code.h":
    ctypedef struct PyCodeObject:
        PyObject* co_filename
        PyObject* co_name

cdef extern from "frameobject.h":
    ctypedef struct PyFrameObject:
        PyFrameObject* f_back
        PyCodeObject* f_code
        PyObject* f_globals

    int PyFrame_GetLineNumber(PyFrameObject*)
    PyTypeObject PyFrame_Type


DEF gran_file = 0
DEF gran_method = 1
DEF gran_line = 2
cdef int _lookup_granularity(str granularity):
    if granularity == 'file':
        return gran_file
    elif granularity == 'method':
        return gran_method
    elif granularity == 'line':
        return gran_line
    else:
        raise ValueError('Granularity must be file, method, or line')



cpdef generate_stack_trace(frame_, str granularity, bint strip_eliot_frames):
    cdef PyFrameObject* frame
    cdef str module_name
    if not PyObject_TypeCheck(frame_, &PyFrame_Type):
        raise TypeError('Argument must be stack frame')
    int_granularity = _lookup_granularity(granularity)
    frame = <PyFrameObject*>frame_
    result = []
    while frame != NULL:
        items = [<str>frame.f_code.co_filename]
        if int_granularity >= gran_method:
            items.append(<str>frame.f_code.co_name)
        if int_granularity >= gran_line:
            items.append(str(PyFrame_GetLineNumber(frame)))
        instruction = ':'.join(items)
        if strip_eliot_frames:
            f_globals = <dict>frame.f_globals
            module_name = f_globals['__name__']
            if not (module_name == 'eliot' or module_name.startswith('eliot.')
                    or module_name == 'eliot_profiler' or module_name.startswith('eliot_profiler.')):
                result.append(instruction)
                strip_eliot_frames = False
        else:
            result.append(instruction)
        frame = frame.f_back

    result.reverse()
    return result
