""" !!. """
from copy import deepcopy
from operator import attrgetter

from .resource import Resource, parse_alias

class ResourceFormatter(list):
    """ List that defines the order and columns in the displayed table.
    Each entry defines resource, whether to include it and if it can be hidden, as well as some other display params.
    The order of the list is used for table ordering.

    #TODO: can easily make compatible with repeating columns
    """
    def __init__(self, obj):
        obj = [list(entry) if isinstance(entry, tuple) else entry for entry in obj]

        actual_resources = [entry['resource'] for entry in obj if 'DELIMITER' not in entry['resource'].name]
        if len(actual_resources) != len(set(actual_resources)):
            raise ValueError('Each resource should be used only once in formatter!')
        super().__init__(obj)

    def __getitem__(self, key):
        key = parse_alias(key)

        if isinstance(key, Resource):
            for entry in self:
                if entry['resource'] is key:
                    return entry['include']
            raise KeyError(f'Entry `{key}` is not in the formatter!')

        result = super().__getitem__(key)
        return ResourceFormatter(result) if isinstance(result, list) else result

    def get(self, key, default=None):
        """ !!. """
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        key = parse_alias(key)

        if isinstance(key, str):
            raise KeyError(f'Key `{key}` is not recognized!')

        if isinstance(key, Resource):
            for entry in self:
                if entry['resource'] is key:
                    entry['include'] = value
                    return None
            raise KeyError(f'Entry `{key}` is not in the formatter!')
        return super().__setitem__(key, value)

    def update(self, other=None, **kwargs):
        """ !!. """
        other = other if other is not None else {}
        kwargs.update(other)

        for key, value in kwargs.items():
            self[key] = value

        if isinstance(other, ResourceFormatter):
            self.extend(other)

    def copy(self):
        return deepcopy(self)

    def include_all(self):
        """ !!. """
        for column in self:
            column['include'] = True

    @property
    def included_only(self):
        """ !!. """
        formatter = []
        for column in self:
            included = column['include']
            if not included:
                continue

            resource = column['resource']

            if 'DELIMITER' in resource.name and len(formatter) > 0:
                previous_resource = formatter[-1]['resource']
                if 'DELIMITER' in previous_resource.name:
                    formatter[-1]['resource'] = max(resource, previous_resource, key=attrgetter('value'))
                    continue
            formatter.append(column)

        if 'DELIMITER' in formatter[-1]['resource'].name:
            formatter.pop()
        return formatter


NBSTAT_FORMATTER = ResourceFormatter([
    # Notebook/script name
    {'resource' : Resource.PY_NAME, 'include' :  True, 'hidable' :  True},

    # Process info
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_TYPE, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_PID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_SELFPID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_KERNEL, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_STATUS, 'include' : False, 'hidable' : False, 'min_width' : 10},

    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_CREATE_TIME, 'include' : False, 'hidable' : False},

    # Process resource usage
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_RSS, 'include' : True, 'hidable' : True, 'min_width': 8},

    # Process device usage
    {'resource' : Resource.DELIMITER2, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_SHORT_ID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : False, 'min_width' : 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : False, 'min_width' : 5},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : False},
])


DEVICESTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True, 'hidable' : True},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : True},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : True, 'min_width' : 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : True, 'min_width' : 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : True},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},

    # Individual processes for each device
    {'resource' : Resource.PY_NAME, 'include' :  True, 'hidable' :  False},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True, 'hidable' : False},
    # Notebook/script name

    # Process info
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_TYPE, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_PID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_SELFPID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_KERNEL, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_STATUS, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_CREATE_TIME, 'include' : False, 'hidable' : False},

    # Process resource usage
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_RSS, 'include' : False, 'hidable' : False, 'min_width' : 10},

])


GPUSTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : False, 'min_width': 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : False, 'min_width': 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : False, 'hidable' : False},
])
