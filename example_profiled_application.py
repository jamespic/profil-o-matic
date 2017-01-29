from __future__ import absolute_import, print_function
import eliot_profiler
import eliot_profiler.monkey_patch
import eliot_profiler.monitor
import eliot
import datetime
import json
from eliot_profiler.fast_monotonic import monotonic
from eliot import startAction, Action, FileDestination
from threading import Thread
from prometheus_client.exposition import make_wsgi_app
try:
    from urllib2 import urlopen, Request
except ImportError:
    from urllib.request import urlopen, Request
from wsgiref.simple_server import make_server, WSGIServer
from wsgiref.util import shift_path_info
try:
    from SocketServer import ThreadingMixIn
except ImportError:
    from socketserver import ThreadingMixIn
import sys
import time

try:
    from eliot_profiler._call_graph import CallGraphRoot
    from eliot_profiler._stack_trace import generate_stack_trace
except ImportError:
    from eliot_profiler.call_graph import CallGraphRoot
    from eliot_profiler.stack_trace import generate_stack_trace



def ping(environ, start_response):
    with startAction(action_type='ping') as action:
        for i in range(1000):
            req = Request(
                'http://localhost:8090/pong',
                headers={'X-Eliot-Context': action.serialize_task_id().decode('ascii')})
            response = urlopen(req)
            response.read()
            response.close()
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'OK']


def pong(environ, start_response):
    with Action.continueTask(
            task_id=environ['HTTP_X_ELIOT_CONTEXT'].encode('ascii')) as action:
        time.sleep(0.2)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'OK']


def app(environ, start_response):
    path = shift_path_info(environ)
    if path == 'ping':
        return ping(environ, start_response)
    elif path == 'pong':
        return pong(environ, start_response)
    elif path == 'metrics':
        return make_wsgi_app()(environ, start_response)
    else:
        start_response('404 Not Found', [])
        return 'Not Found'


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

# eliot_profiler.configure(max_overhead=0.05, code_granularity='line', simultaneous_tasks_profiled=15, time_granularity=0.05)


# import socket
# s = socket.socket()
# s.connect(('127.0.0.1', 54637))
# eliot_profiler.add_destination(FileDestination(s.makefile()))

# eliot_profiler.add_destination(FileDestination(open('profile.log', 'wb')))
eliot.add_destination(FileDestination(open('app.log', 'w')))
# eliot_profiler.monkey_patch.patch()
# eliot_profiler.monitor.enable_prometheus()

if __name__ == '__main__':
    server = make_server('', 8090, app, server_class=ThreadingWSGIServer)
    server_thread = Thread(target=server.serve_forever, args=[0.1])
    server_thread.start()
    worker_threads = []
    for i in range(5):
        worker = Thread(target=urlopen, args=['http://localhost:8090/ping'])
        worker.start()
        worker_threads.append(worker)

    # profiler_thread_id = eliot_profiler._instance.thread.ident
    # profiler_callgraph = CallGraphRoot(
    #     profiler_thread_id,
    #     'profile',
    #     datetime.datetime.now() - datetime.timedelta(seconds=monotonic()))
    #
    # def profile_profiler():
    #     before = monotonic()
    #     while True:
    #         time.sleep(0.01)
    #         frame = sys._current_frames()[profiler_thread_id]
    #         stack = generate_stack_trace(frame, 'line', False)
    #         after = monotonic()
    #         profiler_callgraph.ingest(stack, after - before, after)
    #         before = after
    #
    # profiler_profiler_thread = Thread(target=profile_profiler)
    # profiler_profiler_thread.setDaemon(True)
    # profiler_profiler_thread.start()

    for thread in worker_threads:
        thread.join()
    server.shutdown()
    server_thread.join()
    print('Finished!')
    time.sleep(0.1)

    # with open('profiler_callgraph.json', 'w') as f:
    #     f.write(json.dumps(profiler_callgraph.jsonize(), indent=2))

    # import prometheus_client
    # print(prometheus_client.generate_latest())
