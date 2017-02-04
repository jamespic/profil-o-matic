import datetime


class BaseCallGraphTest(object):
    maxDiff = None
    def test_call_graph(self):
        instance = self.call_graph_class(
            1, '12345', datetime.datetime(2016, 1, 21, 9, 0, 0), 1.0)
        instance.ingest([], 1.0, 1.0, {'event': 'missing_call_graph'})
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 2.0)
        instance.ingest(['main', 'doIt', '_innerDoSomethingElse'], 1.0, 3.0)
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 4.0)
        instance.ingest(['main', 'doIt'], 1.0, 5.0)
        instance.ingest(['main', 'doIt'], 0.0, 5.5, {'event': 'something'})
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 6.0)
        jsonized = instance.jsonize()
        import json
        self.assertEqual({
            "thread": 1,
            "start_time": "2016-01-21T09:00:00",
            "task_uuid": "12345",
            "self_time": 0.0,
            "end_time": "2016-01-21T09:00:05",
            "time": 6.0,
            "children": [
                {
                    "start_time": "2016-01-21T09:00:00",
                    "self_time": 1.0,
                    "message": {
                        "event": "missing_call_graph"
                    },
                    "end_time": "2016-01-21T09:00:00",
                    "time": 1.0
                },
                {
                    "start_time": "2016-01-21T09:00:01",
                    "instruction": "main",
                    "self_time": 0.0,
                    "end_time": "2016-01-21T09:00:05",
                    "time": 5.0,
                    "children": [
                        {
                            "start_time": "2016-01-21T09:00:01",
                            "instruction": "doIt",
                            "self_time": 1.0,
                            "end_time": "2016-01-21T09:00:04",
                            "time": 4.0,
                            "children": [
                                {
                                    "start_time": "2016-01-21T09:00:01",
                                    "self_time": 2.0,
                                    "instruction": "_innerDoIt",
                                    "end_time": "2016-01-21T09:00:03",
                                    "time": 2.0
                                },
                                {
                                    "start_time": "2016-01-21T09:00:02",
                                    "self_time": 1.0,
                                    "instruction": "_innerDoSomethingElse",
                                    "end_time": "2016-01-21T09:00:02",
                                    "time": 1.0
                                }
                            ]
                        },
                        {
                            "start_time": "2016-01-21T09:00:04.500000",
                            "instruction": "doIt",
                            "self_time": 0.0,
                            "end_time": "2016-01-21T09:00:04.500000",
                            "time": 0.0,
                            "message": {
                                "event": "something"
                            }
                        },
                        {
                            "start_time": "2016-01-21T09:00:05",
                            "instruction": "doIt",
                            "self_time": 0.0,
                            "end_time": "2016-01-21T09:00:05",
                            "time": 1.0,
                            "children": [
                                {
                                    "start_time": "2016-01-21T09:00:05",
                                    "self_time": 1.0,
                                    "instruction": "_innerDoIt",
                                    "end_time": "2016-01-21T09:00:05",
                                    "time": 1.0
                                }
                            ]
                        }
                    ]
                }
            ]
        }, jsonized)
