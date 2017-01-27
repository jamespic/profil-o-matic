gran_file = 0
gran_method = 1
gran_line = 2

def _lookup_granularity(granularity):
    if granularity == 'file':
        return gran_file
    elif granularity == 'method':
        return gran_method
    elif granularity == 'line':
        return gran_line
    else:
        raise ValueError('Granularity must be file, method, or line')


def generate_stack_trace(frame, granularity, strip_eliot_frames):
    int_granularity = _lookup_granularity(granularity)
    result = []
    while frame is not None:
        items = [frame.f_code.co_filename]
        if int_granularity >= gran_method:
            items.append(frame.f_code.co_name)
        if int_granularity >= gran_line:
            items.append(str(frame.f_lineno))
        instruction = ':'.join(items)
        if strip_eliot_frames:
            f_globals = frame.f_globals
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
