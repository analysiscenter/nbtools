""" !!. """
from enum import Enum, auto


class Resource(Enum):
    """ !!.
    Does not work well with autoreload magic.
    """
    # Possible columns in python-table: notebooks and python scripts
    PY_TYPE = auto()
    PY_NAME = auto()
    PY_PATH = auto()
    PY_PID = auto()
    PY_SELFPID = auto()
    PY_CREATE_TIME = auto()
    PY_RSS = auto()
    PY_KERNEL = auto()
    PY_STATUS = auto()

    # Possible columns in device-table: information about each device
    DEVICE_ID = auto()
    DEVICE_NAME = auto()
    DEVICE_MEMORY_UTIL = auto()
    DEVICE_MEMORY_USED = 'memory'
    DEVICE_MEMORY_TOTAL = auto()
    DEVICE_TEMP = ['temp', 'temperature']
    DEVICE_FAN = ['fan', 'fans']
    DEVICE_UTIL = 'util'
    DEVICE_UTIL_ENC = auto()
    DEVICE_UTIL_DEC = auto()

    DEVICE_POWER_USED = 'power'
    DEVICE_POWER_TOTAL = auto()

    # Aggregated process info
    DEVICE_PROCESS_N = auto()
    DEVICE_PROCESS_PID = auto()
    DEVICE_PROCESS_MEMORY_USED = auto()

    # Aggregated resources: one for each notebook/script
    AGGREGATED_RSS = auto()
    AGGREGATED_DEVICE_MEMORY_USED = auto()

    # Used for better repr
    DELIMITER1 = auto()
    DELIMITER2 = auto()
    DEVICE_SHORT_ID = auto()

    def __repr__(self):
        return self.name

    def to_format_data(self, terminal, process_memory_format, device_memory_format):
        """ !!. """
        _ = terminal, process_memory_format, device_memory_format
        template = None # for possible future changes

        if self == Resource.DEVICE_ID:
            data = ['DEVICE NAME', 'ID']
        elif self == Resource.DEVICE_SHORT_ID:
            data = ['DEVICE ID']
        elif self == Resource.DELIMITER1:
            data = ['|']
        elif self == Resource.DELIMITER2:
            data = ['||']
        else:
            data = self.name.replace('PY_', '').replace('DEVICE_', '').replace('_USED', '').replace('_', ' ')
            data = [data]
        return template, data


# Dictionary with aliases for each Resource: more aliases can be added by setting values in Enum instead of `auto`
ALIAS_TO_RESOURCE = {}
for resource in Resource.__members__.values():
    name, aliases = resource.name, resource.value
    aliases = aliases if isinstance(aliases, list) else [aliases]
    aliases.extend([name, name.lower(), name.lower().replace('py_', '')])

    ALIAS_TO_RESOURCE.update({alias : resource for alias in aliases})

def parse_alias(alias):
    """ !!. """
    if isinstance(alias, str) and alias in ALIAS_TO_RESOURCE:
        alias = ALIAS_TO_RESOURCE[alias]
    return alias
