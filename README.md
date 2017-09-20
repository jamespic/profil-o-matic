Profil-o-matic
==============
A hybrid profiler / mini APM tool for Python, that links slow high-level
actions to low-level code issues, even under load. It has hooks for WSGI and
Eliot to enable it to identify high-level actions.

It actively monitors profiling overhead, and can reduce granularity
or shed load to ensure the application is not adversely affected.
Hot loops are implemented in Cython, with pure Python fallbacks.

How it works
============

Profilomatic supports integration with Eliot, the context based logging
framework:

    import eliot
    import profilomatic
    import profilomatic.eliot

    profilomatic.eliot.patch()

    # Configure output the same way as eliot
    log_destination = eliot.FileDestination(open('app_log.log', 'w'))
    eliot.add_destination(log_destination)

    prof_destination = eliot.FileDestination(open('app_prof.log', 'w'))
    profilomatic.add_destination(prof_destination)


    # Optionally set your options
    profilomatic.configure(
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

It also supports WSGI, so can easily integrate into WSGI-based frameworks, such
as Flask or Django:

    import profilomatic

    # Configure output destinations
    prof_destination = profilomatic.file_destination(open('app_prof.log', 'w'))
    # Or maybe hook it up directly to Profil-o-matic analysis
    prof_destination = profilomatic.RestDestination(
      'monitoring_server', 443, ssl_context=ssl.create_default_context())

    profilomatic.add_destination(prof_destination)

    # Optionally set your options
    profilomatic.configure(
        max_overhead=0.02,  # Autotune granularity to target a desired profiling overhead - 2% in this case
        time_granularity=0.01,  # Sampling frequency - 10ms in this case
        code_granularity='method',  # Get file, method, or line-level performance data
        store_all_logs=False,  # Incorporate all log messages into call graph
        max_actions_per_run=10,  # When heavily loaded, limit how many new actions you profile per cycle
    )

    # Now run a program
    import urllib2
    import wsgiref.simple_server
    import profilomatic.wsgi

    @profilomatic.wsgi.wrap
    def app(environ, start_response):
        data = urllib2.urlopen('http://www.python.org').read()
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [data.replace('Python 3', 'Python 3000')]

    wsgiref.simple_server.make_server('', 8000, app).serve_forever()
