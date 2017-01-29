enabled = False


def enable_prometheus():
    global enabled
    if enabled:
        return

    from prometheus_client.core import \
        SummaryMetricFamily, \
        CounterMetricFamily, \
        Summary, \
        REGISTRY
    from eliot import add_destination
    from . import _instance, add_destination

    class ProfilerCollector(object):
        def collect(self):
            yield SummaryMetricFamily(
                'profiler_profiling_time_secs',
                'Time used in profiling, each cycle, by Eliot profiler',
                count_value=_instance.total_samples,
                sum_value=_instance.total_overhead
            )
            yield SummaryMetricFamily(
                'profiler_profiling_granularity_secs',
                'The time granularity that Eliot profiler has been able to achieve',
                count_value=_instance.total_samples,
                sum_value=_instance.granularity_sum
            )
            yield CounterMetricFamily(
                'profiler_tasks_profiled_total',
                'The number of tasks that Eliot profiler has agreed to profile',
                value=_instance.profiled_tasks
            )
            yield CounterMetricFamily(
                'profiler_tasks_not_profiled_total',
                'The number of tasks that Eliot profiler has elected not to profile, to reduce load',
                value=_instance.unprofiled_tasks
            )
            yield CounterMetricFamily(
                'profiler_tasks_inflight',
                'The number of tasks that Eliot profiler is currently profiling',
                value=_instance.actions_since_last_run + len(_instance.thread_tasks)
            )

    REGISTRY.register(ProfilerCollector())
    enabled = True
