from __future__ import absolute_import
from uuid import uuid4
from urlparse import parse_qs

from .profiler import \
    TASK_UUID_FIELD, \
    ACTION_TYPE_FIELD, \
    ACTION_STATUS_FIELD, \
    STARTED_STATUS, \
    SUCCEEDED_STATUS, \
    FAILED_STATUS
from . import _instance

TASK_UUID_HEADER = 'HTTP_X_TASK_UUID'
HOST_HEADER = 'HTTP_HOST'
HOST_FIELD = 'host'
WSGI_TASK_TYPE = 'wsgi_task'


class ProfiledApp(object):
    def __init__(self, app, profiler=_instance):
        self.__app = app
        self.__profiler = profiler

    def __call__(self, environ, start_response):
        task_uuid = (environ[TASK_UUID_HEADER]
                     if TASK_UUID_HEADER in environ
                     else str(uuid4()))
        task_type = environ.get('PATH_INFO') or 'wsgi_task'
        environ[TASK_UUID_HEADER] = task_uuid

        def wrap_iterator(result):
            try:
                for row in result:
                    yield row
            except:
                log_failure()
                raise
            else:
                log_success()

        def log_start():
            message_dict = {
                TASK_UUID_FIELD: environ[TASK_UUID_HEADER],
                ACTION_TYPE_FIELD: task_type,
                ACTION_STATUS_FIELD: STARTED_STATUS
            }
            message_dict['query_string'] = parse_qs(
                environ.get('QUERY_STRING', ''))
            if HOST_HEADER in environ:
                message_dict[HOST_FIELD] = environ[HOST_HEADER]
            else:
                message_dict[HOST_FIELD] = (environ['SERVER_NAME'] +
                                            ':' + environ['SERVER_PORT'])
            message_dict['script_name'] = environ['SCRIPT_NAME']
            message_dict['path_info'] = environ['PATH_INFO']
            self.__profiler.handle_message(message_dict)

        def log_success():
            message_dict = {
                TASK_UUID_FIELD: task_uuid,
                ACTION_TYPE_FIELD: task_type,
                ACTION_STATUS_FIELD: SUCCEEDED_STATUS
            }
            self.__profiler.handle_message(message_dict)

        def log_failure():
            message_dict = {
                TASK_UUID_FIELD: task_uuid,
                ACTION_TYPE_FIELD: task_type,
                ACTION_STATUS_FIELD: FAILED_STATUS
            }
            self.__profiler.handle_message(message_dict)

        log_start()

        try:
            result = self.__app(environ, start_response)

            file_wrapper = environ.get('wsgi.file_wrapper')

            is_result_wrapped_file = False
            try:
                if isinstance(result, file_wrapper):
                    is_result_wrapped_file = True
            except:
                pass

            if is_result_wrapped_file:
                log_success()
                return result
            else:
                return wrap_iterator(result)
        except:
            log_failure()
            raise



## FIXME: Figure out what assumptions I'm making about log formats


def wrap(app):
    return ProfiledApp(app)
