import datetime
import re
import sys
import threading
import time
import traceback
from collections import deque, OrderedDict

import pyximport
pyximport.install()
from .call_graph import _CallGraphRoot, _CallGraphNode, _MessageNode
from .stack_trace import generate_stack_trace

import eliot
from eliot._action import \
    ACTION_STATUS_FIELD, \
    STARTED_STATUS, \
    SUCCEEDED_STATUS, \
    FAILED_STATUS, \
    TASK_UUID_FIELD

from monotonic import monotonic
import pytz

_PROFILER_DEFAULTS = {
    'max_actions_per_run': 10,
    'max_overhead': 0.02,  # fraction
    'time_granularity': 0.01,  # seconds
    'code_granularity': 'method',  # line, method, or file
    'store_all_logs': False
}


class _MessageInfo(object):
    def __init__(self, message, next_task_uuid):
        self.message = message
        self.next_task_uuid = next_task_uuid
        self.frame = sys._getframe()
        self.thread = threading.currentThread().ident
        self.clock = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        self.monotonic = monotonic()


class _Profiler(object):
    def __init__(self, **kwargs):
        self.configure(**kwargs)
        self.actions_since_last_run = 0
        self.message_queue = deque()
        self.action_context = threading.local()
        self.destinations = []
        self.thread_tasks = {}
        self.call_graphs = {}
        self.thread = None
        self.total_overhead = 0.0
        self.total_samples = 0
        self.profiled_tasks = 0
        self.unprofiled_tasks = 0

    def configure(self, **kwargs):
        for arg in _PROFILER_DEFAULTS.keys():
            if arg in kwargs:
                setattr(self, arg, kwargs[arg])
            elif not hasattr(self, arg):
                setattr(self, arg, _PROFILER_DEFAULTS[arg])

    def add_destination(self, destination):
        self.destinations.append(destination)

    def remove_destination(self, destination):
        self.destinations.remove(destination)

    def handle_message(self, message):
        status = message.get(ACTION_STATUS_FIELD)
        if status == STARTED_STATUS:
            self._start_message(message)
        elif status in (SUCCEEDED_STATUS, FAILED_STATUS):
            self._end_message(message)
        elif self.store_all_logs:
            self._log_message(message)

    def _start_message(self, message):
        context = self.action_context
        if not hasattr(context, 'stack'):
            context.stack = []
            # This is racy, but it's not a disaster
            # if a small number of extra actions are profiled
            if self.actions_since_last_run < self.max_actions_per_run:
                self.actions_since_last_run += 1
                context.logging = True
                self.profiled_tasks += 1
            else:
                context.logging = False
                self.unprofiled_tasks += 1
        context.stack.append(message[TASK_UUID_FIELD])
        self._log_message(message)

    def _end_message(self, message):
        context = self.action_context
        context.stack.pop()
        self._log_message(message)
        if not context.stack:  # Stack is empty, so revert to actionless state
            del context.stack
            del context.logging

    def _log_message(self, message):
        context = self.action_context
        if getattr(context, 'logging', False):
            stack = getattr(context, 'stack', None)
            if stack:
                task_uuid = stack[-1]
            else:
                task_uuid = None
            msg_info = _MessageInfo(message, task_uuid)
            self.message_queue.append(msg_info)

    def _ingest_messages(self):
        try:
            while True:
                message = self.message_queue.popleft()
                self._ingest_message(message)
        except IndexError:
            pass

    def _profile_stacks(self, time_to_record, monotime):
        for thread, frame in self._current_frames().items():
            task = self.thread_tasks.get(thread)
            if not task:
                continue
            call_graph = self.call_graphs[(thread, task)]
            call_stack = generate_stack_trace(frame, self.code_granularity, False)
            call_graph.ingest(call_stack, time_to_record, monotime)
        self.actions_since_last_run = 0

    def _profile_once(self, time_to_record, monotime):
        """
        Added for testing - in use, it would be important for monotime to be generated between ingesting and profiling
        """
        self._ingest_messages()
        self._profile_stacks(time_to_record, monotime)

    def _profiler_loop(self):
        wait_time = self.time_granularity
        last_start_time = monotonic()
        while True:
            time.sleep(wait_time)
            start_time = monotonic()
            time_to_record = start_time - last_start_time
            self._ingest_messages()
            self._profile_stacks(time_to_record, monotonic())
            end_time = monotonic()
            time_taken = end_time - start_time
            wait_time = max(self.time_granularity, time_taken /
                            self.max_overhead) - time_taken
            last_start_time = start_time
            self.total_overhead += time_taken
            self.total_samples += 1

    def start(self):
        if self.thread:
            return
        eliot.add_destination(self.handle_message)
        self.thread = threading.Thread(
            target=self._profiler_loop, name='Eliot Profiler Thread')
        self.thread.setDaemon(True)
        self.thread.start()

    def _current_frames(self):
        return sys._current_frames()

    def _ingest_message(self, message):
        thread = message.thread
        task = message.message[TASK_UUID_FIELD]
        call_graph = self.call_graphs.get((thread, task))
        if not call_graph:
            call_graph = _CallGraphRoot(
                thread,
                task,
                message.clock - datetime.timedelta(seconds=message.monotonic))
            self.call_graphs[(thread, task)] = call_graph
        call_stack = generate_stack_trace(message.frame, self.code_granularity, True)
        call_graph.ingest(call_stack, 0.0, message.monotonic, message.message)
        next_task_uuid = message.next_task_uuid
        if next_task_uuid is None:
            self._emit(call_graph)
            del self.thread_tasks[message.thread]
            del self.call_graphs[(thread, task)]
        else:
            self.thread_tasks[message.thread] = next_task_uuid

    def _emit(self, message):
        jsonized = message.jsonize()
        for destination in self.destinations:
            try:
                destination(jsonized)
            except:
                traceback.print_exc()  # Can we do better?


_instance = _Profiler()
configure = _instance.configure
remove_destination = _instance.remove_destination


def add_destination(destination):
    _instance.start()
    _instance.add_destination(destination)
