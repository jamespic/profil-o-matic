try:
    from eliot_profiler.fast_monotonic import monotonic
    from unittest import TestCase
    from time import sleep

    class TestFastMonotonic(TestCase):
        def test_fast_monotonic(self):
            start = monotonic()
            sleep(0.75)
            end = monotonic()
            self.assertAlmostEqual(end - start, 0.75, delta=0.2)

except (ImportError, OSError):
    pass
