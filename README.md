Eliot Profiler
==============
A hybrid profiler / mini APM tool for Python, that uses eliot to link slow
high-level actions to low-level code issues, even under load.

It actively monitors profiling overhead, and can reduce granularity
or shed load to ensure the application is not adversely affected.
Hot loops are implemented in Cython, with pure Python fallbacks.

How it works
============

    import eliot
    import eliot_profiler

    # Configure output the same way as eliot
    log_destination = eliot.FileDestination(open('app_log.log', 'w'))
    prof_destination = eliot.FileDestination(open('app_prof.log', 'w'))

    eliot.add_destination(log_destination)
    eliot_profiler.add_destination(prof_destination)

    # Optionally set your options
    eliot_profiler.configure(
        max_overhead=0.02,  # Autotune granularity to target a desired profiling overhead - 2% in this case
        time_granularity=0.01,  # Sampling frequency - 10ms in this case
        code_granularity='method',  # Get file, method, or line-level performance data
        store_all_logs=False,  # Incorporate all log messages into call graph
        max_actions_per_run=10,  # When heavily loaded, limit how many new actions you profile per cycle
    )

    # Now run a program
    import urllib2
    import wsgiref.simple_server
    def app(environ, start_response):
        with eliot.startAction(event='app:hello-world'):
            data = urllib2.urlopen('http://www.python.org').read()
            start_response('200 OK', [('Content-Type', 'text/html')])
            return [data.replace('Python 3', 'Python 3000')]

    wsgiref.simple_server.make_server('', 8000, app).serve_forever()
