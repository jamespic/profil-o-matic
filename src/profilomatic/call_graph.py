import datetime

class _CallGraphNode(object):
    __slots__ = [
        "instruction_pointer",
        "time",
        "self_time",
        "min_monotonic",
        "max_monotonic",
        "archived_children",
        "current_children",
        "message"
    ]


    def __init__(self,
                 instruction_pointer,
                 time,
                 self_time,
                 min_monotonic,
                 max_monotonic):
        self.instruction_pointer = instruction_pointer
        self.time = time
        self.self_time = self_time
        self.min_monotonic = min_monotonic
        self.max_monotonic = max_monotonic
        self.archived_children = []
        self.current_children = []
        self.message = None

    def add_time(self, time, monotime):
        self.time += time
        if monotime < self.min_monotonic:
            self.min_monotonic = monotime
        if monotime > self.max_monotonic:
            self.max_monotonic = monotime

    def _jsonize(self, wall_clock_minus_monotonic):
        msg = {
            'time': self.time,
            'self_time': self.self_time,
            'start_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.min_monotonic)).isoformat(),
            'end_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.max_monotonic)).isoformat()
        }
        if self.archived_children or self.current_children:
            msg['children'] = [
                node._jsonize(wall_clock_minus_monotonic)
                for node in self.archived_children + self.current_children
            ]
        if self.instruction_pointer is not None:
            msg['instruction'] = self.instruction_pointer
        if self.message is not None:
            msg['message'] = self.message
        return msg


class CallGraphRoot(_CallGraphNode):
    __slots__ = [
        "thread",
        "task_uuid",
        "wall_clock_minus_monotonic"
    ]

    def __init__(self, thread, task_uuid, start_time, start_monotonic):
        _CallGraphNode.__init__(self, None, 0.0, 0.0, start_monotonic, start_monotonic)
        self.thread = thread
        self.task_uuid = task_uuid
        self.wall_clock_minus_monotonic = (
            start_time - datetime.timedelta(seconds=start_monotonic))

    def ingest(self, call_stack, time, monotime, message=None):
        last_instruction = None
        node = self

        if message is not None:
            if len(call_stack) > 0:
                call_stack, last_instruction = call_stack[:-1], call_stack[-1]

        self.add_time(time, monotime)
        for instruction_pointer in call_stack:
            for child in node.current_children:
                if child.instruction_pointer == instruction_pointer:
                    node = child
                    node.add_time(time, monotime)
                    break
            else:
                new_node = _CallGraphNode(instruction_pointer, time, 0.0, monotime, monotime)
                node.current_children.append(new_node)
                node = new_node

        if message is not None:
            node.archived_children.extend(node.current_children)
            new_node = _CallGraphNode(last_instruction, time, 0.0, monotime, monotime)
            new_node.message = message
            node.archived_children.append(new_node)
            node.current_children = []
            node = new_node

        # Add self time to leaf node
        node.self_time += time

    def jsonize(self):
        result = self._jsonize(self.wall_clock_minus_monotonic)
        result['task_uuid'] = self.task_uuid
        result['thread'] = self.thread
        return result
