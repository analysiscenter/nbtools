""" !!. """
from datetime import datetime

from .resource import Resource, parse_alias
from .utils import format_memory, true_len, true_rjust

class ResourceEntry(dict):
    """ !!. """
    def __getitem__(self, key):
        key = parse_alias(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        key = parse_alias(key)
        return super().get(key, default)

    def to_format_data(self, resource, terminal, process_memory_format, device_memory_format):
        """ !!. """
        resource = parse_alias(resource)
        template = '{0}'
        data = self.get(resource, None)

        # Process description
        if resource == Resource.PY_NAME:
            template = terminal.bold + '{0}'

        elif resource in [Resource.PY_TYPE, Resource.PY_PID, Resource.PY_SELFPID, Resource.PY_STATUS]:
            template = terminal.white + '{0}'

        elif resource == Resource.PY_CREATE_TIME:
            template = terminal.white + '{0}'
            data = datetime.fromtimestamp(data).strftime("%Y-%m-%d %H:%M:%S")

        elif resource == Resource.PY_KERNEL:
            template = terminal.white + '{0}'
            data = data.split('-')[0] if data is not None else 'N/A'

        # Process resources
        elif resource == Resource.PY_RSS:
            template = terminal.bold + terminal.cyan + '{0}'
            if data is not None:
                rounded, unit = format_memory(data, format=process_memory_format)
                data = f'{rounded} {unit}'

        # Device description
        elif resource == Resource.DEVICE_ID:
            template = (terminal.bold + terminal.blue + '{0}' + terminal.normal) + (terminal.cyan + ' [{1}]')
            if data is not None:
                device_name = (self[Resource.DEVICE_NAME].replace('NVIDIA', '').replace('RTX', '')
                               .replace('  ', ' ').strip())
                data = [device_name, data]

        elif resource == Resource.DEVICE_SHORT_ID:
            template = terminal.blue + '[{0}]'
            data = self[Resource.DEVICE_ID]

        # Device resources
        elif resource == Resource.DEVICE_MEMORY_USED:
            template = terminal.yellow + '{0}' + terminal.normal + terminal.bold + '{1}'

            if data is not None:
                if data > 10*1024*1024:
                    template = terminal.bold + template

                used, unit = format_memory(data, format=device_memory_format)
                total, unit = format_memory(self[Resource.DEVICE_MEMORY_TOTAL], format=device_memory_format)

                n_digits = len(str(total))
                data = [f'{used:>{n_digits}}/{total}', ' ' + unit]

        elif resource == Resource.DEVICE_PROCESS_MEMORY_USED:
            template = terminal.yellow + '{0}' + terminal.normal + terminal.bold + '{1}'

            if data is not None:
                if data > 10*1024*1024:
                    template = terminal.bold + template

                used_process, unit = format_memory(data, format=device_memory_format)
                used_device, unit = format_memory(self[Resource.DEVICE_MEMORY_USED], format=device_memory_format)
                total, _ = format_memory(self[Resource.DEVICE_MEMORY_TOTAL], format=device_memory_format)

                n_digits = len(str(total))
                data = [f'{used_process:>{n_digits}}/{max(used_device, used_process):>{n_digits}}/{total}', ' ' + unit]

        elif resource == Resource.DEVICE_POWER_USED:
            template = terminal.magenta + '{0}'

            if data is not None:
                power_used = data // 1000
                power_total = self[Resource.DEVICE_POWER_TOTAL] // 1000
                data = f'{power_used:>3}/{power_total:>3} W'

        elif resource == Resource.DEVICE_UTIL:
            template = terminal.green + '{0}'
            if data is not None:
                if data > 30:
                    template = terminal.bold + template
                data = f'{data}%' # don't use the `％` symbol as it is not unit wide

        elif resource == Resource.DEVICE_TEMP:
            template = terminal.red + '{0}'
            if data is not None:
                if data > 30:
                    template = terminal.bold + template
                data = f'{data}°C' # don't use the `℃` symbol as it is not unit wide

        # Delimiters
        elif resource == Resource.DELIMITER1:
            data = '|'
        elif resource == Resource.DELIMITER2:
            data = '||'

        template = template + terminal.normal
        data = data if data is not None else (['N/A'] + [''] * 4)
        data = data if isinstance(data, list) else [data]
        return template, data


class ResourceTable:
    """ !!. """
    #pylint: disable=self-cls-assignment
    def __init__(self, data=None):
        self._data = [] if data is None else [ResourceEntry(entry) for entry in data]

    @property
    def data(self):
        """ !!. """
        return self._data

    @data.setter
    def data(self, value):
        self._data = [ResourceEntry(entry) for entry in value]


    # Basic inner workings
    def __len__(self):
        return len(self.data)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key]

        if isinstance(key, slice):
            return ResourceTable(self.data[key])

        if isinstance(key, (str, Resource)):
            key = parse_alias(key)
            return [entry[key] for entry in self]

        # Iterable with bools
        if len(key) == len(self):
            return ResourceTable(data=[entry for entry, flag in zip(self, key) if flag])

        raise TypeError(f'Unsupported type {type(key)} for getitem!')

    def aggregate(self, key, default=0.0, aggregation=max):
        """ !!. """
        data = [(item if item is not None else default) for item in self[key]]
        return aggregation(data)

    @property
    def columns(self):
        """ !!. """
        return None if len(self.data) == 0 else list(self.data[0].keys())

    def append(self, entry):
        """ !!. """
        entry_columns = list(entry.keys())

        if self.columns is not None:
            if set(self.columns) != set(entry_columns):
                raise ValueError('Trying to append entry with different set of columns!')

        entry = ResourceEntry(entry)
        self.data.append(entry)

    def maybe_copy(self, return_self):
        """ Inspired by Pandas. """
        return self if return_self else ResourceTable(self.data)


    # Logic
    def merge(self, other, self_key, other_key):
        """ Create a new `ResourceTable` with info merged from `self` and `other`, based on `key`. """
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
        """ !!. """
        self = self.maybe_copy(return_self=inplace)

        # Assert
        if self_key not in self.columns:
            raise ValueError(f'Key `{self_key}` is not found in `self`!')
        if other_key not in other.columns:
            raise ValueError(f'Key `{other_key}` is not found in `other`!')

        # Actual logic
        for self_entry in self:
            self_value = self_entry[self_key]
            for other_entry in other:
                if self_value == other_entry[other_key]:
                    self_entry.update(other_entry)
        return self

    def unroll(self, inplace=True):
        """ !!. """
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
        """ !!. """
        self = self.maybe_copy(return_self=inplace)

        # Parse parameters into the similar list structure
        key = key if isinstance(key, (tuple, list)) else [key]
        default = default if isinstance(default, (tuple, list)) and len(default) == len(key) else [default] * len(key)
        reverse = reverse if isinstance(reverse, (tuple, list)) and len(reverse) == len(key) else [reverse] * len(key)
        def itemgetter(entry):
            result = []
            for key_, default_, reverse_ in zip(key, default, reverse):
                key_ = parse_alias(key_)
                sign = -1 if reverse_ is True else +1
                value = entry[key_] if entry[key_] is not None else default_
                result.append(sign * value)
            return tuple(result)

        self.data.sort(key=itemgetter)
        return self

    def filter(self, condition, inplace=True):
        """ !!. """
        self = self.maybe_copy(return_self=inplace)
        self.data = [entry for entry in self if condition(entry)]
        return self


    # Work with index
    def set_index(self, index, inplace=True):
        """ !!. """
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
        subtable = ResourceTable()
        for entry in self:
            if entry[self.index] == index_value:
                subtable.append(entry)
        return subtable

    def split_by_index(self):
        """ !!. """
        subtables = []
        for index_value in self.index_values:
            subtable = self._get_subtable(index_value)
            subtables.append(subtable)

        return subtables

    def sort_by_index(self, key, default=0.0, reverse=False, inplace=True, aggregation=max):
        """ !!. """
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
        """ !!. """
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

    def aggregate_by_index(self, key, default=0.0, aggregation=max):
        """ !!. """
        result = []
        for subtable in self.split_by_index():
            value = subtable.aggregate(key=key, default=default, aggregation=aggregation)
            result.append(value)
        return result

    # Display
    def __str__(self):
        return repr('\n'.join([str(entry) for entry in self.data]))

    def to_format_data(self, resource, terminal, process_memory_format, device_memory_format):
        """ !!. """
        _ = process_memory_format, device_memory_format

        template = None
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
        default_data = [''] * 5
        subtables = self.split_by_index()

        lines = [[] for _ in range(1 + len(self))]
        for column in formatter.included_only:
            # Retrieve parameters of the column display
            resource = column['resource']
            hidable = column.get('hidable', False)
            min_width = column.get('min_width', 0)

            templates, data = [], []

            # Table header: names of the columns
            if add_header:
                header_template, header_data = resource.to_format_data(terminal=terminal,
                                                                    process_memory_format=process_memory_format,
                                                                    device_memory_format=device_memory_format)
                templates.append(header_template)
                data.append(header_data)

            # Body of the table: add sublines for each table entry
            for subtable in subtables:
                for i, entry in enumerate(subtable):
                    template, data_ = entry.to_format_data(resource=resource, terminal=terminal,
                                                           process_memory_format=process_memory_format,
                                                           device_memory_format=device_memory_format)

                    if aggregate and i == 0:
                        remaining_table = subtable[1:]
                        template_, data__ = remaining_table.to_format_data(resource=resource, terminal=terminal,
                                                                           process_memory_format=process_memory_format,
                                                                           device_memory_format=device_memory_format)
                        template = template_ if template_ is not None else template
                        data_ = data__ if data__ is not None else data_

                    if hide_similar and hidable and i > 0:
                        template = '{0}'
                        data_ = default_data

                    templates.append(template)
                    data.append(data_)

            # Modify header template to match the templates of rows
            if add_header:
                if templates[0] is None:
                    templates[0] = max(templates[1:], key=len)
                if 'DELIMITER' not in resource.name:
                    if underline_header:
                        templates[0] = terminal.underline + templates[0]
                    if bold_header:
                        templates[0] = terminal.bold + templates[0]

            # Make every subline the same width
            substrings = [template.format(*data_, *default_data) for template, data_ in zip(templates, data)]
            max_len = max(true_len(substring) for substring in substrings)
            width = max(min_width, max_len)
            substrings = [true_rjust(substring, width) for substring in substrings]

            for line, substring in zip(lines, substrings):
                line.append(substring)

        lines = [' '.join(line).rstrip() for line in lines]

        # Add separators between index values
        if add_separator or separate_header:
            s, separator_indices = 1 if add_header else 0, []
            for subtable in subtables:
                separator_indices.append(s)
                s += len(subtable)

            if separate_header and add_separator:
                separator_indices = separator_indices[::-1]
            elif separate_header:
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
