import unittest

import threading
import wsgiref.simple_server

from profilomatic.output import RestDestination

class MockWSGIApp(object):
    def __init__(self):
        self.requests = []
    def __call__(self, environ, start_response):
        environ['wsgi.input'] = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
        self.requests.append(environ)
        start_response('200 OK', [('Content-Type', 'application/json')])
        return ['{"status": "OK"}']

class RestDestinationTest(unittest.TestCase):
    def setUp(self):
        self.mock_app = MockWSGIApp()
        self.httpd = wsgiref.simple_server.make_server('0.0.0.0', 6483, self.mock_app)
        self.thread = threading.Thread(target=self.httpd.serve_forever, args=(0.01,))
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join()

    def test_rest_output(self):
        instance = RestDestination('127.0.0.1', 6483)
        instance({"hello": "world"})
        self.assertEqual(self.mock_app.requests[0]['wsgi.input'], '{"hello": "world"}')
