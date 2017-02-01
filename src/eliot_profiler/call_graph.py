import datetime


class _CallGraphNode(object):
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
    def __init__(self, monotime, message):
        self.monotime = monotime
        self.message = message

    def jsonize(self, wall_clock_minus_monotonic):
        return {
            'message_time': (wall_clock_minus_monotonic + datetime.timedelta(
                seconds=self.monotime)).isoformat(),
            'message': self.message
        }


class CallGraphRoot(object):
    def __init__(self, thread, task_uuid, start_time, start_monotonic):
        self.thread = thread
        self.task_uuid = task_uuid
        self.start_time = start_time
        self.start_monotonic = start_monotonic
        self.children = []

    def ingest(self, call_stack, time, monotime, message=None):
        node = None
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
        if node:
            node.self_time += time
            if message:
                node.archived_children.extend(node.current_children)
                node.archived_children.append(_MessageNode(monotime, message))
                node.current_children = []

    def jsonize(self):
        return {
            'thread': self.thread,
            'task_uuid': self.task_uuid,
            'start_time': self.start_time.isoformat(),
            'children': [
                node.jsonize(self.start_time
                             - datetime.timedelta(seconds=self.start_monotonic))
                for node in self.children
            ]
        }
