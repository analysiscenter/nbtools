""" Resource -- a class to describe a property of an entry. Refer to class documentation for more. """
from enum import Enum, auto


class Resource(Enum):
    """ Enumeration of all possible properties of an entry.
    An entry is any monitored entity -- Python process, Jupyter Notebook or device.

    A good example of property of a Python process is the amount of CPU resources it uses,
    or the number of its subprocesses, or the amount of GPUs (or other accelerators) taken by this process.
    At the same time, we consider less obvious properties to be a Resource: the name of process, its disk path and
    even type (process, notebook or device).
    Moreover, we consider table elements and prettifyings to be Resources as well: that help us to use the
    same notation for both building and formatting the resulting table.

    A sequence of Resources supposed to define both resources to fetch from system sensors and structure of the
    table (used columns and delimiters): we use `ResourceFormatter` class for that purpose.

    A dictionary of all properties with their values to describe an entry is `ResourceEntry`.
    Entries are collected into `ResourceTables`, which provide methods to beautifully format their data.
    Refer to those classes for continuation of the usage logic of Resources.

    Using the enumeration makes sure that the same named unique constants are used throughout the code base.
    Nevetheless, `parse_alias` method makes sure that we can convert string like `'device_util'` to a correct Resource.
    It comes handy when we get strings from command line, and we use it to process every key that can come from user.

    Members of this enumeration have prefixes to distinguish their supposed use:
        - `` to describe Python processes and Jupyter Notebooks properties like name, path, PID
        - `DEVICE_` to describe properties of accelerators like memory taken, temperature, and utilization
        - `TABLE_` to denote elements that are parts of the formatted table.

    As all `Enum`s, does not work well with `autoreload` Jupyter magic.


    TODO: a potential improvement of the logic is to use values not only for aliases, but to point out the
    resources to collect for complex columns, which are not fetched themselves, but rely on other collected resources.
    For example, the `DEVICE_SHORT_ID` requires the `DEVICE_ID` and we can define it here instead of
    the corresponding if-clause in the `ResourceInspector.get_device_table`.
    TODO: add encoder/decoder utilization
    """
    # Possible columns in python-table: notebooks and python scripts
    PROCESS = auto()
    TYPE = auto()
    NAME = 'process_name'
    PATH = auto()
    CMDLINE = auto()
    PID = auto()
    PPID = auto()
    NGID = auto()
    HOST_PID = auto()
    PYTHON_PPID = auto()
    CREATE_TIME = auto()
    KERNEL = 'kernel_id'
    STATUS = auto()

    RSS = auto()
    CPU = auto()

    # Possible columns in device-table: information about each device
    DEVICE_ID = auto()
    DEVICE_NAME = auto()
    DEVICE_MEMORY_UTIL = auto()
    DEVICE_MEMORY_USED = 'memory'
    DEVICE_MEMORY_TOTAL = auto()
    DEVICE_TEMP = ['temp', 'temperature']
    DEVICE_POWER_USED = 'power'
    DEVICE_POWER_TOTAL = auto()
    DEVICE_FAN = 'fan'
    DEVICE_UTIL = 'util'
    DEVICE_UTIL_ENC = auto()
    DEVICE_UTIL_DEC = auto()

    # Aggregated process info
    DEVICE_PROCESS_N = auto()
    DEVICE_PROCESS_PID = 'device_pid'
    DEVICE_PROCESS_MEMORY_USED = 'process_memory'

    # Used for better repr in formatter tables
    TABLE_DELIMITER1 = auto()
    TABLE_DELIMITER2 = auto()
    DEVICE_SHORT_ID = 'short_id'

    USES_DEVICE = auto()
    IS_PARENT = auto()

    # Moving averages
    DEVICE_UTIL_MA = 'util_ma'


    def __repr__(self):
        return self.name

    @staticmethod
    def parse_alias(alias):
        """ Convert a string `alias` into member of the Resource enumeration. """
        if isinstance(alias, str):
            alias = alias.lower()
            if alias in Resource.ALIAS_TO_RESOURCE:
                alias = Resource.ALIAS_TO_RESOURCE[alias]
        return alias

    def to_format_data(self, terminal, **kwargs):
        """ Create a string template and data for a given `self=resource`.
        For more information about formatting refer to `ResourceTable.format` method.
        """
        _ = kwargs
        style, string = None, None

        # Process description
        if self == Resource.NAME:
            style = terminal.bold
            string = 'PROCESS NAME'
        elif self in [Resource.TYPE, Resource.PID, Resource.PYTHON_PPID,
                          Resource.STATUS, Resource.CREATE_TIME, Resource.KERNEL]:
            style = terminal.normal

        # Process resources
        elif self in [Resource.RSS, Resource.CPU]:
            style = terminal.bold + terminal.cyan

        # Device description
        elif self == Resource.DEVICE_ID:
            style = terminal.blue
            string = 'DEVICE NAME ' + terminal.cyan + '[ID]'
        elif self == Resource.DEVICE_SHORT_ID:
            style = terminal.blue
            string = 'DEVICE ID'
        elif self == Resource.DEVICE_PROCESS_PID:
            string = 'DEVICE PID'

        # Device resources
        elif self == Resource.DEVICE_MEMORY_USED:
            style = terminal.yellow
        elif self == Resource.DEVICE_PROCESS_MEMORY_USED:
            style = terminal.yellow
        elif self == Resource.DEVICE_POWER_USED:
            style = terminal.magenta
        elif self in [Resource.DEVICE_UTIL]:
            style = terminal.green
            string = 'UTIL'
        elif self in [Resource.DEVICE_UTIL_MA]:
            style = terminal.green
            string = 'UTIL AVERAGE'
        elif self == Resource.DEVICE_TEMP:
            style = terminal.red

        # Table elements
        elif self == Resource.TABLE_DELIMITER1:
            string = '┃'
        elif self == Resource.TABLE_DELIMITER2:
            string = '║'

        # Default values
        if style is None:
            style = ''
        if string is None:
            string = self.name.replace('', '').replace('DEVICE_', '').replace('_USED', '').replace('_', ' ')
        return style, string


# Dictionary with aliases for each Resource: more aliases can be added by setting values in Enum instead of `auto`
# Added to the class attributes after its creation so it is not a member of actual enumeration.
ALIAS_TO_RESOURCE, RESOURCE_TO_ALIAS = {}, {}
for resource in Resource.__members__.values():
    name, aliases = resource.name, resource.value
    aliases_from_name = [name, name.lower()]

    aliases = aliases if isinstance(aliases, list) else [aliases]
    aliases = [alias for alias in aliases if not isinstance(alias, int)]
    aliases = aliases_from_name + aliases

    ALIAS_TO_RESOURCE.update({alias : resource for alias in aliases})
    RESOURCE_TO_ALIAS[resource] = [alias for alias in aliases if isinstance(alias, str)][-1]
Resource.ALIAS_TO_RESOURCE = ALIAS_TO_RESOURCE
Resource.RESOURCE_TO_ALIAS = RESOURCE_TO_ALIAS
