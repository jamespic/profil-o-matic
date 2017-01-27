import sys
from six import exec_


def wrap_function(module, name, line, f):
    fake_globals = dict(globals())
    f_name = f.__name__
    fake_globals[f_name] = f
    fake_globals['__name__'] = module
    code = compile(
        '\n' * (line - 2)
        + """def {name}():
                return {f_name}()
        """.format(name=name, f_name=f_name),
        module.replace('.', '/') + '.py',
        'exec'
    )
    exec_(code, fake_globals)
    return fake_globals[name]


def make_frame(*args):
    f = sys._getframe
    for module, name, line in reversed(args):
        f = wrap_function(module, name, line, f)
    return f()


test_frame = make_frame(
    ('__main__', 'main', 5),
    ('framework.module', 'run', 6),
    ('eliot', 'initialise', 7),
    ('mylogger', 'dostuff', 10),
    ('eliot_profiler', 'profile', 12),
    ('eliot_profiler.profile', 'loop', 14),
    ('eliot._output', 'write', 16),
    ('eliot', 'log', 16),
)


class BaseStackTraceTest(object):
    def test_stack_trace_line(self):
        trace = self.stack_trace_fn(test_frame, 'line', False)
        self.assertEqual(
            [
                "__main__.py:main:5",
                "framework/module.py:run:6",
                "eliot.py:initialise:7",
                "mylogger.py:dostuff:10",
                "eliot_profiler.py:profile:12",
                "eliot_profiler/profile.py:loop:14",
                "eliot/_output.py:write:16",
                "eliot.py:log:16"
            ],
            trace[-8:]
        )

    def test_stack_trace_method(self):
        trace = self.stack_trace_fn(test_frame, 'method', False)
        self.assertEqual(
            [
                "__main__.py:main",
                "framework/module.py:run",
                "eliot.py:initialise",
                "mylogger.py:dostuff",
                "eliot_profiler.py:profile",
                "eliot_profiler/profile.py:loop",
                "eliot/_output.py:write",
                "eliot.py:log"
            ],
            trace[-8:]
        )

    def test_stack_trace_file(self):
        trace = self.stack_trace_fn(test_frame, 'file', False)
        self.assertEqual(
            [
                "__main__.py",
                "framework/module.py",
                "eliot.py",
                "mylogger.py",
                "eliot_profiler.py",
                "eliot_profiler/profile.py",
                "eliot/_output.py",
                "eliot.py"
            ],
            trace[-8:]
        )

    def test_stack_trace_strip(self):
        trace = self.stack_trace_fn(test_frame, 'line', True)
        self.assertEqual(
            [
                "__main__.py:main:5",
                "framework/module.py:run:6",
                "eliot.py:initialise:7",
                "mylogger.py:dostuff:10",
            ],
            trace[-4:]
        )
