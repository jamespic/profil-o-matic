import datetime


cdef class _CallGraphNode(object):
    cdef str instruction_pointer
    cdef double time
    cdef double self_time
    cdef double min_monotonic
    cdef double max_monotonic
    cdef list archived_children
    cdef list current_children

    def __init__(self,
                 str instruction_pointer,
                 double time,
                 double self_time,
                 double min_monotonic,
                 double max_monotonic):
        self.instruction_pointer = instruction_pointer
        self.time = time
        self.self_time = self_time
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


cdef class _MessageNode(object):
    cdef double monotime
    cdef object message

    def __init__(self, double monotime, object message):
        self.monotime = monotime
        self.message = message

    cpdef dict jsonize(self, wall_clock_minus_monotonic):
        return {
            'message_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.monotime)).isoformat(),
            'message': self.message
        }


cdef class CallGraphRoot(object):
    cdef long thread
    cdef basestring task_uuid
    cdef object wallclock_minus_monotonic
    cdef list children

    def __init__(self, long thread, basestring task_uuid, wallclock_minus_monotonic):
        self.thread = thread
        self.task_uuid = task_uuid
        self.wallclock_minus_monotonic = wallclock_minus_monotonic
        self.children = []

    def ingest(self, list call_stack, double time, double monotime, message=None):
        cdef _CallGraphNode child
        cdef str instruction_pointer
        cdef _CallGraphNode node = None
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
                node = _CallGraphNode(instruction_pointer, time, 0.0, monotime, monotime)
                children.append(node)
            children = node.current_children
        # Do extra steps that only apply to leaf node
        if node is not None:
            node.self_time += time
            if message:
                node.archived_children.extend(node.current_children)
                node.archived_children.append(_MessageNode(monotime, message))
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
