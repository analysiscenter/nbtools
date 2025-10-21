""" Controlling class for fetching tables with system information,
merging them into a view and displaying in a stream.
"""
import os
import re
import json
import time

import psutil
import requests
from blessed import Terminal

import pynvml

from .resource import Resource
from .resource_table import ResourceTable
from .utils import format_memory, pid_to_name, pid_to_ngid, FiniteList, true_len, true_rjust, true_center
from ..exec_notebook import get_exec_notebook_name



KERNEL_ID_SEARCHER   = re.compile('kernel-(.*).json').search
VSCODE_KEY_SEARCHER  = re.compile('key=b"(.*)"').search
SCRIPT_NAME_SEARCHER = re.compile('python.* (.*).py').search
RUN_NOTEBOOK_PATH_SEARCHER = re.compile('/tmp/.*.json.*--HistoryManager.hist_file=:memory:.*').search  # noqa: S108


class ResourceInspector:
    """ A class to controll the process of gathering information about system resources into ResourceTables,
    merging them into views, and formatting into nice colored strings.
    """
    # TODO: correct working with VSCode Jupyter Notebooks
    # TODO: make sure that everything works without sudo
    # TODO: add more fallbacks for unavailable resources
    # TODO: can add explicit __delete__ to call pynvml.nvmlShutdown(), if we ever have problems with that
    def __init__(self, formatter=None):
        self.formatter = formatter

        self._device_handles = None
        self._device_utils = None
        self.warnings = {}

        self._cache = {}
        self._v_position = 0

    @property
    def device_handles(self):
        """ Cached handles of NVIDIA devices. """
        if self._device_handles is None:
            pynvml.nvmlInit()
            n_devices = pynvml.nvmlDeviceGetCount()

            self._device_handles = {device_id : pynvml.nvmlDeviceGetHandleByIndex(device_id)
                                    for device_id in range(n_devices)}
        return self._device_handles

    @property
    def device_utils(self):
        """ Values of device utilization over time. """
        if self._device_utils is None:
            self._device_utils = {device_id : FiniteList(size=1000)
                                  for device_id in self.device_handles}
        return self._device_utils


    # Collect system resources into ResourceTables
    def get_device_table(self, formatter=None, window=20):
        """ Collect data about current device usage into two tables:
        one is indexed by device, the second is indexed by process on a device.

        Each value is collected only if requested by the current formatter.
        Device-wide values (like temperature and utilization) are reported for each process.

        As the slowest operation is getting device handles, we cache it inside the instance attributes.
        Note that this does nothing for a single query to this class.

        PIDs, reported by nvidia-smi, are from the host namespace and may (most probably) not
        exist in the container namespace. Currently, we don't have a reliable and not overly hacky way of matching it to
        a PID inside the container: we circumwent this problem in the `process_table`.
        """
        formatter = formatter or self.formatter
        device_table, device_process_table = ResourceTable(), ResourceTable()

        for device_id, handle in self.device_handles.items():
            device_name = pynvml.nvmlDeviceGetName(handle)
            device_name = device_name.decode() if isinstance(device_name, bytes) else device_name
            common_info = {Resource.DEVICE_ID : device_id,
                           Resource.DEVICE_NAME : device_name}

            # Inseparable device information like memory, temperature, power, etc. Request it only if needed
            if (formatter.get(Resource.DEVICE_UTIL, False) or
                formatter.get(Resource.DEVICE_UTIL_MA, False)):
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                common_info[Resource.DEVICE_UTIL] = utilization.gpu
                common_info[Resource.DEVICE_MEMORY_UTIL] = utilization.memory

                # Store values over requests to compute moving average of device utilization
                lst = self.device_utils[device_id]
                lst.append(utilization.gpu)
                common_info[Resource.DEVICE_UTIL_MA] = lst.get_average(size=window)

            if formatter.get(Resource.DEVICE_TEMP, False):
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                common_info[Resource.DEVICE_TEMP] = temperature

            if formatter.get(Resource.DEVICE_FAN, False):
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                common_info[Resource.DEVICE_FAN] = fan_speed

            if formatter.get(Resource.DEVICE_POWER_USED, False):
                power_used = pynvml.nvmlDeviceGetPowerUsage(handle)
                power_total = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle)

                common_info[Resource.DEVICE_POWER_USED] = power_used
                common_info[Resource.DEVICE_POWER_TOTAL] = power_total

            if (formatter.get(Resource.DEVICE_MEMORY_USED, False) or
                formatter.get(Resource.DEVICE_PROCESS_MEMORY_USED, False)):
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                common_info[Resource.DEVICE_MEMORY_USED] = memory.used
                common_info[Resource.DEVICE_MEMORY_TOTAL] = memory.total

            # Collect individual processes info, if needed. Save it to both tables: in one as list, in other separately
            device_info = {**common_info}
            processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            device_info.update({Resource.DEVICE_PROCESS_N : 0,
                                Resource.DEVICE_PROCESS_PID : [],
                                Resource.DEVICE_PROCESS_MEMORY_USED : []})

            if processes:
                for process in processes:
                    pid, process_memory = process.pid, process.usedGpuMemory

                    # Update the aggregate device info table
                    device_info[Resource.DEVICE_PROCESS_N] += 1
                    device_info[Resource.DEVICE_PROCESS_PID].append(pid)
                    device_info[Resource.DEVICE_PROCESS_MEMORY_USED].append(process_memory)

                    # Update the table with individual processes
                    device_process_info = {**common_info}
                    device_process_info[Resource.DEVICE_PROCESS_PID] = pid
                    device_process_info[Resource.DEVICE_PROCESS_MEMORY_USED] = process_memory
                    device_process_table.append(device_process_info)

            device_table.append(device_info)

        self._cache.update({
            'device_table': device_table,
            'device_process_table': device_process_table,
        })
        return device_table, device_process_table

    def get_notebook_table(self, formatter=None):
        """ Collect information about all running Jupyter Notebooks inside all of the Jupyter Servers.
        Works with both v2 and v3 APIs.

        The most valuable information from this table is the mapping from `kernel_id` to `path` and `name`: all of
        other properties of a process can be retrieved by looking at the process (see `get_process_table`).

        TODO: once VSCode has stable standard and doc for ipykernel launches, add its parsing here.
        """
        servers = []
        try:
            from notebook.notebookapp import list_running_servers as list_running_servers_v2
            servers.extend(list(list_running_servers_v2()))
        except ImportError:
            pass
        try:
            from jupyter_server.serverapp import list_running_servers as list_running_servers_v3
            servers.extend(list(list_running_servers_v3()))
        except ImportError:
            pass

        _ = formatter # currently, not used

        # Information about all running kernels for all running servers
        notebook_table = ResourceTable()
        for server in servers:
            root_dir = server.get('root_dir') or server.get('notebook_dir') # for v2 and v3
            response = requests.get(requests.compat.urljoin(server['url'], 'api/sessions'),
                                    params={'token': server.get('token', '')})

            for instance in json.loads(response.text):
                name = instance['notebook']['name']
                path = os.path.join(root_dir, instance['notebook']['path'])
                kernel_id = instance['kernel']['id']

                if not os.path.exists(path):
                    # VSCode notebooks use tmp files with mangled names
                    # Also, the path may be incorrect, and we can't fix that
                    name = '-'.join(name[:-6].split('-')[:-5]) + '.ipynb'
                    path = '-'.join(path[:-6].split('-')[:-10]) + '.ipynb'

                notebook_info = {
                    Resource.NAME : name,
                    Resource.PATH : path,
                    Resource.KERNEL : kernel_id,
                }
                notebook_table.append(notebook_info)

        self._cache['notebook_table'] = notebook_table
        return notebook_table

    def get_python_pids(self):
        """ PIDs of processes, which have `python` in its name. """
        python_pids = set()
        for pid in psutil.pids():
            name = pid_to_name(pid)
            if 'python' in name:
                python_pids.add(pid)
        return python_pids

    def get_process_table(self, formatter=None):
        """ Collect information about all Python processes.
        Information varies from process properties (its path, PID, NGID, status, etc) to system resource usage like
        CPU utilization or RSS. The table also includes some inferred columns like type and kernel_id.

        Some of the fields are intentionally left blank / with meaningless defaults: those are supposed to be filled by
        later merges / updates of the multiple tables. For example, processes that contain `kernel_id` in the name are
        matched on `kernel_id` with the result of `get_notebook_table` to fill in correct names and paths.

        If those fields are not updated with correct info, they would break table formatting: mainly, sorting and
        filtering. This is a good thing, as such occasions signal about something very wrong and unexpected.
        An example of this is an abandoned Jupyter Notebook, not managed by its Jupyter Server, or a host process, for
        some reasons visible inside the container.

        As `NBStat` can be run inside the container which has different namespace to the host, we are trying to match
        PIDs of the processes to the ones on the host. That is what the `NGID` column for: later we use
        either PIDs or NGIDs (whichever matches the DEVICE_PIDs) to merge with device information.
        This fallback should be easy to extend once we find new ways of inferring the host PID of a process.
        """
        formatter = formatter or self.formatter

        python_pids = self.get_python_pids()

        process_table = ResourceTable()
        for pid in python_pids:
            try:
                process = psutil.Process(pid)
                pid = process.pid

                with process.oneshot():
                    # Command used to start the Python interpreter
                    cmdline = ' '.join(process.cmdline())

                    # cwd with a default: access can be denied to current user
                    try:
                        cwd = process.cwd()
                    except psutil.AccessDenied:
                        cwd = ''

                    # Determine the type, name and path of the python process
                    kernel_id = KERNEL_ID_SEARCHER(cmdline)
                    vscode_key = VSCODE_KEY_SEARCHER(cmdline)
                    script_name = SCRIPT_NAME_SEARCHER(cmdline)
                    exec_notebook_path = RUN_NOTEBOOK_PATH_SEARCHER(cmdline)

                    if kernel_id:
                        # The name will be changed by data from `notebook_table`.
                        # If not, then something very fishy is going on.
                        type_ = 'notebook'
                        name = kernel_id.group(1).split('-')[0] + '.ipynb'
                        path = os.path.join(cwd, name)
                        kernel_id = kernel_id.group(1)
                    elif vscode_key:
                        # Can't tell much more for processes run by VSCode for now
                        type_ = 'vscode'
                        name = vscode_key.group(1).split('-')[0] + '.ipynb'
                        path = kernel_id = vscode_key.group(1)
                    elif exec_notebook_path:
                        type_ = 'exec_notebook'
                        name = get_exec_notebook_name(process.ppid())
                        path = os.path.join(cwd, name)
                        kernel_id = None
                    elif script_name:
                        type_ = 'script'
                        name = script_name.group(1) + '.py'
                        path = os.path.join(cwd, name)
                        kernel_id = None
                    else:
                        type_ = 'unknown'
                        name = 'unknown'
                        path = cwd
                        kernel_id = None

                    # PYTHON_PPID = PPID if parent is Python process else -1
                    ppid = process.ppid()
                    if type_ == 'exec_notebook':
                        # Spawned by `exec_notebook` function of the library
                        python_ppid = ppid
                    elif ppid in python_pids:
                        # Spawned by one of other Python processes
                        type_ = 'subprocess'
                        python_ppid = ppid
                    elif 'containerd' in pid_to_name(ppid):
                        # Something very wrong is going on
                        type_ = 'containerd'
                        python_ppid = ppid
                    else:
                        # Spawned by non-Python process: terminal / Jupyter Server
                        python_ppid = -1

                    # Fill in the basic info
                    process_info = {
                        Resource.NAME : name,
                        Resource.PATH : path,
                        Resource.CMDLINE : cmdline,
                        Resource.TYPE : type_,
                        Resource.PID : pid,
                        Resource.PPID : ppid,
                        Resource.NGID : pid_to_ngid(pid),
                        Resource.PYTHON_PPID : python_ppid,
                        Resource.CREATE_TIME : process.create_time(),
                        Resource.KERNEL : kernel_id,
                        Resource.STATUS : process.status(),
                        Resource.PROCESS : process
                    }

                    # Gather resource info
                    if formatter.get(Resource.CPU, False):
                        process_info[Resource.CPU] = process.cpu_percent()

                    if formatter.get(Resource.RSS, False):
                        memory = process.memory_info()
                        process_info[Resource.RSS] = memory.rss

                process_table.append(process_info)

            except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess, FileNotFoundError):
                continue

        # Postprocess the table: update some entries with info from the others
        for entry in process_table:
            if entry[Resource.NAME] == 'unknown' and 'multiprocess' in entry[Resource.CMDLINE]:
                ppid = entry[Resource.PPID]

                for entry_ in process_table:
                    if entry_[Resource.PID] == ppid and entry_[Resource.PYTHON_PPID] == -1:
                        entry.update({key : entry_[key] for key in [Resource.NAME, Resource.PATH, Resource.KERNEL]})

        self._cache['process_table'] = process_table
        return process_table


    # Aggregate multiple ResourceTables into more representative tables
    def make_nbstat_table(self, formatter=None, sort=True, verbose=0, window=20):
        """ Prepare a `nbstat` view: a table, indexed by script/notebook name, with info about each of its processes.

        Parameters
        ----------
        sort : bool
            If True, then the table is sorted in the following order:
                - notebook name, which is used as table index
                - for each notebook, we display its process as the first row
                - then all device processes, sorted by device ID
                - then all other processes, sorted by create time
        verbose : {0, 1, 2}
            Sets the filtration of the table.
            If 0, then we keep only notebooks, which use at least one device. For them we keep only device processes.
            If 1, then we keep only notebooks, which use at least one device. For them we keep all processes.
            If 2, then we keep all notebooks and all processes for them.
        """
        # Collect all the data
        _, device_process_table = self.get_device_table(formatter=formatter, window=window) # ~20% of the time taken
        notebook_table = self.get_notebook_table(formatter=formatter)                       # ~15% of the time taken
        process_table = self.get_process_table(formatter=formatter)                         # ~45% of the time taken

        # Try to match the process pids (local namespace) to device pids (host). Merge on those
        table = process_table
        if device_process_table:
            device_pids = device_process_table[Resource.DEVICE_PROCESS_PID]

            def select_pid(entry):
                pid = entry[Resource.PID]
                ngid = entry[Resource.NGID]
                result = ngid if ngid in device_pids else pid
                return result

            table.add_column(Resource.HOST_PID, select_pid)
            self.nbstat_check_device_pids(device_pids, table, add_to_table=True)

            table = ResourceTable.merge(table, device_process_table,
                                        self_key=Resource.HOST_PID, other_key=Resource.DEVICE_PROCESS_PID)

        # Update entries: change `path` and `name` for Notebook from placeholders to proper ones
        if notebook_table:
            table.update(notebook_table, self_key=Resource.KERNEL, other_key=Resource.KERNEL, inplace=True)

        # Custom sort for processes: parent -> device processes -> non-device processes -> create time
        if sort:
            is_parent = lambda entry: entry[Resource.PYTHON_PPID] == -1
            table.add_column(Resource.IS_PARENT, is_parent)

            table.sort(key=[Resource.IS_PARENT, Resource.DEVICE_ID, Resource.CREATE_TIME],
                       reverse=[True, False, False], default=[0.0, 999, 0.0])

        # Filter non-device processes
        if verbose == 0:
            function = lambda entry: (entry.get(Resource.DEVICE_ID) is not None or entry[Resource.PYTHON_PPID] == -1)
            table.filter(function, inplace=True)

        # Sort index on create time
        table.set_index(Resource.PATH, inplace=True)
        if sort:
            uses_device = lambda entry: entry.get(Resource.DEVICE_ID) is not None
            table.add_column(Resource.USES_DEVICE, uses_device)
            table.sort_by_index(key=(Resource.USES_DEVICE, Resource.CREATE_TIME),
                                reverse=[True, False], aggregation=[max, min])

        # Filter non-device notebooks
        if verbose <= 1:
            function = lambda entry: (entry.get(Resource.DEVICE_ID) is not None)
            table.filter_by_index(function, inplace=True)
        return table

    def make_devicestat_table(self, formatter=None, window=20):
        """ A transposed `nbstat` view: the same information, but indexed with device ids. """
        device_table, device_process_table = self.get_device_table(formatter=formatter, window=window)
        notebook_table = self.get_notebook_table(formatter=formatter)
        process_table = self.get_process_table(formatter=formatter)

        # Try to match the process pids (local namespace) to device pids (host). Merge on those
        device_pids = device_process_table[Resource.DEVICE_PROCESS_PID]
        def select_pid(entry):
            pid = entry[Resource.PID]
            ngid = entry[Resource.NGID]
            result = ngid if ngid in device_pids else pid
            return result
        process_table.add_column(Resource.HOST_PID, select_pid)

        table = device_table.unroll(inplace=False)
        if process_table:
            table = table.merge(process_table, self_key=Resource.DEVICE_PROCESS_PID, other_key=Resource.HOST_PID)

        # Update entries: change `path` and `name` for Notebook from placeholders to proper ones
        if notebook_table:
            table.update(notebook_table, self_key=Resource.KERNEL, other_key=Resource.KERNEL, inplace=True)

        self.devicestat_check_device_pids(table)

        # A simple sort of entries and index
        table.sort(key=Resource.CREATE_TIME, reverse=False)
        table.set_index(Resource.DEVICE_ID, inplace=True)
        table.sort_by_index(key=Resource.DEVICE_ID, aggregation=min)
        return table

    def make_gpustat_table(self, formatter=None, window=20):
        """ A device-only view. Same information, as vanilla `gpustat`. """
        device_table, _ = self.get_device_table(formatter=formatter, window=window)
        device_table.set_index(Resource.DEVICE_ID)
        return device_table


    # Check for information consistency in multiple tables
    def nbstat_check_device_pids(self, device_pids, table, add_to_table=True):
        """ Check if some of `device pids` are not referenced in the `table`.
        Add them with template names and values, if needed.
        """
        set_device_pids = set(device_pids)
        set_host_pids = set(table[Resource.HOST_PID])
        if None in set_device_pids:
            set_device_pids.pop(None)
        if None in set_host_pids:
            set_host_pids.pop(None)

        if set_device_pids != set_host_pids:
            missing_pids = set_device_pids.difference(set_host_pids)
            self.warnings['missing_device_pids'] = missing_pids

            if add_to_table:
                entry_template = {key : None for key in table.columns or []}
                for missing_pid in sorted(missing_pids):
                    name = 'non-python' if psutil.pid_exists(missing_pid) else 'device_zombie'

                    entry = {
                        **entry_template,
                        Resource.NAME : name,
                        Resource.TYPE : name,
                        Resource.PATH : name,
                        Resource.STATUS : 'sleeping',
                        Resource.PID : missing_pid,
                        Resource.PPID : missing_pid,
                        Resource.NGID : missing_pid,
                        Resource.HOST_PID : missing_pid,
                        Resource.PYTHON_PPID : missing_pid,
                        Resource.CREATE_TIME : missing_pid, # for sort on `CREATE_TIME`
                    }
                    table.append(entry)

    def devicestat_check_device_pids(self, table):
        """ Check if some of the `device pids` are not matched to any Python processes.
        Add template names to them instead of empty ones.
        """
        self.warnings['missing_device_pids'] = set()
        for entry in table:
            if entry[Resource.DEVICE_PROCESS_PID] is not None and entry[Resource.HOST_PID] is None:
                missing_pid = entry[Resource.DEVICE_PROCESS_PID]
                self.warnings['missing_device_pids'].add(missing_pid)

                name = 'non-python' if psutil.pid_exists(missing_pid) else 'device_zombie'
                entry.update({Resource.NAME : name,
                              Resource.TYPE : name,
                              Resource.PATH : name,
                              Resource.STATUS : 'sleeping'})

    # Make formatted visualization of tables
    def get_view(self, name='nbstat', formatter=None, index_condition=None, force_styling=True,
                 sort=True, verbose=0, window=20, interval=None,
                 add_header=True, underline_header=True, bold_header=False, separate_header=True,
                 separate_table=False,
                 add_footnote=False, underline_footnote=False, bold_footnote=True,
                 add_help=False, underline_help=False, bold_help=True,
                 use_cache=False,
                 vertical_change=0,
                 separate_index=True, separator='—', hide_similar=True,
                 process_memory_format='GB', device_memory_format='MB'):
        """ Get the desired view. Format it into colored string.
        Optionally, add a supheader (driver and CUDA info) and a footnote (total CPU / RSS usage) to the visualization.
        """
        formatter = formatter or self.formatter

        # Get the table from cache or re-compute it
        if use_cache and self.cache_available(name=name, formatter=formatter, verbose=verbose,
                                              interval=interval * 0.8):
            table = self._cache['table']
        else:
            # Compute the table
            if name.startswith('nb'):
                table = self.make_nbstat_table(formatter=formatter, sort=sort, verbose=verbose, window=window)
            elif name.startswith('device'):
                table = self.make_devicestat_table(formatter=formatter, window=window)
            elif name.startswith('gpu'):
                table = self.make_gpustat_table(formatter=formatter, window=window)
            else:
                raise ValueError('Wrong name of view to get!')

            # Filter some processes
            if 'nb' in name and table:
                bad_names = ['lsp_server']
                function = lambda index_value, _: not any(name in index_value for name in bad_names)
                table.filter_on_index(function, inplace=True)

            # Filter index of the table by a regular expression
            if table and index_condition is not None:
                function = lambda index_value, _: bool(re.search(index_condition, str(index_value)))
                table.filter_on_index(function, inplace=True)

            # Store the table into cache along with the parameters of its creation
            self._cache.update({
                'table': table,
                'time': time.time(),
                'parameters': {
                    'name': name,
                    'n_formatter': sum(int(column['include']) for column in formatter),
                    'sort': sort,
                    'verbose': verbose,
                }
            })

        # Create terminal instance
        terminal = self.make_terminal(force_styling=force_styling, separator=separator)

        # Make formatted strings
        lines = table.format(terminal=terminal, formatter=formatter,
                             add_header=add_header, underline_header=underline_header, bold_header=bold_header,
                             separate_header=separate_header,
                             separate_index=separate_index, hide_similar=hide_similar,
                             process_memory_format=process_memory_format, device_memory_format=device_memory_format)

        # Placeholder for empty table
        if not table:
            width = terminal.length(lines[-1])
            placeholder = terminal.center(terminal.bold + '---no entries to display---' + terminal.normal, width)
            lines.insert(1, placeholder)

        # Additional line elements: separator, footnote, help
        if separate_table:
            separator = terminal.bold + '-' * terminal.length(lines[0])
            lines.append(separator)

        if add_footnote:
            lines = self.add_footnote(lines, terminal=terminal,
                                      underline=underline_footnote, bold=bold_footnote,
                                      process_memory_format=process_memory_format)

        if add_help:
            lines = self.add_help(lines, terminal=terminal, name=name,
                                  underline=underline_help, bold=bold_help)

        # Select visible lines: keep header / footnote+help, move just the index items
        if 'watch' in name:
            v_start = int(add_header) + int(separate_header)
            v_end = int(separate_table) + 2*int(add_footnote) + 2*int(add_help)
            v_size = terminal.height - v_start - v_end - 5

            self._v_position = max(0, min(self._v_position + vertical_change, len(lines) - v_start - v_end - v_size))
            v_slice_start = v_start + self._v_position
            v_slice_end = v_slice_start + v_size
            if len(lines) > terminal.height:
                lines = lines[:v_start] + lines[v_slice_start : v_slice_end] + lines[-(v_end or 1):]

        return '\n'.join(lines) + terminal.normal


    def cache_available(self, name, formatter, verbose, interval):
        """ Check if the stored cache is fresh enough to re-use it. """
        if not self._cache or 'table' not in self._cache:
            return False

        if time.time() - self._cache['time'] > interval:
            return False

        if name != self._cache['parameters']['name']:
            return False

        if verbose != self._cache['parameters']['verbose']:
            return False

        n_formatter = sum(int(column['include']) for column in formatter)
        if n_formatter != self._cache['parameters']['n_formatter']:
            return False

        return True


    def make_terminal(self, force_styling, separator):
        """ Create terminal instance. """
        terminal = Terminal(kind=os.getenv('TERM'), force_styling=force_styling if force_styling else None)
        terminal.separator_symbol = separator
        terminal._normal = '\x1b[0;10m'  # noqa: SLF001

        # Change some methods to a faster versions
        # TODO: better measurements and tests for the same outputs
        terminal.length = true_len
        terminal.rjust = true_rjust
        terminal.center = true_center
        return terminal

    def add_line(self, lines, parts, terminal, position, separator_position, underline, bold):
        """ Add line, created from joined `parts`, to `lines`, in desired `position`. """
        parts = [part for part in parts if part]
        if underline:
            parts = [terminal.underline + part for part in parts]
        if bold:
            parts = [terminal.bold + part for part in parts]
        parts = [part + terminal.normal for part in parts]
        added_line = '    '.join(parts)

        added_line_width = terminal.length(added_line)
        table_width = terminal.length(lines[0])

        if added_line_width <= table_width:
            added_line = terminal.rjust(added_line, table_width)
        else:
            lines = [terminal.rjust(line, added_line_width) for line in lines]
        lines.insert(position, added_line)

        if separator_position is not None:
            lines.insert(separator_position, terminal.separator_symbol * terminal.length(added_line))
        return lines


    def add_footnote(self, lines, terminal, underline=True, bold=True, process_memory_format='GB'):
        """ Add a footnote with info about current CPU, RSS and GPU usage. """
        # N running notebooks, number of used devices
        parts = []

        if 'notebook_table' in self._cache:
            n_notebooks = len(self._cache['notebook_table'])
            parts.append(f'{terminal.pink}# KERNELS: {n_notebooks:>3}')

        if 'device_table' in self._cache:
            n_used_devices = sum(bool(entry[Resource.DEVICE_PROCESS_N]) for entry in self._cache['device_table'])
            n_total_devices = len(self._cache['device_table'])
            parts.append(f'{terminal.green}DEVICES USED: {n_used_devices} / {n_total_devices}')

        if parts:
            lines = self.add_line(lines=lines, parts=parts, terminal=terminal,
                                position=len(lines), separator_position=None,
                                underline=underline, bold=bold)

        # System info
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        vm = psutil.virtual_memory()
        vm_used, unit = format_memory(vm.used, process_memory_format)
        vm_total, unit = format_memory(vm.total, process_memory_format)
        n_digits = len(str(vm_total))

        parts = [
            timestamp,
            f'CPU: {psutil.cpu_percent():6}%',
            f'RSS: {vm_used:>{n_digits}} / {vm_total} {unit}',
        ]
        parts = [terminal.cyan + part for part in parts]

        lines = self.add_line(lines=lines, parts=parts, terminal=terminal,
                              position=len(lines), separator_position=None,
                              underline=underline, bold=bold)

        return lines

    def add_help(self, lines, terminal, name, underline=True, bold=True):
        """ Add a footnote with info about current CPU and RSS usage. """
        # General controls
        parts = [
            'TAB: SWITCH VIEWS',
            'V: VERBOSITY' if 'nb' in name else None,
            'S: SEPARATORS',
            # 'B: BARS',
            # 'M: MOVING AVGS',
            'R: RESET',
            'Q: QUIT'
        ]
        parts = ['    '.join([part for part in parts if part])]

        lines = self.add_line(lines=lines, parts=parts, terminal=terminal,
                              position=len(lines), separator_position=None,
                              underline=underline, bold=bold)

        # F-buttons: column controls
        parts = []
        resource_and_color = [
            (1, 'PID', terminal.on_magenta),
            (2, 'PPID', terminal.on_magenta),
            (3, 'CPU', terminal.on_cyan),
            (4, 'RSS', terminal.on_cyan),
            (5, 'DEVICE', terminal.on_blue),
            (6, 'MEMORY', terminal.on_yellow),
            (7, 'UTIL', terminal.on_green),
            (8, 'TEMP', terminal.on_red),
        ]

        for f, name_, color in resource_and_color:
            parts.append(f'{terminal.bold}{color}F{f}: {name_}{terminal.normal}')
        parts = ['  '.join(parts)]


        lines = self.add_line(lines=lines, parts=parts, terminal=terminal,
                              position=len(lines), separator_position=None,
                              underline=underline, bold=False)
        return lines
