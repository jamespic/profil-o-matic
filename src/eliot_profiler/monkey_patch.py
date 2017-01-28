from eliot import Action
from . import _instance
from .profiler import \
    ACTION_TYPE_FIELD, \
    REMOTE_TASK_ACTION, \
    TASK_UUID_FIELD, \
    TASK_LEVEL_FIELD

_original_serialize_task_id = Action.serialize_task_id


def _modified_serialize_task_id(self):
    serialized = _original_serialize_task_id(self)
    try:
        task_uuid, level = serialized.decode('ascii').split('@')
        level = [int(l) for l in level.split('/') if l]
        _instance._log_message({
            ACTION_TYPE_FIELD: REMOTE_TASK_ACTION,
            TASK_LEVEL_FIELD: level,
            TASK_UUID_FIELD: task_uuid
        })
    finally:
        return serialized


def patch():
    Action.serialize_task_id = _modified_serialize_task_id
    Action.serializeTaskId = _modified_serialize_task_id


def unpatch():
    Action.serialize_task_id = _original_serialize_task_id
    Action.serializeTaskId = _original_serialize_task_id
