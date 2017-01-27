from __future__ import absolute_import
from .profiler import Profiler

_instance = Profiler()
configure = _instance.configure
remove_destination = _instance.remove_destination


def add_destination(destination):
    _instance.start()
    _instance.add_destination(destination)
