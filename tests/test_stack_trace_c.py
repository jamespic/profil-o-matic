import unittest
from .base_stack_trace_test import BaseStackTraceTest

try:
    from profilomatic._stack_trace import generate_stack_trace

    class CStackTraceTest(BaseStackTraceTest, unittest.TestCase):
        stack_trace_fn = generate_stack_trace.__call__
except ImportError:
    pass
