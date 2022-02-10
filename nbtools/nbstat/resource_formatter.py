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
    present in the `formatter`.

    Note that it does not change the order of elements: that is the key feature and allows us to define
    'templates` of table formatters, where some of the elements have `include` flag set to False by default.
    Changing the value of `include` flag adds required resources in the table in pre-defined positions.
    Refer to `NBSTAT_FORMATTER` for example.
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

    def __contains__(self, key):
        """ Overloaded `in` operator. """
        try:
            _ = self[key]
            return True
        except KeyError:
            return False

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

    @property
    def names(self):
        """ Aliases of all resources in `self`. """
        return [Resource.RESOURCE_TO_ALIAS[item['resource']] for item in self]

    @property
    def included_names(self):
        """ Aliases of included resources in `self`. """
        return [Resource.RESOURCE_TO_ALIAS[item['resource']] for item in self.included_only
                if 'TABLE_DELIMITER' not in item['resource'].name]

    @property
    def excluded_names(self):
        """ Aliases of not included resources in `self`. """
        return [Resource.RESOURCE_TO_ALIAS[item['resource']] for item in self
                if item['include'] is False and 'TABLE_DELIMITER' not in item['resource'].name]

    def toggle_bars(self):
        """ Change resources to use `bar` representation. """
        for item in self:
            if 'bar' in item:
                item['bar'] = not item['bar']


NBSTAT_FORMATTER = ResourceFormatter([
    # Notebook/script name
    {'resource' : Resource.NAME, 'include' : True, 'hidable': True},
    {'resource' : Resource.PATH, 'include' : False, 'hidable': True},
    {'resource' : Resource.CMDLINE, 'include' : False, 'hidable': True},

    # Process info
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.TYPE, 'include' : True},
    {'resource' : Resource.PID, 'include' : True},
    {'resource' : Resource.PPID, 'include' : False},
    {'resource' : Resource.NGID, 'include' : False},
    {'resource' : Resource.PYTHON_PPID, 'include' : False},
    {'resource' : Resource.HOST_PID, 'include' : False},
    {'resource' : Resource.KERNEL, 'include' : False},
    {'resource' : Resource.STATUS, 'include' : False, 'min_width' : 10},

    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.CREATE_TIME, 'include' : False},

    # Process resource usage
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.CPU, 'include' : False, 'min_width' : 5},
    {'resource' : Resource.RSS, 'include' : True, 'min_width' : 8},

    # Process device usage
    {'resource' : Resource.TABLE_DELIMITER2, 'include' : True},
    {'resource' : Resource.DEVICE_SHORT_ID, 'include' : True},
    {'resource' : Resource.DEVICE_PROCESS_PID, 'include' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'min_width' : 5, 'bar': False},
    {'resource' : Resource.DEVICE_UTIL_MA, 'include' : False, 'min_width' : 5, 'bar': False},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'min_width' : 5},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False},
    {'resource' : Resource.DEVICE_FAN, 'include' : False, 'min_width' : 4},
])


DEVICESTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True, 'hidable' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'hidable' : True, 'min_width' : 5, 'bar': False},
    {'resource' : Resource.DEVICE_UTIL_MA, 'include' : False, 'min_width' : 5, 'bar': False},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'hidable' : True, 'min_width' : 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False, 'hidable' : True},
    {'resource' : Resource.DEVICE_FAN, 'include' : False, 'hidable' : True, 'min_width' : 4},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},

    # Individual processes for each device
    {'resource' : Resource.DEVICE_PROCESS_MEMORY_USED, 'include' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},

    # Notebook/script name
    {'resource' : Resource.NAME, 'include' : True},
    {'resource' : Resource.CMDLINE, 'include' : False, 'hidable': True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},

    # Process info
    {'resource' : Resource.TYPE, 'include' : False},
    {'resource' : Resource.PID, 'include' : False},
    {'resource' : Resource.PPID, 'include' : False},
    {'resource' : Resource.NGID, 'include' : False},
    {'resource' : Resource.PYTHON_PPID, 'include' : False},
    {'resource' : Resource.DEVICE_PROCESS_PID, 'include' : True},
    {'resource' : Resource.HOST_PID, 'include' : False},
    {'resource' : Resource.KERNEL, 'include' : False},
    {'resource' : Resource.STATUS, 'include' : False},
    {'resource' : Resource.CREATE_TIME, 'include' : False},

    # Process resource usage
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.CPU, 'include' : False, 'min_width' : 5},
    {'resource' : Resource.RSS, 'include' : False, 'min_width' : 10},

])


GPUSTAT_FORMATTER = ResourceFormatter([
    # Device usage
    {'resource' : Resource.DEVICE_ID, 'include' : True},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_UTIL, 'include' : True, 'min_width': 5, 'bar': False},
    {'resource' : Resource.DEVICE_TEMP, 'include' : True, 'min_width': 5},
    {'resource' : Resource.DEVICE_POWER_USED, 'include' : False},
    {'resource' : Resource.TABLE_DELIMITER1, 'include' : True},
    {'resource' : Resource.DEVICE_MEMORY_USED, 'include' : True},
])
