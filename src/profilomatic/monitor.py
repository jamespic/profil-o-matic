enabled = False


def enable_prometheus():
    global enabled
    if enabled:
        return

    from prometheus_client.core import \
        SummaryMetricFamily, \
        CounterMetricFamily, \
        GaugeMetricFamily, \
        Summary, \
        REGISTRY
    from . import _instance

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
            yield GaugeMetricFamily(
                'profiler_tasks_inflight',
                'The number of tasks that Eliot profiler is currently profiling',
                value=_instance.actions_since_last_run + len(_instance.thread_tasks)
            )
            yield GaugeMetricFamily(
                'profiler_tasks_allowed',
                'The number of tasks that the profiler thinks it can handle, whilst meeting its granularity and overhead targets',
                value=_instance.actions_next_run
            )

    REGISTRY.register(ProfilerCollector())
    enabled = True
