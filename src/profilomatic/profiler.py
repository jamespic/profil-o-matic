import datetime
import platform
import six
import sys
import threading
import time
import traceback
from collections import deque

try:
    from ._call_graph import CallGraphRoot
    from ._stack_trace import generate_stack_trace
except ImportError:
    from .call_graph import CallGraphRoot
    from .stack_trace import generate_stack_trace

try:
    from fast_monotonic import monotonic
    monotonic()  # Check it actually works
except (ImportError, OSError):
    from monotonic import monotonic
try:
    utc = datetime.timezone.utc
except AttributeError:
    import pytz
    utc = pytz.utc

ACTION_STATUS_FIELD = 'action_status'
ACTION_TYPE_FIELD = 'action_type'
TASK_UUID_FIELD = 'task_uuid'
TASK_LEVEL_FIELD = 'task_level'

REMOTE_TASK_ACTION = 'profilomatic:linked_remote_task'

STARTED_STATUS = 'started'
SUCCEEDED_STATUS = 'succeeded'
FAILED_STATUS = 'failed'

_PROFILER_DEFAULTS = {
    'simultaneous_tasks_profiled': 10,
    'max_overhead': 0.02,  # fraction
    'time_granularity': 0.1,  # seconds
    'code_granularity': 'line',  # line, method, or file
    'store_all_logs': False,
    'source_name': platform.node()
}


class _MessageInfo(object):
    def __init__(self, message, next_task_uuid):
        self.message = message
        self.next_task_uuid = next_task_uuid
        self.thread = threading.currentThread().ident
        self.clock = datetime.datetime.utcnow().replace(tzinfo=utc)
        self.monotonic = monotonic()

        _, _, tb = sys.exc_info()
        if tb is not None:
            while tb.tb_next is not None:
                tb = tb.tb_next
            self.frame = tb.tb_frame
        else:
            self.frame = sys._getframe()


class Profiler(object):
    __slots__ = [
        'simultaneous_tasks_profiled', 'max_overhead', 'time_granularity',
        'code_granularity', 'source_name', 'store_all_logs',
        'actions_since_last_run', 'actions_next_run', 'message_queue',
        'action_context', 'destinations', 'thread_tasks', 'call_graphs',
        'thread', 'total_overhead', 'granularity_sum', 'total_samples',
        'profiled_tasks', 'unprofiled_tasks', 'stopped']
    def __init__(self, **kwargs):
        self.configure(**kwargs)
        self.actions_since_last_run = 0
        self.actions_next_run = self.simultaneous_tasks_profiled
        self.message_queue = deque()
        self.action_context = threading.local()
        self.destinations = []
        self.thread_tasks = {}
        self.call_graphs = {}
        self.thread = None
        self.total_overhead = 0.0
        self.granularity_sum = 0.0
        self.total_samples = 0
        self.profiled_tasks = 0
        self.unprofiled_tasks = 0
        self.stopped = False

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
            if self.simultaneous_tasks_profiled == 0 or (
                    len(self.thread_tasks) + self.actions_since_last_run
                        < self.actions_next_run):
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
        frames = sys._current_frames()
        for thread, task in six.iteritems(self.thread_tasks):
            try:
                frame = frames[thread]
                call_graph = self.call_graphs[(thread, task)]
                call_stack = generate_stack_trace(frame, self.code_granularity, False)
                call_graph.ingest(call_stack, time_to_record, monotime)
            except KeyError:
                pass  # No frame, no biggie
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
            if self.stopped:
                return
            self._profile_stacks(time_to_record, monotonic())
            end_time = monotonic()
            time_taken = end_time - start_time
            # How did the time taken compare with the target
            performance_against_target = (
                time_taken / (self.time_granularity * self.max_overhead)
            ) or 1.0
            if performance_against_target <= 1:
                # Performance was good, so maybe profile more actions
                self.actions_next_run += (
                    self.simultaneous_tasks_profiled
                    * (1.0 - performance_against_target)
                )
                wait_time = self.time_granularity - time_taken
            else:
                # Performance wasn't so good, so wait longer, reducing granularity
                self.actions_next_run = self.simultaneous_tasks_profiled
                wait_time = time_taken / self.max_overhead - time_taken
            last_start_time = start_time
            self.total_overhead += time_taken
            self.granularity_sum += time_to_record
            self.total_samples += 1

    def start(self):
        if self.thread:
            return
        self.stopped = False
        self.thread = threading.Thread(
            target=self._profiler_loop, name='Profilomatic Thread')
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        if self.thread:
            self.stopped = True
            self.thread.join()
            self.thread = None


    def current_task_uuid(self):
        try:
            return self.action_context.stack[-1]
        except:
            return None


    def _ingest_message(self, message):
        thread = message.thread
        task = message.message[TASK_UUID_FIELD]
        call_graph = self.call_graphs.get((thread, task))
        if not call_graph:
            call_graph = CallGraphRoot(
                thread,
                task,
                message.clock,
                message.monotonic)
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
        jsonized['source'] = self.source_name
        for destination in self.destinations:
            try:
                destination(jsonized)
            except:
                traceback.print_exc()  # Can we do better?
