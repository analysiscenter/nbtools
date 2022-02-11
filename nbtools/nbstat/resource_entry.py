""" ResourceEntry -- a dict-like class to hold all properties (Resources) of an entry. """
from datetime import datetime

from .resource import Resource
from .utils import format_memory

class ResourceEntry(dict):
    """ Dictionary to hold all properties (Resources) of an entry.
    An entry is any monitored entity -- Python process, Jupyter Notebook or device.
    For more about Resources, refer to its class documentation.

    `getitem` is overloaded to recognize Resource aliases (like `memory_util`) as actual Resource enumeration members.

    The main method of this class, `format`, is used to create a string representation of a single requested property
    from the contained information. As some of the requested columns require multiple values from the dictionary,
    we can't use individual key-value pairs to create string representation on their own.
    For example, the `DEVICE_MEMORY` column show the `'used_memory / total_memory MB'` information and
    requires multiple items from the ResourceEntry at the same time.
    """
    def __getitem__(self, key):
        key = Resource.parse_alias(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        key = Resource.parse_alias(key)
        return super().get(key, default)

    def to_format_data(self, resource, terminal, **kwargs):
        """ Create a string template and data for a given `resource`. Essentially, a huge switch on `resource` type.
        For more information about formatting refer to `ResourceTable.format` method.

        Parameters
        ----------
        resource : member of Resource
            Column to create string representation for.
        terminal : blessed.Terminal
            Terminal to use for text formatting and color control sequences.
        kwargs : dict
            Other parameters for string creation like memory format, width, etc.
        """
        #pylint: disable=too-many-statements
        resource = Resource.parse_alias(resource)
        default_string = '-'
        style, string = None, None
        data = self.get(resource, None)

        # Process description
        if resource in [Resource.PATH, Resource.CMDLINE, Resource.STATUS,
                        Resource.PID, Resource.PPID, Resource.NGID, Resource.HOST_PID, Resource.PYTHON_PPID,
                        Resource.DEVICE_PROCESS_PID,]:
            pass

        elif resource in [Resource.NAME, Resource.TYPE]:
            if data is not None:
                if 'zombie' in data or 'container' in data:
                    style = terminal.red
                if '/' in data:
                    data = '~' + data.split('/')[-1]

        elif resource == Resource.CREATE_TIME:
            if data is not None:
                data = datetime.fromtimestamp(data).strftime("%Y-%m-%d %H:%M:%S")
        elif resource == Resource.KERNEL:
            data = data.split('-')[0] if data is not None else 'N/A'

        # Process resources
        elif resource == Resource.CPU:
            process = self[Resource.PROCESS]
            if process is not None:
                data = process.cpu_percent()
                data = round(data)

                style = terminal.bold if data > 30 else ''
                string = f'{data}%' # don't use the `％` symbol as it is not unit wide

        elif resource == Resource.RSS:
            if data is not None:
                rounded, unit = format_memory(data, format=kwargs['process_memory_format'])
                data = f'{rounded} {unit}'

        # Device description
        elif resource == Resource.DEVICE_ID:
            if data is not None:
                device_name = (self[Resource.DEVICE_NAME].replace('NVIDIA', '').replace('RTX', '')
                               .replace('  ', ' ').strip())
                string = f'{device_name} {terminal.cyan}[{data}]'

        elif resource == Resource.DEVICE_SHORT_ID:
            data = self.get(Resource.DEVICE_ID, None)
            if data is not None:
                data = data if data is not None else default_string
                device_name = (self[Resource.DEVICE_NAME]
                               .replace('NVIDIA', '').replace('RTX', '').replace('GeForce', '')
                               .replace('  ', ' ').strip())
                string = f'{device_name} [{data}]'

        # Device resources
        elif resource == Resource.DEVICE_MEMORY_USED:
            if data is not None:
                style = terminal.bold if data > 10*1024*1024 else ''

                memory_format = kwargs['device_memory_format']
                used, unit = format_memory(data, format=memory_format)
                total, unit = format_memory(self[Resource.DEVICE_MEMORY_TOTAL], format=memory_format)

                n_digits = len(str(total))
                string = (f'{terminal.normal + terminal.yellow}{style}{used:>{n_digits}}'
                          f'{terminal.normal + terminal.bold} / '
                          f'{terminal.normal + terminal.yellow}{style}{total} '
                          f'{terminal.normal + terminal.bold}{unit}')

        elif resource == Resource.DEVICE_PROCESS_MEMORY_USED:
            if data is not None:
                style = terminal.bold if data > 10*1024*1024 else ''

                memory_format = kwargs['device_memory_format']
                used_process, unit = format_memory(data, format=memory_format)
                used_device, unit = format_memory(self[Resource.DEVICE_MEMORY_USED], format=memory_format)
                total, _ = format_memory(self[Resource.DEVICE_MEMORY_TOTAL], format=memory_format)

                n_digits = len(str(total))
                string = (f'{terminal.normal + terminal.yellow}{style}{used_process:>{n_digits}}'
                          f'{terminal.normal + terminal.bold} / '
                          f'{terminal.normal + terminal.yellow}{style}{max(used_device, used_process):>{n_digits}}'
                          f'{terminal.normal + terminal.bold} / '
                          f'{terminal.normal + terminal.yellow}{style}{total} '
                          f'{terminal.normal + terminal.bold}{unit}')
            else:
                # Fallback to total device memory usage, if possible
                if self.get(Resource.DEVICE_MEMORY_USED, None) is not None:
                    entry = {key : self[key] for key in [Resource.DEVICE_MEMORY_USED, Resource.DEVICE_MEMORY_TOTAL]}
                    entry = ResourceEntry(entry)
                    style, string = entry.to_format_data(resource=Resource.DEVICE_MEMORY_USED,
                                                         terminal=terminal, **kwargs)

        elif resource == Resource.DEVICE_POWER_USED:
            if data is not None:
                power_used = data // 1000
                power_total = self[Resource.DEVICE_POWER_TOTAL] // 1000
                string = f'{power_used:>3}/{power_total:>3} W'

        elif resource in [Resource.DEVICE_FAN, Resource.DEVICE_UTIL, Resource.DEVICE_UTIL_MA]:
            if data is not None:
                style = terminal.bold if data >= 30 else ''
                string = f'{data}%' # don't use the `％` symbol as it is not unit wide

                if kwargs.get('bar'):
                    if data < 30:
                        bar_color = terminal.on_red
                    elif data < 70:
                        bar_color = terminal.on_yellow
                    else:
                        bar_color = terminal.on_green

                    string = f'{string:^4}'.center(9)

                    split = data // 10
                    string_1 = f'{terminal.normal}{bar_color}{style}{string[:split]}'
                    string_2 = f'{terminal.normal}{style}{string[split:]}' # can add {terminal.on_white}
                    string = string_1 + string_2

        elif resource == Resource.DEVICE_TEMP:
            if data is not None:
                style = terminal.bold if data >= 40 else ''
                string = f'{data}°C' # don't use the `℃` symbol as it is not unit wide

        # Table delimiters
        elif resource == Resource.TABLE_DELIMITER1:
            string = '┃'
        elif resource == Resource.TABLE_DELIMITER2:
            string = '║'

        # Default values
        if style is None:
            style = ''
        if string is None:
            if data is not None:
                string = str(data)
            else:
                string = default_string
        return style, string
