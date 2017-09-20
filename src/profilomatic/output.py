import json
import six.moves.http_client as httplib

from six import b


def _ensure_file_obj(f):
    if isinstance(f, basestring):
        return open(f, 'w')
    else:
        return f


def file_destination(f):
    f = _ensure_file_obj(f)

    def write(message):
        f.write(json.dumps(message) + '\n')
        f.flush()
    return write


def no_flush_destination(f):
    f = _ensure_file_obj(f)

    def write(message):
        f.write(json.dumps(message) + '\n')
    return write


class RestDestination(object):
    def __init__(self, host, port=None, timeout=5, ssl_context=None):
        self._host = host
        self._port = port
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._connection = None

    def __call__(self, data):
        if not self._connection:
            if self._ssl_context:
                self._connection = httplib.HTTPSConnection(
                    self._host, self._port or 443,
                    timeout=self._timeout, context=self._ssl_context)
            else:
                self._connection = httplib.HTTPConnection(
                    self._host, self._port or 80, timeout=self._timeout)
        try:
            self._connection.request('POST', '/api/data', b(json.dumps(data)))
            response = self._connection.getresponse()
            response.read()
        except:
            self._connection = None
            raise
