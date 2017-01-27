import unittest
from .base_call_graph_test import BaseCallGraphTest
from eliot_profiler.call_graph import CallGraphRoot


class PureCallGraphTest(BaseCallGraphTest, unittest.TestCase):
    call_graph_class = CallGraphRoot
