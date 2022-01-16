""" ResourceEntry -- a dict-like class to hold all properties (Resources) of an entry.
ResourceTable -- sequence of multiple ResourceEntries with interface of merging, updating, sorting for multiple tables.
Can be formatted into beautiful colored string representation by using `format` method.
"""
from datetime import datetime

from .resource import Resource
from .utils import format_memory, true_len, true_rjust

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
        resource = Resource.parse_alias(resource)
        default_string = '-'
        style, string = None, None
        data = self.get(resource, None)

        # Process description
        if resource in [Resource.PY_NAME, Resource.PY_PATH, Resource.PY_TYPE,
                        Resource.PY_PID, Resource.PY_SELFPID, Resource.PY_STATUS]:
            pass
        elif resource == Resource.PY_CREATE_TIME:
            data = datetime.fromtimestamp(data).strftime("%Y-%m-%d %H:%M:%S")
        elif resource == Resource.PY_KERNEL:
            data = data.split('-')[0] if data is not None else 'N/A'

        # Process resources
        elif resource == Resource.PY_CPU:
            data = self[Resource.PY_PROCESS].cpu_percent(interval=kwargs.get('interval', 0.01))
            data = round(data)

            if data > 30:
                style = terminal.bold
            string = f'{data}%' # don't use the `％` symbol as it is not unit wide

        elif resource == Resource.PY_RSS:
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
            data = self.get(Resource.DEVICE_ID, None) or default_string
            string = f'[{data}]'

        # Device resources
        elif resource == Resource.DEVICE_MEMORY_USED:
            if data is not None:
                if data > 10*1024*1024:
                    style = terminal.bold
                else:
                    style = ''

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
                if data > 10*1024*1024:
                    style = terminal.bold
                else:
                    style = ''

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

        elif resource in [Resource.DEVICE_FAN, Resource.DEVICE_UTIL]:
            if data is not None:
                if data > 30:
                    style = terminal.bold
                string = f'{data}%' # don't use the `％` symbol as it is not unit wide

        elif resource == Resource.DEVICE_TEMP:
            if data is not None:
                if data > 40:
                    style = terminal.bold
                string = f'{data}°C' # don't use the `℃` symbol as it is not unit wide

        # Table delimiters
        elif resource == Resource.TABLE_DELIMITER1:
            string = '|'
        elif resource == Resource.TABLE_DELIMITER2:
            string = '||'

        # Default values
        if style is None:
            style = ''
        if string is None:
            if data is not None:
                string = str(data)
            else:
                string = default_string
        return style, string


class ResourceTable:
    """ Container for multiple ResourceEntries.
    Provides API to work with multiple tables, collected about different types of entries. In this module, we use:
        - a table about all Python processes, collected with `psutil` and the likes
        - a table about Jupyter Notebooks, collected with requests to `jupyter_server` and `notebook` interfaces
        - a table about system devices, collected with `nvidia-smi` Python bindings.

    Creating a final table for actual representation requires some merges, sorts, filtering, etc.
    For convenience, we implement all of the usual table methods: `merge`, `update`, `sort`, `filter`, as well as their
    versions for working with tables with defined `index`.

    For the most part, this class acts as a lightweight version of a`Pandas.DataFrame`: it saves us a huge dependency
    and also allows to tweak some of the metods to our needs. As our tables are tiny, efficiency is not a concern.
    If the `pandas` is already installed, `ResourceTable` can be converted to dataframe by using `to_pd` method.

    Also provides method `format` for table visualization as a beautiful colored string representation.
    Most of the design choices in this module are dictated by the needs of this method: classes are made as they are
    so it is easy to use them there.

    Current implementation uses `list` as the underlying container, which is appended by `ResourceEntries`.
    Checks that the set of appended columns is the same as columns in previous entries, but does not guarantee
    consistency of columns if initialized from list.

    # TODO: can require `index` and/or `columns` at table creation, should we want so, for consistency
    # TODO: can create a `PandasResourceTable` with the same API, but `pandas.DataFrame` under the hood
    """
    #pylint: disable=self-cls-assignment
    def __init__(self, data=None):
        self._data = [] if data is None else [ResourceEntry(entry) for entry in data]

    @property
    def data(self):
        """ Property to make sure that every entry is an instance of `ResourceEntry`. """
        return self._data

    @data.setter
    def data(self, value):
        """ Property to make sure that every entry is an instance of `ResourceEntry`. """
        self._data = [ResourceEntry(entry) for entry in value]


    # Basic inner workings
    def __len__(self):
        return len(self.data)

    def __getitem__(self, key):
        """ Multiple ways to get items from the table:
            - integer to get i-th entry from the table. Returns an instance of `ResourceEntry`
            - slice to get range of entries from the table. Returns an instance of `ResourceTable`
            - member of Resource enumeration or string alias to get column values. Returns list
            - list with bools of the same length, as the self to signal which entries to include.
            Returns an instance of `ResourceTable`
        """
        if isinstance(key, int):
            return self.data[key]

        if isinstance(key, slice):
            return ResourceTable(self.data[key])

        if isinstance(key, (str, Resource)):
            key = Resource.parse_alias(key)
            return [entry[key] for entry in self]

        # Iterable with bools
        if len(key) == len(self):
            return ResourceTable(data=[entry for entry, flag in zip(self, key) if flag])

        raise TypeError(f'Unsupported type {type(key)} for getitem!')

    @property
    def columns(self):
        """ List of present columns. """
        return None if len(self.data) == 0 else list(self.data[0].keys())

    def append(self, entry):
        """ Check if the `keys` of `entry` match columns of the table. Wrap with `ResourceEntry`, if needed. """
        entry_columns = list(entry.keys())

        if self.columns is not None:
            if set(self.columns) != set(entry_columns):
                raise ValueError('Trying to append entry with different set of columns!')

        entry = ResourceEntry(entry)
        self.data.append(entry)

    def maybe_copy(self, return_self):
        """ Inspired by Pandas. `return_self` coincides with `inplace` flag of the calling method. """
        return self if return_self else ResourceTable(self.data)


    # Logic
    def merge(self, other, self_key, other_key):
        """ Create a new `ResourceTable` with info merged from `self` and `other`,
        from entries where values of `self_key` and `other_key` columns match. All of the entries in `self` remain.
        If no matched entry present in `other`, values of additional columns are set to None.
        """
        # Assert
        if self_key not in self.columns:
            raise ValueError(f'Key `{self_key}` is not found in `self`!')
        if other_key not in other.columns:
            raise ValueError(f'Key `{other_key}` is not found in `other`!')

        for self_column in self.columns:
            for other_column in other.columns:
                if self_column == other_column:
                    raise ValueError(f'Column `{self_column}` present in both tables!')

        # Actual logic
        result = ResourceTable()
        template = {**{key : None for key in self.columns},
                    **{key : None for key in other.columns}}

        for self_entry in self:
            self_value = self_entry[self_key]
            flag = False

            for other_entry in other:
                other_value = other_entry[other_key]

                if self_value == other_value:
                    merged_entry = {**template, **self_entry, **other_entry}
                    result.append(merged_entry)
                    flag = True
            if flag is False:
                merged_entry = {**template, **self_entry}
                result.append(merged_entry)
        return result

    def update(self, other, self_key, other_key, inplace=True):
        """ Update `self` table with `other` table, matching entries on `self_key` and `other_key` columns.
        All of the columns in `other` should be present in `self`. All of the entries in `self` remain.
        """
        self = self.maybe_copy(return_self=inplace)

        # Assert
        if self_key not in self.columns:
            raise ValueError(f'Key `{self_key}` is not found in `self`!')
        if other_key not in other.columns:
            raise ValueError(f'Key `{other_key}` is not found in `other`!')

        if set(other.columns).intersection(set(self.columns)) != set(other.columns):
            difference = set(other.columns).difference(set(other.columns).intersection(set(self.columns)))
            raise ValueError(f'Columns of `other` should be a strict subset of `self` columns! Excess: {difference}')

        # Actual logic
        for self_entry in self:
            self_value = self_entry[self_key]
            for other_entry in other:
                if self_value == other_entry[other_key]:
                    self_entry.update(other_entry)
        return self

    def unroll(self, inplace=True):
        """ Unroll entries with sequence-values into multiple separate entries. """
        self = self.maybe_copy(return_self=inplace)

        unrolled = []
        for entry in self:
            lens = []
            for value in entry.values():
                if isinstance(value, list):
                    lens.append(len(value))

            if len(set(lens)) != 1:
                raise ValueError('Entry items have different lengths!')
            n = lens[0]

            if n == 0:
                new_entry = {key : (value if not isinstance(value, list) else None)
                            for key, value in entry.items()}
                unrolled.append(new_entry)
            else:
                for i in range(n):
                    new_entry = {key : (value if not isinstance(value, list) else value[i])
                                for key, value in entry.items()}
                    unrolled.append(new_entry)
        self.data = unrolled
        return self

    def sort(self, key, default=0.0, reverse=False, inplace=True):
        """ Sort the table based on `key`.

        Parameters
        ----------
        key : Resource, string or sequence of them
            Keys to sort on.
        default : number or sequence of numbers
            Default values to use instead of Nones.
        reverse : bool or sequence of bools
            Whether to use descending or ascending order of sort, individual for each key.
        inplace : bool
            Whether to return the same instance with changed data or a completely new instance.
        """
        self = self.maybe_copy(return_self=inplace)

        # Parse parameters into the similar list structure
        key = key if isinstance(key, (tuple, list)) else [key]
        default = default if isinstance(default, (tuple, list)) and len(default) == len(key) else [default] * len(key)
        reverse = reverse if isinstance(reverse, (tuple, list)) and len(reverse) == len(key) else [reverse] * len(key)
        def itemgetter(entry):
            result = []
            for key_, default_, reverse_ in zip(key, default, reverse):
                key_ = Resource.parse_alias(key_)
                sign = -1 if reverse_ is True else +1
                value = entry[key_] if entry[key_] is not None else default_
                result.append(sign * value)
            return tuple(result)

        self.data.sort(key=itemgetter)
        return self

    def filter(self, condition, inplace=True):
        """ Filter entries, based on `condition`. Keep only those which evaluate to True. """
        self = self.maybe_copy(return_self=inplace)
        self.data = [entry for entry in self if condition(entry)]
        return self


    # Work with index
    def set_index(self, index, inplace=True):
        """ Select a column as the index of the table. Stable sorts on unique values of the index.
        Under the hood, creates a list of unique values of chosen column to use in later methods.
        """
        self = self.maybe_copy(return_self=inplace)
        index_values = []
        for entry in self:
            value = entry[index]
            if value not in index_values:
                index_values.append(value)

        data = []
        for value in index_values:
            for entry in self:
                if entry[index] == value:
                    data.append(entry)

        self.data = data
        self.index = index
        self.index_values = index_values
        return self

    def _get_subtable(self, index_value):
        """ Extract subtable, corresponding to one of the current index values. """
        subtable = ResourceTable()
        for entry in self:
            if entry[self.index] == index_value:
                subtable.append(entry)
        return subtable

    def split_by_index(self):
        """ Split the table into a list of subtables, corresponding to unique index values. """
        subtables = []
        for index_value in self.index_values:
            subtable = self._get_subtable(index_value)
            subtables.append(subtable)

        return subtables

    def sort_by_index(self, key, default=0.0, reverse=False, inplace=True, aggregation=max):
        """ Sort unique index values, based on aggregated values of `key` columns in their subtables.
        Has the same semantics, as `sort` method.
        """
        self = self.maybe_copy(return_self=inplace)

        # Parse parameters into the similar list structure
        key = key if isinstance(key, (tuple, list)) else [key]
        default = default if isinstance(default, (tuple, list)) else [default] * len(key)
        reverse = reverse if isinstance(reverse, (tuple, list)) else [reverse] * len(key)
        aggregation = aggregation if isinstance(aggregation, (tuple, list)) else [aggregation] * len(key)

        def itemgetter(index_value):
            subtable = self._get_subtable(index_value)
            result = []

            for key_, default_, reverse_, aggregation_ in zip(key, default, reverse, aggregation):
                sign = -1 if reverse_ is True else +1
                value = subtable.aggregate(key=key_, default=default_, aggregation=aggregation_)
                result.append(sign * value)
            return tuple(result)

        self.index_values.sort(key=itemgetter)
        return self

    def filter_by_index(self, condition, inplace=True):
        """ Filter entries in subtables, based on `condition`. Keep only those which evaluate to True.
        Essentially, the same as `filter`, by also updates `index_values` list.
        """
        self = self.maybe_copy(return_self=inplace)

        data = []
        index_values = []
        for index_value, subtable in zip(self.index_values, self.split_by_index()):
            filtered_subtable = subtable.filter(condition=condition, inplace=False)
            if len(filtered_subtable) > 0:
                data.extend(subtable.data)
                index_values.append(index_value)

        self.data = data
        self.index_values = index_values
        return self

    def filter_on_index(self, condition, inplace=True):
        """ Filter subtables and index values, based on `condition`, evaluated on them.
        Keep only those which evaluate to True.
        """
        self = self.maybe_copy(return_self=inplace)

        data = []
        index_values = []
        for index_value, subtable in zip(self.index_values, self.split_by_index()):
            if condition(index_value, subtable):
                data.extend(subtable.data)
                index_values.append(index_value)

        self.data = data
        self.index_values = index_values
        return self

    def aggregate_by_index(self, key, default=0.0, aggregation=max):
        """ Get aggregates of `key` column for each index value. """
        result = []
        for subtable in self.split_by_index():
            value = subtable.aggregate(key=key, default=default, aggregation=aggregation)
            result.append(value)
        return result


    # Work with columns
    def apply(self, key, function):
        """ Apply `function` to a `key` column. """
        for entry in self:
            entry[key] = function(entry[key])

    def add_column(self, key, function):
        """ Apply `function` to each entry in the table and store as `key` column. """
        for entry in self:
            entry[key] = function(entry)

    def aggregate(self, key, default=0.0, aggregation=max):
        """ Apply `aggregation` to values from a `key`-column. `None` values are changed to `default`. """
        data = [(item if item is not None else default) for item in self[key]]
        return aggregation(data)


    # Display
    def __str__(self):
        return repr('\n'.join([str(entry) for entry in self.data]))

    def to_format_data(self, resource, terminal, process_memory_format, device_memory_format):
        """ Create a string template and data for a given `resource` column from entire table.
        Works by aggregation information in the `resource` column and making string from it.
        For more information about formatting refer to `ResourceTable.format` method.

        TODO: can actually create a `ResourceEntry` instance and use its `to_format_data` method.
        """
        _ = process_memory_format, device_memory_format

        template = '{0}'
        data = None

        if resource == Resource.DEVICE_SHORT_ID:
            data = self.aggregate(Resource.DEVICE_ID, default=None, aggregation=list)
            data = [str(item) for item in sorted(set(data)) if item is not None]
            data = ', '.join(data)

        if template is not None:
            template = template + terminal.normal
        if data is not None:
            data = data if isinstance(data, list) else [data]

        return template, data


    def format(self, terminal, formatter, aggregate=False,
               add_header=True, underline_header=True, bold_header=True, separate_header=True,
               add_separator=True, separator='-', hide_similar=True,
               process_memory_format='GB', device_memory_format='MB'):
        """ !!. """
        subtables = self.split_by_index()
        kwargs = {'process_memory_format' : process_memory_format,
                  'device_memory_format' : device_memory_format}

        lines = [[] for _ in range(1 + len(self))]
        for column_dict in formatter.included_only:
            # Retrieve parameters of the column display
            resource = column_dict['resource']
            hidable, min_width = column_dict.get('hidable', False), column_dict.get('min_width', 0)
            column_kwargs = {**kwargs, **{key : value for key, value in column_dict.items() if key != 'resource'}}

            styles, strings = [], []

            # Table header: names of the columns
            main_style, header_string = resource.to_format_data(terminal=terminal, **column_kwargs)
            if add_header:
                header_style = ''
                if 'TABLE_DELIMITER' not in resource.name:
                    header_style += (terminal.underline if underline_header else '')
                    header_style += (terminal.bold if bold_header else '')
                styles.append(header_style)
                strings.append(header_string)

            # Body of the table: add sublines for each table entry
            for subtable in subtables:
                for i, entry in enumerate(subtable):
                    style, string = entry.to_format_data(resource=resource, terminal=terminal, **column_kwargs)

                    # Changes based on the position of entry
                    if aggregate and i == 0:
                        remaining_table = subtable[1:]
                        style, string = remaining_table.to_format_data(resource=resource, terminal=terminal,
                                                                       **column_kwargs)
                    if hide_similar and hidable and i > 0:
                        style, string = '', ''

                    styles.append(style)
                    strings.append(string)

            # Modify header style
            if add_header:
                if len(styles) > 1:
                    styles[0] += terminal.bold * max(terminal.bold in style for style in styles)

            # Make every string the same width
            strings = [main_style + style + string + terminal.normal
                       for style, string in zip(styles, strings)]
            max_len = max(true_len(string) for string in strings)
            width = max(min_width, max_len)
            strings = [true_rjust(string, width) for string in strings]

            for line, string in zip(lines, strings):
                line.append(string)

        lines = [' '.join(line).rstrip() for line in lines]

        # Add separators between index values
        if add_separator or (add_header and separate_header):
            s, separator_indices = 1 if add_header else 0, []
            for subtable in subtables:
                separator_indices.append(s)
                s += len(subtable)

            if (add_header and separate_header) and add_separator:
                separator_indices = separator_indices[::-1]
            elif add_header and separate_header:
                separator_indices = separator_indices[:0]
            else:
                separator_indices = separator_indices[1:][::-1]

            separator = separator * true_len(lines[0])
            for idx in separator_indices:
                lines.insert(idx, separator)

        return lines


    # Pandas compatibility
    def to_pd(self):
        """ !!. """
        import pandas as pd #pylint: disable=import-outside-toplevel
        return pd.DataFrame(self.data)
