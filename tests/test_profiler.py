from __future__ import absolute_import
import unittest
from mock import patch
import datetime
import collections
from profilomatic.profiler import Profiler, _MessageInfo
from profilomatic.stack_trace import generate_stack_trace


def drain_queue(q):
    output = []
    while True:
        try:
            output.append(q.popleft())
        except IndexError:
            return output


MockFrame = collections.namedtuple('MockFrame',
                                   'f_code f_globals f_lineno f_back')
MockCode = collections.namedtuple('MockCode', 'co_filename co_name')


def mock_frame(*frames):
    result = None
    for frame in frames:
        module, method, line = frame.split(':')
        filename = module.replace('.', '/') + '.py'
        result = MockFrame(
            MockCode(filename, method), {'__name__': module}, int(line),
            result)
    return result


def raise_nested_exception():
    def inner_raise_exception():
        raise Exception()
    inner_raise_exception()


def mock_current_frames():
    return {
        12345: mock_frame('__main__:main:1', 'business.app:__init__:5',
                          'business.backend:doStuff:10')
    }


class ProfilomaticTest(unittest.TestCase):
    maxDiff = None
    def test_max_actions_per_run(self):
        instance = Profiler(simultaneous_tasks_profiled=2)
        instance.handle_message({'task_uuid': '1', 'action_status': 'started'})
        instance.handle_message({
            'task_uuid': '1',
            'action_status': 'succeeded'
        })
        instance.handle_message({'task_uuid': '2', 'action_status': 'started'})
        instance.handle_message({
            'task_uuid': '2a',
            'action_status': 'started'
        })
        instance.handle_message({'task_uuid': '2a', 'action_status': 'failed'})
        instance.handle_message({'task_uuid': '2', 'action_status': 'failed'})
        instance.handle_message({'task_uuid': '3', 'action_status': 'started'})
        instance.handle_message({
            'task_uuid': '3',
            'action_status': 'succeeded'
        })
        messages = drain_queue(instance.message_queue)
        self.assertEqual(6, len(messages))
        self.assertEqual('1', messages[0].next_task_uuid)
        self.assertEqual(None, messages[1].next_task_uuid)
        self.assertEqual('2', messages[2].next_task_uuid)
        self.assertEqual('2a', messages[3].next_task_uuid)
        self.assertEqual('2', messages[4].next_task_uuid)
        self.assertEqual(None, messages[5].next_task_uuid)

    def test_dont_handle_message_outside_action(self):
        instance = Profiler(store_all_logs=True)
        instance.handle_message({'task_uuid': '99', 'msg': 'outside'})
        instance.handle_message({'task_uuid': '1', 'action_status': 'started'})
        instance.handle_message({'task_uuid': '1', 'msg': 'inside'})
        instance.handle_message({'task_uuid': '1', 'action_status': 'failed'})
        messages = drain_queue(instance.message_queue)
        self.assertEqual(3, len(messages))
        self.assertEqual('started', messages[0].message['action_status'])
        self.assertEqual('inside', messages[1].message['msg'])
        self.assertEqual('failed', messages[2].message['action_status'])

    def test_dont_store_all_logs(self):
        instance = Profiler(store_all_logs=False)
        instance.handle_message({'task_uuid': '1', 'action_status': 'started'})
        instance.handle_message({'task_uuid': '1', 'msg': 'inside'})
        instance.handle_message({'task_uuid': '1', 'action_status': 'failed'})
        messages = drain_queue(instance.message_queue)
        self.assertEqual(2, len(messages))
        self.assertEqual('started', messages[0].message['action_status'])
        self.assertEqual('failed', messages[1].message['action_status'])

    @patch('profilomatic.profiler.generate_stack_trace', generate_stack_trace
           )  # Use pure Python one, to allow use of mock stack frames
    def test_ingest_message(self):
        instance = Profiler(source_name='localhost', code_granularity='method')
        messages = []
        instance.add_destination(messages.append)

        msg1 = _MessageInfo(
            message={
                'action_status': 'started',
                'task_uuid': '1',
                'msg': 'Hi'
            },
            next_task_uuid='1')
        msg1.frame = mock_frame('__main__:main:1', 'business.app:__init__:5',
                                'eliot._action:startAction:100',
                                'profilomatic:emit:101')
        msg1.monotonic = 0.0
        msg1.clock = datetime.datetime(1988, 1, 1, 9, 0, 0)
        msg1.thread = 12345
        instance._ingest_message(msg1)

        msg2 = _MessageInfo(
            message={
                'action_status': 'success',
                'task_uuid': '1',
                'msg': 'World'
            },
            next_task_uuid=None)
        msg2.frame = mock_frame('__main__:main:1', 'business.app:__init__:5',
                                'eliot._action:endAction:100',
                                'profilomatic:emit:101')
        msg2.monotonic = 1.0
        msg2.clock = datetime.datetime(
            1987, 1, 1, 9, 0,
            0)  # Clock skew should be ignored, after first message
        msg2.thread = 12345
        instance._ingest_message(msg2)

        self.assertEqual([
            {
                "thread": 12345,
                "source": "localhost",
                "start_time": "1988-01-01T09:00:00",
                "task_uuid": "1",
                "self_time": 0.0,
                "end_time": "1988-01-01T09:00:01",
                "time": 0.0,
                "children": [
                    {
                        "start_time": "1988-01-01T09:00:00",
                        "instruction": "__main__.py:main",
                        "self_time": 0.0,
                        "end_time": "1988-01-01T09:00:01",
                        "time": 0.0,
                        "children": [
                            {
                                "start_time": "1988-01-01T09:00:00",
                                "instruction": "business/app.py:__init__",
                                "self_time": 0.0,
                                "end_time": "1988-01-01T09:00:00",
                                "time": 0.0,
                                "message": {
                                    "msg": "Hi",
                                    "task_uuid": "1",
                                    "action_status": "started"
                                }
                            },
                            {
                                "start_time": "1988-01-01T09:00:01",
                                "instruction": "business/app.py:__init__",
                                "self_time": 0.0,
                                "end_time": "1988-01-01T09:00:01",
                                "time": 0.0,
                                "message": {
                                    "msg": "World",
                                    "task_uuid": "1",
                                    "action_status": "success"
                                }
                            }
                        ]
                    }
                ]
            }
        ], messages)

    @patch('sys._current_frames', mock_current_frames)
    @patch('profilomatic.profiler.generate_stack_trace', generate_stack_trace
           )  # Use pure Python one, to allow use of mock stack frames
    def test_profiling_cycle(self):
        # import pudb
        # pu.db
        instance = Profiler(source_name='test_source', code_granularity='method')
        messages = []
        instance.add_destination(messages.append)

        msg1 = _MessageInfo(
            message={
                'action_status': 'started',
                'task_uuid': '1',
                'msg': 'Hi'
            },
            next_task_uuid='1')
        msg1.frame = mock_frame('__main__:main:1', 'business.app:__init__:5',
                                'eliot._action:startAction:100',
                                'profilomatic:emit:101')
        msg1.monotonic = 0.0
        msg1.clock = datetime.datetime(1988, 1, 1, 9, 0, 0)
        msg1.thread = 12345
        instance.message_queue.append(msg1)

        instance._profile_once(0.25, 0.5)

        msg2 = _MessageInfo(
            message={
                'action_status': 'success',
                'task_uuid': '1',
                'msg': 'World'
            },
            next_task_uuid=None)
        msg2.frame = mock_frame('__main__:main:1', 'business.app:__init__:5',
                                'eliot._action:endAction:100',
                                'profilomatic:emit:101')
        msg2.monotonic = 1.0
        msg2.clock = datetime.datetime(
            1987, 1, 1, 9, 0,
            0)  # Clock skew should be ignored, after first message
        msg2.thread = 12345
        instance.message_queue.append(msg2)

        instance._profile_once(0.25, 1.5)

        self.assertEqual([{
            "thread": 12345,
            "start_time": "1988-01-01T09:00:00",
            "source": "test_source",
            "task_uuid": "1",
            "self_time": 0.0,
            "end_time": "1988-01-01T09:00:01",
            "time": 0.25,
            "children": [
                {
                    "start_time": "1988-01-01T09:00:00",
                    "instruction": "__main__.py:main",
                    "self_time": 0.0,
                    "end_time": "1988-01-01T09:00:01",
                    "time": 0.25,
                    "children": [
                        {
                            "start_time": "1988-01-01T09:00:00",
                            "instruction": "business/app.py:__init__",
                            "self_time": 0.0,
                            "end_time": "1988-01-01T09:00:00",
                            "time": 0.0,
                            "message": {
                                "msg": "Hi",
                                "task_uuid": "1",
                                "action_status": "started"
                            }
                        },
                        {
                            "start_time": "1988-01-01T09:00:00.500000",
                            "instruction": "business/app.py:__init__",
                            "self_time": 0.0,
                            "end_time": "1988-01-01T09:00:00.500000",
                            "time": 0.25,
                            "children": [
                                {
                                    "start_time": "1988-01-01T09:00:00.500000",
                                    "self_time": 0.25,
                                    "instruction": "business/backend.py:doStuff",
                                    "end_time": "1988-01-01T09:00:00.500000",
                                    "time": 0.25
                                }
                            ]
                        },
                        {
                            "start_time": "1988-01-01T09:00:01",
                            "instruction": "business/app.py:__init__",
                            "self_time": 0.0,
                            "end_time": "1988-01-01T09:00:01",
                            "time": 0.0,
                            "message": {
                                "msg": "World",
                                "task_uuid": "1",
                                "action_status": "success"
                            }
                        }
                    ]
                }
            ]
        }], messages)

    def test_messageinfo_exc_info(self):
        try:
            raise_nested_exception()
        except:
            instance = _MessageInfo(None, None)
        trace = generate_stack_trace(instance.frame, 'method', False)
        self.assertTrue(trace[-1].endswith('inner_raise_exception'))
        self.assertTrue(trace[-2].endswith('raise_nested_exception'))
