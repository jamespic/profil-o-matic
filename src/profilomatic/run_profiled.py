import argparse
import profilomatic
import profilomatic.monitor
import json
import platform
import runpy
import socket
import sys

from profilomatic.output import file_destination, no_flush_destination


def percentage(s):
    if s.endswith('%'):
        return float(s[:-1]) / 100.0
    else:
        return float(s)


parser = argparse.ArgumentParser(
    description="A low-overhead sampling profiler for Python code, that takes advantage of Eliot to link actions to code"
)
parser.add_argument(
    '-s', '--source-name', default=platform.node(),
    help='The name of the data source - usually hostname or app name')
parser.add_argument(
    '-o', '--output-file', type=argparse.FileType('w'),
    help='A file where profiler output should be sent')
parser.add_argument(
    '--no-flush', action='store_true',
    help='Do not flush profiling data to file after writing - can reduce overhead, but risks data loss'
)
parser.add_argument(
    '-i', '--output-socket', type=str,
    help='A TCP address where profiler output should be sent')
parser.add_argument(
    '-n', '--tasks-profiled', type=int, default=10,
    help='The number of concurrent Eliot tasks that the profiler should aim to profile at once'
)
parser.add_argument(
    '-v', '--max-overhead', type=percentage, default=0.02,
    help='The most performance overhead the profiler is allowed to add, expressed as a fraction or percentage'
)
parser.add_argument(
    '-t', '--time-granularity', type=float, default=0.1,
    help='The time granularity that the profiler should try to acheive in its measurements'
)
parser.add_argument(
    '-c', '--code-granularity', choices=['file', 'method', 'line'], default='line',
    help='The level at which the profiler should measure performance - can be file, method, or line'
)
parser.add_argument(
    '-l', '--all-logs', action='store_true',
    help='Store all logs in profiler call graphs, not just action start and end messages'
)
parser.add_argument(
    '-e', '--eliot', action='store_true',
    help='Monkey patch eliot, to allow profiler to record remote task creation'
)
parser.add_argument(
    '-x', '--monitor', action='store_true',
    help='Expose profiler metric in Prometheus'
)
parser.add_argument(
    '-m', action='store_true',
    help='Run code as Python module'
)
parser.add_argument(
    '--profile-profiler', type=argparse.FileType('w'), metavar='PROFILER_PROFILE_OUTPUT',
    help='Profile the profiler itself, and output the data to the file. Mostly for dev use.'
)
parser.add_argument(
    'target',
    help='The file or module you would like to profile'
)
parser.add_argument(
    'target_args', nargs='*',
    help='Arguments for the application being profiled'
)


args = parser.parse_args()

profilomatic.configure(
    source_name=args.source_name,
    simultaneous_tasks_profiled=args.tasks_profiled,
    max_overhead=args.max_overhead,
    time_granularity=args.time_granularity,
    code_granularity=args.code_granularity,
    store_all_logs=args.all_logs
)

if args.eliot:
    import profilomatic.eliot
    profilomatic.eliot.patch()

if args.monitor:
    profilomatic.monitor.enable_prometheus()

if args.output_file:
    if not args.no_flush:
        profilomatic.add_destination(file_destination(args.output_file))
    else:
        profilomatic.add_destination(no_flush_destination(args.output_file))
if args.output_socket:
    host, port = args.output_socket.split(':')
    port = int(port)
    s = socket.socket()
    s.connect((host, port))
    profilomatic.add_destination(file_destination(s.makefile()))
if not (args.output_socket or args.output_file):
    profilomatic.add_destination(file_destination(sys.stderr))

sys.argv = [args.target] + args.target_args

if args.profile_profiler:
    from .profiler import CallGraphRoot, monotonic, generate_stack_trace
    import time
    import datetime
    import threading
    profiler_thread_id = profilomatic._instance.thread.ident
    profiler_callgraph = CallGraphRoot(
        profiler_thread_id,
        'profile',
        datetime.datetime.now(),
        monotonic())

    def profile_profiler():
        before = monotonic()
        while True:
            time.sleep(0.01)
            frame = sys._current_frames()[profiler_thread_id]
            stack = generate_stack_trace(frame, 'line', False)
            after = monotonic()
            profiler_callgraph.ingest(stack, after - before, after)
            before = after

    profiler_profiler_thread = threading.Thread(target=profile_profiler)
    profiler_profiler_thread.setDaemon(True)
    profiler_profiler_thread.start()

try:
    if args.m:
        runpy.run_module(args.target, run_name='__main__')
    else:
        runpy.run_path(args.target, run_name='__main__')
finally:
    profilomatic._instance.stop()
    if args.profile_profiler:
        args.profile_profiler.write(json.dumps(profiler_callgraph.jsonize(), indent=2))
