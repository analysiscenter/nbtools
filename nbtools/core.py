""" Core utility functions to work with Jupyter Notebooks. """
import os
import sys
import re
import json
import warnings



class StringWithDisabledRepr(str):
    """ String with disabled repr. Used to avoid cluttering repr from function outputs. """
    def __repr__(self):
        """ Shorten the repr of a string. """
        return f'<StringWithDisabledRepr at {hex(id(self))}. Use `str`/`print` explicitly!>'



def in_notebook():
    """ Return True if in Jupyter notebook and False otherwise. """
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True
        if shell == 'TerminalInteractiveShell':
            return False
        return False
    except NameError:
        return False

def get_notebook_path():
    """ Return the full absolute path of the current Jupyter notebook,
    for example, `/path/path/path/My_notebook_title.ipynb`.

    If run outside Jupyter notebook, returns None.
    """
    if not in_notebook():
        return None

    import requests
    import ipykernel

    # Id of the current running kernel: a string uid
    kernel_id = re.search('kernel-(.*).json', ipykernel.connect.get_connection_file()).group(1)

    # Get running servers for both JupyterLab v2.# and v3.#
    from notebook.notebookapp import list_running_servers as list_running_servers_v2
    from jupyter_server.serverapp import list_running_servers as list_running_servers_v3
    servers = list(list_running_servers_v2()) + list(list_running_servers_v3())

    for server in servers:
        root_dir = server.get('root_dir') or server.get('notebook_dir')
        response = requests.get(requests.compat.urljoin(server['url'], 'api/sessions'),
                                params={'token': server.get('token', '')})

        for params in json.loads(response.text):
            if params['kernel']['id'] == kernel_id:
                relative_path = params['notebook']['path']
                return os.path.join(root_dir, relative_path)
    raise ValueError(f'Unable to find kernel `{kernel_id}` in {len(servers)} servers!')

def get_notebook_name():
    """ Return the title of the current Jupyter notebook without base directory and extension,
    for example, `My_notebook_title`.

    If run outside Jupyter notebook, returns None.
    """
    if not in_notebook():
        return None

    return os.path.splitext(get_notebook_path())[0].split('/')[-1]


def notebook_to_script(path_script, path_notebook=None, ignore_markdown=True, return_info=False):
    """ Convert a notebook to a script. """
    import nbformat
    path_notebook = path_notebook or get_notebook_path()
    if path_notebook is None:
        raise ValueError('Provide path to Jupyter Notebook or run `notebook_to_script` inside of it!')

    # Read notebook as list of cells
    notebook = nbformat.read(path_notebook, as_version=4)

    code_lines = []
    cell_number = 1
    cell_line_numbers = {}

    for cell in notebook['cells']:
        if ignore_markdown and cell['cell_type'] != 'code':
            continue

        cell_lines = cell['source'].split('\n')

        if cell['cell_type'] == 'code':
            cell_lines.insert(0, f'\n### [{cell_number}] cell')

        # Comment cell/line magics
        for j, line in enumerate(cell_lines):
            if line.startswith('%') or line.startswith('!') or cell['cell_type'] != 'code':
                cell_lines[j] = '### ' + line

        code_line_number = len(code_lines) + 1
        cell_line_numbers[cell_number] = range(code_line_number, code_line_number + len(cell_lines))

        code_lines.extend([line.strip('\n') for line in cell_lines])
        code_lines.append('')

        if cell['cell_type'] == 'code':
            cell_number += 1

    code = '\n'.join(code_lines).strip()

    with open(path_script, 'w', encoding='utf-8') as file:
        file.write(code)

    if return_info:
        return {'code': StringWithDisabledRepr(code),
                'cell_line_numbers': cell_line_numbers}
    return None




def get_available_gpus(n=1, min_free_memory=0.9, max_processes=2, verbose=False,
                       raise_error=False, return_memory=False):
    """ Select ``n`` gpus from available and free devices.

    Parameters
    ----------
    n : int, str

        * If ``'max'``, then use maximum number of available devices.
        * If ``int``, then number of devices to select.

    min_free_memory : int, float

        * If ``int``, minimum amount of free memory (in MB) on a device to consider it free.
        * If ``float``, minimum percentage of free memory.

    max_processes : int
        Maximum amount of computed processes on a device to consider it free.
    verbose : bool
        Whether to show individual device information.
    raise_error : bool
        Whether to raise an exception if not enough devices are available.
    return_memory : bool
        Whether to return memory available on each GPU.

    Returns
    -------
    available_devices : list
        List with available GPUs indices or dict of indices and ``'available'`` and ``'max'`` memory (in MB)
    """
    try:
        import pynvml
    except ImportError as exception:
        raise ImportError('Install Python interface for nvidia_smi') from exception

    try:
        error_message = None
        pynvml.nvmlInit()
    except pynvml.NVMLError_LibraryNotFound:
        if sys.platform == 'win32':
            error_message = " Copy nvml.dll from 'Windows/System32' to 'Program Files/NVIDIA Corporation/NVSMI'"
    finally:
        if error_message:
            raise RuntimeError('NVIDIA SMI is not available.' + error_message)
    n_devices = pynvml.nvmlDeviceGetCount()

    available_devices, memory_free, memory_total  = [], [], []

    for i in range(n_devices):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)

        num_processes = len(pynvml.nvmlDeviceGetComputeRunningProcesses(handle))
        free_memory = info.free / 1024**2
        total_memory = info.total / 1024**2

        memory_threshold = total_memory * min_free_memory if isinstance(min_free_memory, float) else min_free_memory

        consider_available = (
            (free_memory >= memory_threshold) &
            (max_processes is None or num_processes <= max_processes)
        )

        if consider_available:
            available_devices.append(i)
            memory_free.append(free_memory)
            memory_total.append(total_memory)

        if verbose:
            print(f'Device {i} | Free memory: {info.free:4.2f} | '
                  f'Number of running processes: {num_processes:>2} | Free: {consider_available}')

    if isinstance(n, str) and n.startswith('max'):
        n = len(available_devices)

    if len(available_devices) < n:
        msg = f'Not enough free devices: requested {n}, found {len(available_devices)}'
        if raise_error:
            raise ValueError(msg)
        warnings.warn(msg, RuntimeWarning)

    sorted_indices = sorted(range(len(memory_free)), key=lambda k: memory_free[k], reverse=True)
    if return_memory:
        gpus = {}
        for ix in sorted_indices[:n]:
            gpu = available_devices[ix]
            gpus[gpu] = {'available': memory_free[ix], 'max': memory_total[ix]}
        return gpus

    sorted_indices = sorted(range(len(memory_free)), key=lambda k: memory_free[k], reverse=True)
    sorted_devices = [available_devices[i] for i in sorted_indices]
    return sorted_devices[:n]

def get_gpu_free_memory(index, ratio=True):
    """ Get free memory of a device (ratio or size in MB). """
    try:
        import pynvml
    except ImportError as exception:
        raise ImportError('Install Python interface for nvidia_smi') from exception

    pynvml.nvmlInit()
    pynvml.nvmlDeviceGetCount()
    handle = pynvml.nvmlDeviceGetHandleByIndex(index)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    pynvml.nvmlShutdown()

    free_memory = info.free / 1024**2
    total_memory = info.total / 1024**2

    if ratio:
        return free_memory / total_memory
    return free_memory

def set_gpus(n=1, min_free_memory=0.9, max_processes=2, verbose=False, raise_error=False):
    """ Set the ``CUDA_VISIBLE_DEVICES`` variable to ``n`` available devices.

    Parameters
    ----------
    n : int, str

        * If ``'max'``, then use maximum number of available devices.
        * If ``int``, then number of devices to select.

    min_free_memory : int, float

        * If ``int``, minimum amount of free memory (in MB) on a device to consider it free.
        * If ``float``, minimum percentage of free memory.

    max_processes : int
        Maximum amount of computed processes on a device to consider it free.
    verbose : bool or int
        Whether to show individual device information.

            * If ``0`` or ``False``, then no information is displayed.
            * If ``1`` or ``True``, then display the value assigned to ``CUDA_VISIBLE_DEVICES`` variable.
            * If ``2``, then display memory and process information for each device.

    raise_error : bool
        Whether to raise an exception if not enough devices are available.

    Returns
    -------
    devices : list
        Indices of selected and reserved GPUs.
    """
    if 'CUDA_VISIBLE_DEVICES' in os.environ.keys():
        str_devices = os.environ["CUDA_VISIBLE_DEVICES"]
        warnings.warn(f'`CUDA_VISIBLE_DEVICES` is already set to "{str_devices}"!')
        return [int(d) for d in str_devices.split(',')]

    devices = get_available_gpus(n=n, min_free_memory=min_free_memory, max_processes=max_processes,
                                 verbose=(verbose==2), raise_error=raise_error)
    str_devices = ','.join(str(i) for i in devices)
    os.environ['CUDA_VISIBLE_DEVICES'] = str_devices

    newline = "\n" if verbose==2 else ""
    if verbose:
        print(f'{newline}`CUDA_VISIBLE_DEVICES` set to "{str_devices}"')
    return devices

def free_gpus(devices=None):
    """ Terminate all processes on gpu devices.

    Parameters
    ----------
    devices : iterable of ints
        Device indices to terminate processes. If ``None``, than free all available gpus.
    """
    import pynvml
    import psutil

    pynvml.nvmlInit()

    if devices is None:
        if 'CUDA_VISIBLE_DEVICES' in os.environ.keys():
            devices = [int(d) for d in os.environ["CUDA_VISIBLE_DEVICES"].split(',')]
        else:
            devices = range(0, pynvml.nvmlDeviceGetCount())

    for device_index in devices:
        handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)

        for proc in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
            psutil.Process(proc.pid).terminate()

    pynvml.nvmlShutdown()
