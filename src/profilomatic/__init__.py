from __future__ import absolute_import
from .profiler import Profiler
from .output import file_destination, no_flush_destination, RestDestination

_instance = Profiler()
configure = _instance.configure
remove_destination = _instance.remove_destination
current_task_uuid = _instance.current_task_uuid


def add_destination(destination):
    _instance.start()
    _instance.add_destination(destination)
