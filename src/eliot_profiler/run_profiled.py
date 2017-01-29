import argparse
import eliot
import eliot_profiler
import eliot_profiler.monkey_patch
import eliot_profiler.monitor
import json
import runpy
import socket
import sys

def percentage(s):
    if s.endswith('%'):
        return float(s[:-1]) / 100.0
    else:
        return float(s)

parser = argparse.ArgumentParser(
    description="A low-overhead sampling profiler for Python code, that takes advantage of Eliot to link actions to code"
)
parser.add_argument(
    '-o', '--output-file', type=argparse.FileType('w'),
    help='A file where profiler output should be sent')
parser.add_argument(
    '--no-flush', action='store_true',
    help='Do not flush profiling data to file after writing - can reduce overhead, but risks data loss'
)
parser.add_argument(
    '-s', '--output-socket', type=str,
    help='A TCP address where profiler output should be sent')
parser.add_argument(
    '-n', '--tasks-profiled', type=int, default=10,
    help='The number of concurrent Eliot tasks that the profiler should aim to profile at once'
)
parser.add_argument(
    '-p', '--max-overhead', type=percentage, default=0.02,
    help='The most performance overhead the profiler is allowed to add, expressed as a fraction or percentage'
)
parser.add_argument(
    '-t', '--time-granularity', type=float, default=0.1,
    help='The time granularity that the profiler should try to acheive in its measurements'
)
parser.add_argument(
    '-c', '--code-granularity', choices=['file', 'method', 'line'], default='method',
    help='The level at which the profiler should measure performance - can be file, method, or line'
)
parser.add_argument(
    '-l', '--all-logs', action='store_true',
    help='Store all logs in profiler call graphs, not just action start and end messages'
)
parser.add_argument(
    '-r', '--monkey-patch', action='store_true',
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
    'target',
    help='The file or module you would like to profile'
)
parser.add_argument(
    'target_args', nargs='*',
    help='Arguments for the application being profiled'
)

args = parser.parse_args()

eliot_profiler.configure(
    simultaneous_tasks_profiled=args.tasks_profiled,
    max_overhead=args.max_overhead,
    time_granularity=args.time_granularity,
    code_granularity=args.code_granularity,
    store_all_logs=args.all_logs
)

if args.monkey_patch:
    eliot_profiler.monkey_patch.patch()

if args.monitor:
    eliot_profiler.monitor.enable_prometheus()

if args.output_file:
    if not args.no_flush:
        eliot_profiler.add_destination(eliot.FileDestination(args.output_file))
    else:
        f = args.output_file
        def write_no_flush(message):
            f.write(json.dumps(message) + '\n')
        eliot_profiler.add_destination(write_no_flush)
if args.output_socket:
    host, port = args.output_socket.split(':')
    port = int(port)
    s = socket.socket()
    s.connect((host, port))
    eliot_profiler.add_destination(eliot.FileDestination(s.makefile()))
if not (args.output_socket or args.output_file):
    eliot_profiler.add_destination(eliot.FileDestination(sys.stderr))

sys.argv = [args.target] + args.target_args
print 'Running', sys.argv
if args.m:
    runpy.run_module(args.target, run_name='__main__')
else:
    runpy.run_path(args.target, run_name='__main__')
