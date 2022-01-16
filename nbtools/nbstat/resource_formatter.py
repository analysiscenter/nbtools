""" A class to define resources to fetch from the system, as well as the table structure. """
from copy import deepcopy
from operator import attrgetter

from .resource import Resource



class ResourceFormatter(list):
    """ An ordered sequence to define which resources to request from the system, as well as
    how to structure them into formatted table.

    Each element is a dictionary with mandatory `resource` and `include` keys, and defines whether this
    `resource` must be fetched/included in the table based on the value of `include` flag.
    Other keys are used to format this column: refer to `ResourceTable.format` method for more about that.

    Note that we can't use `dict` (with resource as key) for this class directly as it would prohibit repeating columns.
    Despite that, we overload `getitem` to provide a dict-like interface for checking whether the `resource` should be
    requested from the system. For example, `formatter[Resource.DEVICE_TEMP]` returns True if it should be fetched.

    We also overload `setitem` to change value of `include` flag for a given resource. That provides simple API for
    modifying existing formatters.
    For example, `formatter[Resource.DEVICE_TEMP] = True` turns on the device temperature column, if it is
    present in the `formatter`. Note that it does not change the order of elements: that allows us to define
    'templates` of table formatters, where some of the elements have `include` flag set to False by default.
    Changing the value of `include` flag adds them in the table in desired position.
    Refer to `NBSTAT_FORMATTER` for example.
    `update` method allows for setting multiple values at once.
    """
    def __getitem__(self, key):
        key = Resource.parse_alias(key)

        if isinstance(key, Resource):
            for entry in self:
                if entry['resource'] is key:
                    if entry['include']:
                        return True
            return False

        result = super().__getitem__(key)
        return ResourceFormatter(result) if isinstance(result, list) else result

    def get(self, key, default=None):
        """ `getitem` with `default`. """
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        """ If `key` is a resource (or an alias), set the values of `include` flag for this resource. """
        key = Resource.parse_alias(key)

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
        """ Change multiple values at once. """
        other = other if other is not None else {}
        kwargs.update(other)

        for key, value in kwargs.items():
            self[key] = value

        if isinstance(other, ResourceFormatter):
            self.extend(other)

    def copy(self):
        """ Deep copy of the formatter. Used to not mess up the original formatter. """
        return deepcopy(self)

    def include_all(self):
        """ Turn on collection of all present resources. """
        for column in self:
            column['include'] = True

    @property
    def included_only(self):
        """ Return formatter with elements which `include` flag is set to True.
        Also removes subsequent duplicates of table delimiters.
        """
        formatter = []
        for column in self:
            included = column['include']
            if not included:
                continue

            resource = column['resource']

            if 'TABLE_DELIMITER' in resource.name and len(formatter) > 0:
                previous_resource = formatter[-1]['resource']
                if 'TABLE_DELIMITER' in previous_resource.name:
                    formatter[-1]['resource'] = max(resource, previous_resource, key=attrgetter('value'))
                    continue
            formatter.append(column)

        if 'TABLE_DELIMITER' in formatter[-1]['resource'].name:
            formatter.pop()
        return formatter


NBSTAT_FORMATTER = ResourceFormatter([
    # Notebook/script name
    {'resource' : Resource.PY_NAME, 'include' :  True, 'hidable' :  True},

    # Process info
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_TYPE, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_PID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_SELFPID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_KERNEL, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_STATUS, 'include' : False, 'hidable' : False, 'min_width' : 10},

    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_CREATE_TIME, 'include' : False, 'hidable' : False},

    # Process resource usage
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_RSS, 'include' : True, 'hidable' : True, 'min_width': 8},

    # Process device usage
    {'resource' : Resource.TABLE_DELIMITER2, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_SHORT_ID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True, 'hidable' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : False, 'min_width' : 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : False, 'min_width' : 5},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : False},
])


DEVICESTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True, 'hidable' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : True},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : True, 'min_width' : 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : True, 'min_width' : 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},

    # Individual processes for each device
    {'resource' : Resource.PY_NAME, 'include' :  True, 'hidable' :  False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True, 'hidable' : False},
    # Notebook/script name

    # Process info
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_TYPE, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_PID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_SELFPID, 'include' : False, 'hidable' : False},
    {'resource' : Resource.PY_KERNEL, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_STATUS, 'include' : False, 'hidable' : True},
    {'resource' : Resource.PY_CREATE_TIME, 'include' : False, 'hidable' : False},

    # Process resource usage
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.PY_RSS, 'include' : False, 'hidable' : False, 'min_width' : 10},

])


GPUSTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True, 'hidable' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : False, 'min_width': 5},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : False, 'min_width': 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : True, 'hidable' : False},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : False, 'hidable' : False},
])
