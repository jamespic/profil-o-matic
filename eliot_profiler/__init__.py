import datetime
import re
import sys
import threading
import time
import traceback
from collections import deque

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


class _CallGraphRoot(object):
    __slots__ = [
        'thread', 'task_uuid', 'wallclock_minus_monotonic', 'children'
    ]

    def __init__(self, thread, task_uuid, wallclock_minus_monotonic):
        self.thread = thread
        self.task_uuid = task_uuid
        self.wallclock_minus_monotonic = wallclock_minus_monotonic
        self.children = []

    def ingest(self, call_stack, time, monotime, message=None):
        children = self.children
        for instruction_pointer in call_stack:
            for child in children:
                if child.instruction_pointer == instruction_pointer:
                    node = child
                    node.time += time
                    if monotime < node.min_monotonic:
                        node.min_monotonic = monotime
                    if monotime > node.max_monotonic:
                        node.max_monotonic = monotime
                    break
            else:
                node = _CallGraphNode(instruction_pointer, time, 0.0, monotime,
                                      monotime, None)
                children.append(node)
            children = node.current_children
        # Do extra steps that only apply to leaf node
        node.self_time += time
        if message:
            children.append(_MessageNode(monotime, message))
            node.archived_children.extend(node.current_children)
            node.current_children = []

    def jsonize(self):
        return {
            'thread': self.thread,
            'task_uuid': self.task_uuid,
            'children': [
                node.jsonize(self.wallclock_minus_monotonic)
                for node in self.children
            ]
        }


class _CallGraphNode(object):
    __slots__ = [
        'instruction_pointer', 'time', 'self_time', 'message', 'min_monotonic',
        'max_monotonic', 'archived_children', 'current_children'
    ]

    def __init__(self,
                 instruction_pointer,
                 time=0.0,
                 self_time=0.0,
                 min_monotonic=None,
                 max_monotonic=None,
                 message=None):
        self.instruction_pointer = instruction_pointer
        self.time = time
        self.self_time = self_time
        self.message = message
        self.min_monotonic = min_monotonic
        self.max_monotonic = max_monotonic
        self.archived_children = []
        self.current_children = []

    def jsonize(self, wall_clock_minus_monotonic):
        msg = {
            'instruction': self.instruction_pointer,
            'time': self.time,
            'self_time': self.self_time,
            'start_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.min_monotonic)).isoformat(),
            'end_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.max_monotonic)).isoformat()
        }
        if self.archived_children or self.current_children:
            msg['children'] = [
                node.jsonize(wall_clock_minus_monotonic)
                for node in self.archived_children + self.current_children
            ]
        return msg


class _MessageNode(object):
    __slots__ = ['monotime', 'message']

    def __init__(self, monotime, message):
        self.monotime = monotime
        self.message = message

    def jsonize(self, wall_clock_minus_monotonic):
        return {
            'message_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.monotime)).isoformat(),
            'message': self.message
        }


_eliot_package_re = re.compile(r'^eliot(?:_profiler)?(?:\.|$)')


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
            call_stack = self._generate_stack_trace(frame, False)
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
        call_stack = self._generate_stack_trace(message.frame, True)
        call_graph.ingest(call_stack, 0.0, message.monotonic, message.message)
        next_task_uuid = message.next_task_uuid
        if next_task_uuid is None:
            self._emit(call_graph)
            del self.thread_tasks[message.thread]
            del self.call_graphs[(thread, task)]
        else:
            self.thread_tasks[message.thread] = next_task_uuid

    def _generate_stack_trace(self, frame, strip_eliot_frames=False):
        result = []
        while frame is not None:
            if self.code_granularity == 'line':
                instruction = (
                    "{f.f_code.co_filename}:{f.f_code.co_name}:{f.f_lineno}"
                    .format(f=frame))
            elif self.code_granularity == 'method':
                instruction = ("{f.f_code.co_filename}:{f.f_code.co_name}"
                               .format(f=frame))
            else:
                instruction = frame.f_code.co_filename
            if strip_eliot_frames:
                if not _eliot_package_re.search(frame.f_globals['__name__']):
                    # Stop stripping at first non-eliot frame
                    result.append(instruction)
                    strip_eliot_frames = False
            else:
                result.append(instruction)
            frame = frame.f_back
        result.reverse()
        return result

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
