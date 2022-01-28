""" !!. """
#pylint: disable=import-outside-toplevel
import os
import re
import json



class StringWithDisabledRepr(str):
    """ String with disabled repr. Used to avoid cluttering repr from function outputs. """
    def __repr__(self):
        """ !!. """
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
    """ !!. """
    import nbformat #pylint: disable=import-outside-toplevel
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
        cell_lines.insert(0, f'\n### [{cell_number}] cell')

        # Comment cell/line magics
        for j, line in enumerate(cell_lines):
            if line.startswith('%') or line.startswith('!'):
                cell_lines[j] = '### ' + line

        code_line_number = len(code_lines) + 1
        cell_line_numbers[cell_number] = range(code_line_number, code_line_number + len(cell_lines))

        code_lines.extend([line.strip('\n') for line in cell_lines])
        code_lines.append('')
        cell_number += 1

    code = '\n'.join(code_lines).strip()

    with open(path_script, 'w', encoding='utf-8') as file:
        file.write(code)

    if return_info:
        return {'code': StringWithDisabledRepr(code),
                'cell_line_numbers': cell_line_numbers}
    return None
