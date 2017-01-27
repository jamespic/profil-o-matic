import unittest
from .base_stack_trace_test import BaseStackTraceTest
from eliot_profiler.stack_trace import generate_stack_trace


class PureStackTraceTest(BaseStackTraceTest, unittest.TestCase):
    stack_trace_fn = generate_stack_trace.__call__
