import datetime


class BaseCallGraphTest(object):
    def test_call_graph(self):
        instance = self.call_graph_class(
            1, '12345', datetime.datetime(2016, 1, 21, 9, 0, 0))
        instance.ingest([], 0.0, 0.0)
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 1.0)
        instance.ingest(['main', 'doIt', '_innerDoSomethingElse'], 1.0, 2.0)
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 3.0)
        instance.ingest(['main', 'doIt'], 1.0, 4.0)
        instance.ingest(['main', 'doIt'], 0.0, 4.5, {'event': 'something'})
        instance.ingest(['main', 'doIt', '_innerDoIt'], 1.0, 5.0)
        jsonized = instance.jsonize()
        self.assertEqual({
            "task_uuid": "12345",
            "children": [{
                "start_time": "2016-01-21T09:00:01",
                "instruction": "main",
                "self_time": 0,
                "end_time": "2016-01-21T09:00:05",
                "time": 5.0,
                "children": [{
                    "start_time": "2016-01-21T09:00:01",
                    "instruction": "doIt",
                    "self_time": 1.0,
                    "end_time": "2016-01-21T09:00:05",
                    "time": 5.0,
                    "children": [{
                        "self_time": 2.0,
                        "start_time": "2016-01-21T09:00:01",
                        "instruction": "_innerDoIt",
                        "end_time": "2016-01-21T09:00:03",
                        "time": 2.0
                    }, {
                        "self_time": 1.0,
                        "start_time": "2016-01-21T09:00:02",
                        "instruction": "_innerDoSomethingElse",
                        "end_time": "2016-01-21T09:00:02",
                        "time": 1.0
                    }, {
                        "message": {
                            "event": "something"
                        },
                        "message_time": "2016-01-21T09:00:04.500000"
                    }, {
                        "self_time": 1.0,
                        "start_time": "2016-01-21T09:00:05",
                        "instruction": "_innerDoIt",
                        "end_time": "2016-01-21T09:00:05",
                        "time": 1.0
                    }]
                }]
            }],
            "thread": 1
        }, jsonized)
