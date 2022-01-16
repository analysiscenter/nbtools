""" !!. """
import os
import re
import json
import time
import platform

import psutil
import requests

import nvidia_smi

from .resource import Resource
from .resource_table import ResourceTable
from .utils import COLORS, true_len, true_rjust


KERNEL_ID_SEARCHER   = re.compile('kernel-(.*).json').search
SCRIPT_NAME_SEARCHER = re.compile('python.* (.*).py').search



def pid_to_name_generic(pid):
    """ !!. """
    try:
        process = psutil.Process(pid)
        name = process.name()
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
        name = ''
    return name

def pid_to_name_linux(pid):
    """ !!.
    ~20% speed-up, compared to the `psutil` version.
    """
    try:
        with open(f'/proc/{pid}/status') as file:
            name = file.readline().split()[1]
    except Exception: #pylint: disable=broad-except
        name = ''
    return name

pid_to_name = pid_to_name_linux if platform.system() == 'Linux' else pid_to_name_generic


class ResourceInspector:
    """ !!. """
    def __init__(self, formatter):
        self.formatter = formatter
        self._device_handles = None

        self.pid_to_process = {}

    @property
    def device_handles(self):
        """ !!. """
        if self._device_handles is None:
            nvidia_smi.nvmlInit()
            n_devices = nvidia_smi.nvmlDeviceGetCount()

            self._device_handles = {device_id : nvidia_smi.nvmlDeviceGetHandleByIndex(device_id)
                                    for device_id in range(n_devices)}
        return self._device_handles


    # Collect system resources into ResourceTables
    def get_device_table(self, inspect_processes=True):
        """ !!. """
        device_table, device_process_table = ResourceTable(), ResourceTable()

        for device_id, handle in self.device_handles.items():
            common_info = {Resource.DEVICE_ID : device_id,
                           Resource.DEVICE_NAME : nvidia_smi.nvmlDeviceGetName(handle).decode()}

            # Inseparable device information like memory, temperature, power, etc. Request it only if needed
            if self.formatter.get(Resource.DEVICE_UTIL, False):
                utilization = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                common_info[Resource.DEVICE_UTIL] = utilization.gpu
                common_info[Resource.DEVICE_MEMORY_UTIL] = utilization.memory

            if self.formatter.get(Resource.DEVICE_TEMP, False):
                temperature = nvidia_smi.nvmlDeviceGetTemperature(handle, nvidia_smi.NVML_TEMPERATURE_GPU)
                common_info[Resource.DEVICE_TEMP] = temperature

            if self.formatter.get(Resource.DEVICE_FAN, False):
                fan_speed = nvidia_smi.nvmlDeviceGetFanSpeed(handle)
                common_info[Resource.DEVICE_FAN] = fan_speed

            if self.formatter.get(Resource.DEVICE_POWER_USED, False):
                power_used = nvidia_smi.nvmlDeviceGetPowerUsage(handle)
                power_total = nvidia_smi.nvmlDeviceGetEnforcedPowerLimit(handle)

                common_info[Resource.DEVICE_POWER_USED] = power_used
                common_info[Resource.DEVICE_POWER_TOTAL] = power_total

            if (self.formatter.get(Resource.DEVICE_MEMORY_USED, False) or
                self.formatter.get(Resource.DEVICE_PROCESS_MEMORY_USED, False)):
                memory = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                common_info[Resource.DEVICE_MEMORY_USED] = memory.used
                common_info[Resource.DEVICE_MEMORY_TOTAL] = memory.total

            # Collect individual processes info, if needed. Save it to both tables: in one as list, in other separately
            device_info = {**common_info}
            if inspect_processes: # TODO: can be computed from `formatter` instead of parameter
                processes = nvidia_smi.nvmlDeviceGetComputeRunningProcesses(handle)
                device_info.update({Resource.DEVICE_PROCESS_N : 0,
                                    Resource.DEVICE_PROCESS_PID : [],
                                    Resource.DEVICE_PROCESS_MEMORY_USED : []})
                if processes:

                    for process in processes:
                        pid, process_memory = process.pid, process.usedGpuMemory

                        # Update the aggregate device info
                        device_info[Resource.DEVICE_PROCESS_N] += 1
                        device_info[Resource.DEVICE_PROCESS_PID].append(pid)
                        device_info[Resource.DEVICE_PROCESS_MEMORY_USED].append(process_memory)

                        # Information about each individual process
                        device_process_info = {**common_info}
                        device_process_info[Resource.DEVICE_PROCESS_PID] = pid
                        device_process_info[Resource.DEVICE_PROCESS_MEMORY_USED] = process_memory
                        device_process_table.append(device_process_info)

            device_table.append(device_info)
        return device_table, device_process_table if inspect_processes else None

    def get_notebook_table(self):
        """ !!. """
        #pylint: disable=import-outside-toplevel
        # !!.
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

        # Information about all running kernels
        notebook_table = ResourceTable()
        for server in servers:
            root_dir = server.get('root_dir') or server.get('notebook_dir') # for v2 and v3
            response = requests.get(requests.compat.urljoin(server['url'], 'api/sessions'),
                                    params={'token': server.get('token', '')})

            for instance in json.loads(response.text):
                kernel_id = instance['kernel']['id']
                notebook_info = {
                    Resource.PY_NAME : instance['notebook']['name'],
                    Resource.PY_PATH : os.path.join(root_dir, instance['notebook']['path']),
                    Resource.PY_KERNEL : kernel_id,
                }
                notebook_table.append(notebook_info)
        return notebook_table

    def get_python_pids(self):
        """ !!. """
        python_pids = set()
        for pid in psutil.pids():
            name = pid_to_name(pid)
            if 'python' in name:
                python_pids.add(pid)
        return python_pids

    def get_process_table(self):
        """ !!. """
        python_pids = self.get_python_pids()

        process_table = ResourceTable()
        for pid in python_pids:
            try:
                if pid not in self.pid_to_process:
                    self.pid_to_process[pid] = psutil.Process(pid)
                process = self.pid_to_process[pid]

                with process.oneshot():
                    # Command used to start the Python interpreter
                    cmdline = ' '.join(process.cmdline())

                    # Determine the type, name and path of the python process
                    kernel_id = KERNEL_ID_SEARCHER(cmdline)
                    if kernel_id:
                        type_ = 'notebook'
                        name = None
                        path = None
                        kernel_id = kernel_id.group(1)
                        status = process.status()

                    else:
                        script_name = SCRIPT_NAME_SEARCHER(cmdline)
                        if script_name:
                            type_ = 'script'
                            name = script_name.group(1) + '.py'
                            path = os.path.join(process.cwd(), name)
                            kernel_id = None
                            status = process.status()
                        else:
                            type_ = 'unknown'
                            name = 'unknown'
                            path = process.cwd()
                            kernel_id = None
                            status = process.status()

                    ppid = process.ppid()
                    if ppid in python_pids:
                        type_ += '-subprocess'
                        selfpid = ppid
                    else:
                        selfpid = process.pid

                    # Fill in the basic info
                    process_info = {
                        Resource.PY_PID : process.pid,
                        Resource.PY_SELFPID : selfpid,
                        Resource.PY_TYPE : type_,
                        Resource.PY_NAME : name,
                        Resource.PY_PATH : path,
                        Resource.PY_CREATE_TIME : process.create_time(),
                        Resource.PY_KERNEL : kernel_id,
                        Resource.PY_STATUS : status,
                        Resource.PY_PROCESS : process
                    }

                    if self.formatter.get(Resource.PY_CPU, False):
                        process_info[Resource.PY_CPU] = process.cpu_percent()

                    if self.formatter.get(Resource.PY_RSS, False):
                        memory = process.memory_info()
                        process_info[Resource.PY_RSS] = memory.rss

                process_table.append(process_info)

            except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess, FileNotFoundError):
                continue
        return process_table


    # Aggregate multiple ResourceTables into more representative tables
    def get_nbstat_table(self, sort=True, only_device_processes=True, at_least_one_device=True):
        """ !!. """
        #
        _, device_process_table = self.get_device_table(True)
        notebook_table = self.get_notebook_table()
        process_table = self.get_process_table()

        #
        table = process_table
        if device_process_table:
            table = ResourceTable.merge(table, device_process_table,
                                        self_key=Resource.PY_PID, other_key=Resource.DEVICE_PROCESS_PID)
        if notebook_table:
            table.update(notebook_table, self_key=Resource.PY_KERNEL, other_key=Resource.PY_KERNEL, inplace=True)


        if sort:
            # Custom sort for nbview. Create multiple flags for sorting
            is_parent = lambda entry: entry[Resource.PY_PID] == entry[Resource.PY_SELFPID]
            table.add_column('is_parent', is_parent)

            has_device = lambda entry: entry[Resource.DEVICE_ID] is not None
            table.add_column('has_device', has_device)

            table.sort(key=['is_parent', 'has_device', Resource.PY_CREATE_TIME],
                       reverse=[True, True, False])

        if only_device_processes:
            if device_process_table:
                function = lambda entry: (entry[Resource.DEVICE_ID] is not None or \
                                          entry[Resource.PY_PID] == entry[Resource.PY_SELFPID])
                table.filter(function, inplace=True)
            else:
                table = ResourceTable()

        #
        table.set_index(Resource.PY_PATH, inplace=True)
        if sort:
            table.sort_by_index(key=Resource.PY_CREATE_TIME, aggregation=sum)
        if device_process_table and at_least_one_device:
            function = lambda entry: (entry[Resource.DEVICE_ID] is not None)
            table.filter_by_index(function, inplace=True)
        return table

    def get_gpustat_table(self):
        """ !!. """
        device_table, _ = self.get_device_table(True)
        device_table.set_index(Resource.DEVICE_ID)
        return device_table

    def get_devicestat_table(self):
        """ !!. """
        device_table, _ = self.get_device_table(True)
        notebook_table = self.get_notebook_table()
        process_table = self.get_process_table()

        table = device_table.unroll(inplace=False)
        table = table.merge(process_table, self_key=Resource.DEVICE_PROCESS_PID, other_key=Resource.PY_PID)

        if notebook_table:
            table.update(notebook_table, self_key=Resource.PY_KERNEL, other_key=Resource.PY_KERNEL, inplace=True)

        table.sort(key=Resource.PY_CREATE_TIME, reverse=False)
        table.set_index(Resource.DEVICE_ID, inplace=True)
        table.sort_by_index(key=Resource.DEVICE_ID, aggregation=min)
        return table


    # Make formatted visualization of tables
    def add_supheader(self, lines, terminal, underline=True, bold=True, separate=True):
        """ !!. """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        driver_version = '.'.join(nvidia_smi.nvmlSystemGetDriverVersion().decode().split('.')[:-1])
        cuda_version = nvidia_smi.nvmlSystemGetNVMLVersion().decode()[:4]
        supheader = f'{timestamp}   Driver Version: {driver_version}   CUDA Version:{cuda_version}'

        if underline:
            supheader = terminal.underline + supheader
        if bold:
            supheader = terminal.bold + supheader
        supheader = supheader + terminal.normal

        supheader_width = true_len(supheader)
        table_width = true_len(lines[0])

        if supheader_width <= table_width:
            supheader = true_rjust(supheader, table_width)
        else:
            lines = [true_rjust(line, supheader_width) for line in lines]
        lines.insert(0, supheader)

        if separate:
            lines.insert(1, '-' * true_len(supheader))
        return lines

    def get_view(self, name='nbstat', terminal=None, index_condition=None,
                 sort=True, only_device_processes=True, at_least_one_device=True,
                 add_supheader=True, underline_supheader=True, bold_supheader=True, separate_supheader=True,
                 add_header=True, underline_header=True, bold_header=False, separate_header=True,
                 aggregate=False, add_separator=True, separator='-', hide_similar=True,
                 process_memory_format='GB', device_memory_format='MB'):
        """ !!. """
        if name.startswith('nb'):
            table = self.get_nbstat_table(sort=sort, only_device_processes=only_device_processes,
                                          at_least_one_device=at_least_one_device)
        elif name.startswith('device'):
            table = self.get_devicestat_table()
        elif name.startswith('gpu'):
            table = self.get_gpustat_table()
        else:
            raise ValueError('Wrong name of view to get!')

        if table and index_condition is not None:
            function = lambda index_value, _: bool(re.search(index_condition, str(index_value)))
            table.filter_on_index(function, inplace=True)

        terminal = terminal or COLORS
        lines = table.format(terminal=terminal, formatter=self.formatter, aggregate=aggregate,
                             add_header=add_header, underline_header=underline_header,
                             bold_header=bold_header, separate_header=separate_header,
                             add_separator=add_separator, separator=separator, hide_similar=hide_similar,
                             process_memory_format=process_memory_format, device_memory_format=device_memory_format)

        if add_supheader:
            lines = self.add_supheader(lines, terminal=terminal,
                                       underline=underline_supheader, bold=bold_supheader, separate=separate_supheader)

        if not table:
            placeholder = true_rjust(terminal.bold + 'No entries to display!' + terminal.normal, true_len(lines[-1]))
            lines[-1] = placeholder
        return '\n'.join(lines)
