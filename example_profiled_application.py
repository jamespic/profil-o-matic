from __future__ import absolute_import, print_function
import eliot_profiler
import eliot
import datetime
import json
from monotonic import monotonic
from eliot import startAction, Action, FileDestination
from threading import Thread
from urllib2 import urlopen, Request
from wsgiref.simple_server import make_server, WSGIServer
from wsgiref.util import shift_path_info
from SocketServer import ThreadingMixIn
import sys
import time

import pyximport
pyximport.install()
from eliot_profiler.call_graph import _CallGraphRoot
from eliot_profiler.stack_trace import generate_stack_trace


def ping(environ, start_response):
    with startAction(action_type='ping') as action:
        for i in range(200):
            req = Request(
                'http://localhost:8090/pong',
                headers={'X-Eliot-Context': action.serialize_task_id()})
            response = urlopen(req)
            response.read()
            response.close()
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['OK']


def pong(environ, start_response):
    with Action.continueTask(
            task_id=environ['HTTP_X_ELIOT_CONTEXT']) as action:
        time.sleep(0.3)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['OK']


def app(environ, start_response):
    path = shift_path_info(environ)
    if path == 'ping':
        return ping(environ, start_response)
    elif path == 'pong':
        return pong(environ, start_response)
    else:
        start_response('404 Not Found', [])
        return 'Not Found'


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    pass


eliot_profiler.configure(max_overhead=1.0, code_granularity='line')
eliot_profiler.add_destination(FileDestination(open('profile.log', 'w')))
eliot.add_destination(FileDestination(open('app.log', 'w')))

if __name__ == '__main__':
    server = make_server('', 8090, app, server_class=ThreadingWSGIServer)
    server_thread = Thread(target=server.serve_forever, args=[0.1])
    server_thread.start()
    worker_threads = []
    for i in xrange(10):
        worker = Thread(target=urlopen, args=['http://localhost:8090/ping'])
        worker.start()
        worker_threads.append(worker)

    profiler_thread_id = eliot_profiler._instance.thread.ident
    profiler_callgraph = _CallGraphRoot(
        profiler_thread_id,
        'profile',
        datetime.datetime.now() - datetime.timedelta(seconds=monotonic()))

    def profile_profiler():
        before = monotonic()
        while True:
            time.sleep(0.01)
            frame = sys._current_frames()[profiler_thread_id]
            stack = generate_stack_trace(frame, 'line', False)
            after = monotonic()
            profiler_callgraph.ingest(stack, after - before, after)
            before = after

    profiler_profiler_thread = Thread(target=profile_profiler)
    profiler_profiler_thread.setDaemon(True)
    profiler_profiler_thread.start()

    for thread in worker_threads:
        thread.join()
    server.shutdown()
    server_thread.join()
    print('Finished!')
    time.sleep(0.1)

    with open('profiler_callgraph.json', 'w') as f:
        f.write(json.dumps(profiler_callgraph.jsonize(), indent=2))

    print("Samples: {i.total_samples}, Overhead: {i.total_overhead}, Profiled: {i.profiled_tasks}, Unprofiled: {i.unprofiled_tasks}".format(
        i=eliot_profiler._instance))
