""" Functions for running Jupyter Notebooks programmatically."""
import os
import time
import json
from functools import wraps
from glob import glob
from textwrap import dedent
from multiprocessing import Process, Queue
import psutil


TMP_DIR = '/tmp/nbtools_exec_notebook'  # noqa: S108
os.makedirs(TMP_DIR, exist_ok=True)


# Decorator
def run_in_process(func):
    """ Decorator to run the ``func`` in a separate process for terminating all related processes properly. """
    @wraps(func)
    def _wrapper(*args, **kwargs):
        _output_queue = Queue()
        kwargs = {**kwargs, '_output_queue': _output_queue}

        json_path = None

        output = {'failed': True, 'traceback': ''}

        try:
            process = Process(target=func, args=args, kwargs=kwargs)
            process.start()

            path = args[0] if args else kwargs['path']
            json_path = f'{TMP_DIR}/{process.pid}.json'

            with open(json_path, 'w', encoding='utf-8') as file:
                json.dump({'path': path}, file)

            output = _output_queue.get()
            process.join()
        except (KeyboardInterrupt, Exception) as e:  # noqa: BLE001
            output = {'failed': True, 'traceback': e}

            # Terminate all relevant processes when something went wrong, e.g. Keyboard Interrupt
            for child in psutil.Process(process.pid).children():
                if psutil.pid_exists(child.pid):
                    child.terminate()

            if psutil.pid_exists(process.pid):
                process.terminate()
        finally:
            if json_path is not None and os.path.exists(json_path):
                os.remove(json_path)

            if kwargs.get('raise_exception', False) and output['failed']:
                raise Exception(output['traceback'])

        return output
    return _wrapper

def get_exec_notebook_name(pid):
    """ Get the notebook name by its pid.

    Under the hood, the function checks the /tmp/ directory for logs of running ``exec_notebook`` executors and extract
    the name for the provided pid.
    """
    json_path = f'{TMP_DIR}/{pid}.json'
    if not os.path.exists(json_path):
        return 'exec_notebook'
    with open(json_path, 'r', encoding='utf-8') as file:
        path = json.load(file)['path']
    return path.split('/')[-1]



# Code fragments that are inserted as additional cells in a notebook
CELL_INSERT_COMMENT = "# Cell inserted during automated execution"

# Connect to a shelve database for inputs/outputs providing
DB_CONNECT_CODE_CELL = """
    import os, shelve
    from dill import Pickler, Unpickler

    shelve.Pickler = Pickler
    shelve.Unpickler = Unpickler

    out_path_db = {}
"""
DB_CONNECT_CODE_CELL = dedent(DB_CONNECT_CODE_CELL)

# Insert inputs into the notebook
INPUTS_CODE_CELL = """
    # Inputs loading
    with shelve.open(out_path_db) as notebook_db:
        inputs = {**notebook_db}

        locals().update(inputs)
"""
INPUTS_CODE_CELL = dedent(INPUTS_CODE_CELL)

INPUTS_DISPLAY = """
    for k, v in inputs.items():
        if isinstance(v, str):
            print(f"{k} = '{v}'")
        else:
            print(f"{k} = {v}")
""" # it is better than pprint, because pprint adds quotes on variable names
# TODO: think about indentation for dicts and lists
INPUTS_DISPLAY = dedent(INPUTS_DISPLAY)

# Save notebook outputs
OUTPUTS_CODE_CELL = """
    # Output dict preparation
    output = {{}}
    outputs = {}

    for value_name in outputs:
        if value_name in locals():
            output[value_name] = locals()[value_name]

    with shelve.open(out_path_db) as notebook_db:
        notebook_db['outputs'] = output
"""
OUTPUTS_CODE_CELL = dedent(OUTPUTS_CODE_CELL)

OUTPUTS_DISPLAY = """
    for k, v in output.items():
        if isinstance(v, str):
            print(f"{k} = '{v}'")
        else:
            print(f"{k} = {v}")
"""
OUTPUTS_DISPLAY = dedent(OUTPUTS_DISPLAY)



# Main functions
@run_in_process
def exec_notebook(path, inputs=None, outputs=None, inputs_pos=1, replace_inputs_pos=False,
                  display_inputs=False, display_outputs=False,
                  working_dir = './', execute_kwargs=None,
                  out_path_db=None, out_path_ipynb=None, out_path_html=None, remove_db='always',
                  add_timestamp=True, hide_code_cells=False, display_links=True,
                  raise_exception=False, return_notebook=False, _output_queue=None):
    """ Execute a Jupyter Notebook programmatically.
    Heavily inspired by https://github.com/tritemio/nbrun.

    Intended to be an analog of ``exec``, providing a way to inject / extract variables from the execution.
    For a detailed description of how to do that, check the ``inputs`` and ``outputs`` parameters.
    The executed notebook is optionally saved to disk as ``.ipynb`` / ``.html`` file: we strongly recommend always
    doing so.

    The ``raise_exception`` flag defines the behavior if the execution of the notebook fails due to an exception.

    Under the hood, this function does the following:
        * Create an internal database to communicate variables (both ``inputs`` and ``outputs``). Save ``inputs`` to it.
        * Add a cell for reading ``inputs`` from the internal database, add a cell for saving ``outputs`` to it.
        * Execute notebook.
        * Handle exceptions.
        * Read ``outputs`` from the database.
        * Add a timestamp cell to the notebook, if needed.
        * Save the executed notebook as ``.ipynb`` and / or ``.html``.
        * Return a dictionary with intermediate results, execution info and values of ``outputs`` variables.

    If there are no ``inputs`` or ``outputs``, a database is not created and additional cells are not inserted.
    Note, if either of them is provided, then one of ``out_path_ipynb`` or ``out_path_db`` must be explicitly defined.

    Parameters
    ----------
    path : str
        Path to the notebook to execute.
    inputs : dict, optional
        Inputs for execution are essentially equivalent to notebook ``globals``.
        Must be a dictionary with variable names and their values; therefore, keys must be valid Python identifiers.
        Under the hood, inputs are saved into a database, loaded in the notebook in a separate cell, that is inserted at
        the ``inputs_pos`` position. Therefore, values must be serializable.
    outputs : str or iterable of str, optional
        The list of variable names to return from the notebook.
        Extracted from the notebook in a separate cell, which is inserted at the last position.
        Note, if some of the variables don't exist, no errors are raised.
    inputs_pos : int, optional
        Position to insert the cell with ``inputs`` loading into the notebook.
    replace_inputs_pos : int, optional
        Whether to replace ``inputs_pos`` code cell with ``inputs`` or insert a new one.
    display_inputs : bool, optional
        Whether to display ``inputs`` or not.
        Under the hood, inputs are provided using a shelve database. If ``display_inputs=True``, variables will be
        inserted in the cell in the following manner: ``input_name = input_value``, instead of importing code from
        shelve.
    display_outputs : bool, optional
        Whether to display ``outputs`` or not.
        Under the hood, outputs are saved using a shelve database. If ``display_outputs=True``, variables will be shown
        in the last cell in the following manner: ``print(input_name)``, instead of dumping code into the database.
    working_dir : str
        The working directory of starting the kernel.
    out_path_db : str, optional
        Path to save the internal database files (without file extension).
        If not provided, then it is inferred from ``out_path_ipynb``.
    out_path_ipynb : str, optional
        Path to save the output ipynb file.
    out_path_html : str, optional
        Path to save the output html file.
    remove_db : str, optional
        Whether to remove the internal database after notebook execution. Possible options are:
            - ``'always'``: remove the database after notebook execution
            - ``'not_failed_case'``: remove the database if there wasn't any execution failure
            - ``'never'``: don't remove the database after notebook execution

        Running :func:`~.exec_notebook` with the ``'not_failed_case'`` or ``'never'`` option helps to reproduce failures
        in the ``out_path_ipynb`` notebook: it will take the inputs from the saved shelve database.
        Note, that the database exists only if inputs and / or outputs are provided.
    execute_kwargs : dict, optional
        Parameters of :class:`nbconvert.preprocessors.ExecutePreprocessor`.
        For example, you can provide ``timeout``, ``kernel_name``, ``resources`` (such as metadata)
        and other :class:`nbclient.client.NotebookClient` arguments.
    add_timestamp : bool, optional
        Whether to add a cell with execution information at the beginning of the saved notebook.
    hide_code_cells : bool, optional
        Whether to hide the code cells in the saved notebook.
    display_links : bool, optional
        Whether to display links to the executed notebook and html at execution.
    raise_exception : bool, optional
        Whether to re-raise exceptions from the notebook.
    return_notebook : bool, optional
        Whether to return the notebook object from this function.
    _output_queue : None
        Placeholder for the :func:`~.run_in_process` decorator to return this function result.

    Returns
    -------
    exec_res : dict
        Dictionary with the notebook execution results.
        It provides the following information:

            - ``'failed'`` : ``bool``
                Whether the notebook execution failed.
            - ``'outputs'`` : ``dict``
                Saved notebook local variables. Is not presented in ``exec_res`` dict, if ``outputs``
                argument is ``None.``
            - ``'failed cell number'`` : ``int``
                An error cell execution number (if notebook failed).
            - ``'traceback'`` : ``str``
                Traceback message from the notebook (if notebook failed).
            - ``'notebook'`` : :class:`nbformat.notebooknode.NotebookNode`, optional
                Executed notebook object. Note that this output is provided only if ``return_notebook`` is ``True``.
    """
    import nbformat
    from jupyter_client.manager import KernelManager
    from nbconvert.preprocessors import ExecutePreprocessor
    import shelve
    from dill import Pickler, Unpickler

    if inputs is not None or outputs is not None:
        # Set `out_path_db` value
        if out_path_db is None:
            if out_path_ipynb:
                out_path_db = os.path.splitext(out_path_ipynb)[0] + '_db'
            else:
                error_message = """\
                                Invalid value for `out_path_db` argument. If `inputs` or `outputs` are provided,
                                then you need to provide `out_path_db` or `out_path_ipynb` arguments."""
                error_message = dedent(error_message)
                raise ValueError(error_message)

        # `out_path_db` is db path for current method, for db reading from the executed notebook we need relative path:
        working_dir_out_path_db = os.path.relpath(out_path_db, start=working_dir)

        # Create a shelve database
        shelve.Pickler = Pickler
        shelve.Unpickler = Unpickler

        with shelve.open(out_path_db) as notebook_db:
            notebook_db.clear()

    if isinstance(outputs, str):
        outputs = [outputs]

    execute_kwargs = {'timeout': -1} if execute_kwargs is None else {'timeout': -1, **execute_kwargs}
    executor = ExecutePreprocessor(**execute_kwargs)
    kernel_manager = KernelManager()

    # Notebook preparation:
    # Read the notebook, insert a cell with inputs, insert another cell for outputs extraction
    with open(path, encoding='utf-8') as file:
        notebook = nbformat.read(file, as_version=4)

    if inputs is not None:
        # Save `inputs` in the shelve database and create a cell in the notebook
        # for parameters extraction
        with shelve.open(out_path_db) as notebook_db:
            notebook_db.update(inputs)

        code = CELL_INSERT_COMMENT + DB_CONNECT_CODE_CELL.format(repr(working_dir_out_path_db)) + INPUTS_CODE_CELL
        if display_inputs:
            code += INPUTS_DISPLAY

        if replace_inputs_pos:
            notebook['cells'][inputs_pos] = nbformat.v4.new_code_cell(code)
        else:
            notebook['cells'].insert(inputs_pos, nbformat.v4.new_code_cell(code))


    if outputs is not None:
        # Create a cell to extract outputs from the notebook
        # It saves locals from the notebook with preferred names in the shelve database
        # This cell will be executed in error case too
        code = CELL_INSERT_COMMENT + \
               (DB_CONNECT_CODE_CELL.format(repr(working_dir_out_path_db)) if not inputs else "") + \
               OUTPUTS_CODE_CELL.format(outputs)

        if display_outputs:
            code += OUTPUTS_DISPLAY

        output_cell = nbformat.v4.new_code_cell(code)
        notebook['cells'].append(output_cell)

    # Execute the notebook
    start_time = time.time()
    exec_failed = False
    try:
        executor.preprocess(notebook, {'metadata': {'path': working_dir}}, km=kernel_manager)
    except:  # noqa: E722
        exec_failed = True

        # Save notebook outputs in the shelve db
        if outputs is not None:
            executor.kc = kernel_manager.client() # For compatibility with 5.x.x version of `nbconvert`
            executor.preprocess_cell(output_cell, {'metadata': {'path': working_dir}}, -1)
    finally:
        # Shutdown kernel
        kernel_manager.cleanup_resources()
        kernel_manager.shutdown_kernel(now=True)

        # Extract information from the database and remove it (if exists)
        if outputs is not None:
            with shelve.open(out_path_db) as notebook_db:
                outputs_values = notebook_db.get('outputs', {})

        # Check if something went wrong
        failed, error_cell_num, traceback_message = extract_traceback(notebook=notebook)

        if exec_failed:
            failed = True
            traceback_message += '\nNotebook execution failed\n'

        # Remove database
        if out_path_db is not None and (remove_db == 'always' or (remove_db == 'not_failed_case' and not failed)):
            db_paths = glob(out_path_db + '*')

            for path_ in db_paths:
                os.remove(path_)

        # Prepare execution results: execution state, notebook outputs and error info (if exists)
        if failed:
            exec_res = {'failed': failed, 'failed cell number': error_cell_num, 'traceback': traceback_message}

            # Re-raise exception if needed
            if raise_exception:
                _output_queue.put(exec_res)
                return None  # noqa: RET501
        else:
            exec_res = {'failed': failed, 'failed cell number': None, 'traceback': ''}

        if outputs is not None:
            exec_res['outputs'] = outputs_values

        # Notebook postprocessing: add timestamp, mask db reading/dumping code
        if add_timestamp:
            timestamp = (f"**Executed:** {time.ctime(start_time)}<br>"
                         f"**Duration:** {time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}<br>"
                         f"**Autogenerated from:** [{path}]\n\n---")
            timestamp_cell = nbformat.v4.new_markdown_cell(timestamp)
            notebook['cells'].insert(0, timestamp_cell)

        if display_inputs and inputs is not None:
            pos = inputs_pos + 1 if add_timestamp else inputs_pos
            _display_inputs_reading(notebook=notebook, pos=pos)

        if display_outputs and outputs is not None:
            pos = len(notebook['cells']) - 1
            _display_outputs_dumping(notebook=notebook, pos=pos)

        if hide_code_cells:
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    cell["metadata"].update({"jupyter": {"source_hidden": "true"}})

        # Save the executed notebook/HTML to disk
        if out_path_ipynb is not None:
            save_notebook(notebook=notebook, out_path_ipynb=out_path_ipynb, display_link=display_links)
        if out_path_html is not None:
            notebook_to_html(notebook=notebook, out_path_html=out_path_html, display_link=display_links)

        if return_notebook:
            exec_res['notebook'] = notebook

        _output_queue.put(exec_res) # return for parent process
    return None  # noqa: RET501

# Functions for database operations cells masking
def _display_inputs_reading(notebook, pos):
    """ Replace database reading code by variables initialization mask.

    Result is a code cell with the following view:
    .. code-block:: python

        varible_name_1 = varible_value_1
        varible_name_2 = varible_value_2
        ...
    """
    import nbformat

    execution_count = notebook['cells'][pos]['execution_count']

    code_mask = str(notebook['cells'][pos]['outputs'][0]['text'])[:-1]

    cell_mask = nbformat.v4.new_code_cell(source=code_mask, execution_count=execution_count)
    notebook['cells'][pos] = cell_mask

def _display_outputs_dumping(notebook, pos):
    """ Replace database dumping code by printing outputs.

    Result is a code cell with the following view and corresponding output:
    .. code-block:: python

        print(varible_name_1)
        print(varible_name_2)
        ...
    """
    import nbformat

    execution_count = notebook['cells'][pos]['execution_count']
    outputs_variables = str(notebook['cells'][pos]['outputs'][0]['text']).split('\n')

    code_mask = ''
    text_mask = ''

    for variable in outputs_variables:
        separator_pos = int(variable.find(' = '))

        if separator_pos != -1:
            variable_name = variable[:separator_pos]
            variable_value = variable[separator_pos+2:] + '\n'

            code_mask += f'print({variable_name})\n'
            text_mask += variable_value

    code_mask = code_mask[:-1] # remove extra '\n'

    outputs_mask =  [nbformat.v4.new_output(text=text_mask[1:], name='stdout', output_type='stream')]

    cell_mask = nbformat.v4.new_code_cell(source=code_mask, execution_count=execution_count, outputs=outputs_mask)
    notebook['cells'][pos] = cell_mask


# Save notebook functions
def save_notebook(notebook, out_path_ipynb, display_link):
    """ Save an instance of :class:``nbformat.notebooknode.NotebookNode`` as ipynb file."""
    import nbformat
    from IPython.display import display, FileLink

    with open(out_path_ipynb, 'w', encoding='utf-8') as file:
        nbformat.write(notebook, file)

    if display_link:
        print('Executed notebook link:')
        display(FileLink(out_path_ipynb))

def notebook_to_html(notebook, out_path_html, display_link):
    """ Save an instance of :class:``nbformat.notebooknode.NotebookNode`` as html file."""
    from nbconvert import HTMLExporter
    from IPython.display import display, FileLink

    html_exporter = HTMLExporter()
    body, _ = html_exporter.from_notebook_node(notebook)

    with open(out_path_html, 'w', encoding='utf-8') as f:
        f.write(body)

    if display_link:
        print('Executed notebook link:')
        display(FileLink(out_path_html))


# Traceback postprocessing
def extract_traceback(notebook):
    """ Extracts information about an error from the notebook.

    Parameters
    ----------
    notebook: :class:`nbformat.notebooknode.NotebookNode`
        Executed notebook to find an error traceback.

    Returns
    -------
    tuple
        Tuple of three elements:

            - ``bool``
                Whether the executed notebook has an error traceback.

            - ``int`` or ``None``
                Number of a cell with a traceback.
                If ``None``, then the notebook doesn't contain an error traceback.

            - ``str``
                Error traceback if exists.

    """
    for cell in notebook['cells']:
        # Find a cell output with a traceback and extract the traceback
        outputs = cell.get('outputs', [])

        for output in outputs:
            traceback = output.get('traceback', [])

            if traceback:
                traceback = '\n'.join(traceback)
                return True, cell['execution_count'], traceback

    return False, None, ""

# Aliases
run_notebook = exec_notebook
