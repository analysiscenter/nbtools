""" Functions for running Jupyter Notebooks programmatically."""
#pylint: disable=import-outside-toplevel
import os
import time
from glob import glob
from textwrap import dedent

# Code fragments that are inserted in the notebook
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


def run_notebook(path, inputs=None, outputs=None, inputs_pos=1, working_dir = './', execute_kwargs=None,
                 out_path_db=None, out_path_ipynb=None, out_path_html=None, remove_db='always', add_timestamp=True,
                 hide_code_cells=False, display_links=True, raise_exception=False, return_notebook=False):
    """ Execute a Jupyter Notebook programmatically.
    Heavily inspired by https://github.com/tritemio/nbrun.

    Intended to be an analog of `exec`, providing a way to inject / extract variables from the execution.
    Executed notebook is optionally saved to disk as `.ipynb`/`.html`: we strongly recommend always doing that.
    For a detailed description of how to do that, check the `inputs` and `outputs` parameters.

    Flag `raise_exception` defines behavior if the execution of the notebook is failed due to an exception.

    Under the hood, this function does the following:
        - Create an internal database to communicate variables (both `inputs` and `outputs`). Save `inputs` to it.
        - Add a cell with reading `inputs` from the database, add a cell for saving `outputs` to the database.
        - Execute notebook.
        - Handle exceptions.
        - Read `outputs` from the database.
        - Add a timestamp cell to the notebook, if needed.
        - Save the executed notebook as `.ipynb` and/or `.html`.
        - Return a dictionary with intermediate results, execution info and values of `outputs` variables.

    If there are no `inputs` nor `outputs`, a database is not created and additional cells are not inserted.
    If either of them is provided, then one of `out_path_ipynb` or `out_path_db` must be explicitly defined.

    Parameters
    ----------
    path : str
        Path to the notebook to execute.
    inputs : dict, optional
        Inputs for notebook execution: essentially, its `globals`.
        Must be a dictionary with variable names and their values; therefore, keys must be valid Python identifiers.
        Saved to a database, loaded in the notebook in a separate cell, that is inserted at `inputs_pos` position.
        Therefore, values must be serializable.
    outputs : str or iterable of str, optional
        List of notebook local variable names to return.
        Extracted from the notebook in a separate cell, that is inserted at the last position.
        If some of the variables don't exist, no errors are raised.
    inputs_pos : int, optional
        Position to insert the cell with `inputs` loading into the notebook.
    working_dir : str
        The working directory of starting the kernel.
    out_path_db : str, optional
        Path to save shelve database files without file extension.
        If not provided, then it is inferred from `out_path_ipynb`.
    out_path_ipynb : str, optional
        Path to save the output ipynb file.
    out_path_html : str, optional
        Path to save the output html file.
    remove_db : str, optional
        Whether to remove shelve database after notebook execution.
        Possible options are: 'always', 'not_failed_case' or 'never'.
        If 'always', then remove the database after notebook execution.
        If 'not_failed_case', then remove the database if there wasn't any execution failure.
        If 'never', then don't remove the database after notebook execution.
        Running `:meth:run_notebook` with 'not_failed_case' or 'never' option helps to reproduce failures
        in the `out_path_ipynb` notebook: it will take passed inputs from the saved shelve database.
        Note, that database exists only if inputs and/or outputs are provided.
    execute_kwargs : dict, optional
        Parameters of `:class:ExecutePreprocessor`.
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

    Returns
    -------
    exec_res : dict
        Dictionary with the notebook execution results.
        It provides next information:
        - 'failed' : bool
           Whether the notebook execution failed.
        - 'outputs' : dict
           Saved notebook local variables.
           Is not presented in `exec_res` dict, if `outputs` argument is None.
        - 'failed cell number': int
           An error cell execution number (if notebook failed).
        - 'traceback' : str
           Traceback message from the notebook (if notebook failed).
        - 'notebook' : :class:`nbformat.notebooknode.NotebookNode`, optional
           Executed notebook object.
           Note that this output is provided only if `return_notebook` is True.
    """
    # pylint: disable=bare-except, lost-exception
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

        # Create a shelve database
        shelve.Pickler = Pickler
        shelve.Unpickler = Unpickler

        with shelve.open(out_path_db) as notebook_db:
            notebook_db.clear()

    if isinstance(outputs, str):
        outputs = [outputs]

    execute_kwargs = execute_kwargs or {'timeout': -1}
    executor = ExecutePreprocessor(**execute_kwargs)
    kernel_manager = KernelManager()

    # Notebook preparation:
    # Read the notebook, insert a cell with inputs, insert another cell for outputs extraction
    notebook = nbformat.read(path, as_version=4)

    if hide_code_cells:
        notebook["metadata"].update({"hide_input": True})

    if inputs is not None:
        # Save `inputs` in the shelve database and create a cell in the notebook
        # for parameters extraction
        with shelve.open(out_path_db) as notebook_db:
            notebook_db.update(inputs)

        code = CELL_INSERT_COMMENT + DB_CONNECT_CODE_CELL.format(repr(out_path_db)) + INPUTS_CODE_CELL
        notebook['cells'].insert(inputs_pos, nbformat.v4.new_code_cell(code))

    if outputs is not None:
        # Create a cell to extract outputs from the notebook
        # It saves locals from the notebook with preferred names in the shelve database
        # This cell will be executed in error case too
        code = CELL_INSERT_COMMENT + \
               (DB_CONNECT_CODE_CELL.format(repr(out_path_db)) if not inputs else "") + \
               OUTPUTS_CODE_CELL.format(outputs)
        output_cell = nbformat.v4.new_code_cell(code)
        notebook['cells'].append(output_cell)

    # Execute the notebook
    start_time = time.time()
    exec_failed = False
    try:
        executor.preprocess(notebook, {'metadata': {'path': working_dir}}, km=kernel_manager)
    except:
        exec_failed = True

        # Save notebook outputs in the shelve db
        if outputs is not None:
            executor.kc = kernel_manager.client() # For compatibility with 5.x.x version of `nbconvert`
            executor.preprocess_cell(output_cell, {'metadata': {'path': working_dir}}, -1)

        if raise_exception:
            raise
    finally:
        kernel_manager.shutdown_kernel()

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
        else:
            exec_res = {'failed': failed, 'failed cell number': None, 'traceback': ''}

        if outputs is not None:
            exec_res['outputs'] = outputs_values

        if add_timestamp:
            timestamp = (f"**Executed:** {time.ctime(start_time)}<br>"
                         f"**Duration:** {time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}<br>"
                         f"**Autogenerated from:** [{path}]\n\n---")
            timestamp_cell = nbformat.v4.new_markdown_cell(timestamp)
            notebook['cells'].insert(0, timestamp_cell)

        # Save the executed notebook/HTML to disk
        if out_path_ipynb is not None:
            save_notebook(notebook=notebook, out_path_ipynb=out_path_ipynb, display_link=display_links)
        if out_path_html is not None:
            notebook_to_html(notebook=notebook, out_path_html=out_path_html, display_link=display_links)

        if return_notebook:
            exec_res['notebook'] = notebook
        return exec_res

# Save notebook functions
def save_notebook(notebook, out_path_ipynb, display_link):
    """ Save an instance of :class:`nbformat.notebooknode.NotebookNode` as ipynb file."""
    import nbformat
    from IPython.display import display, FileLink

    with open(out_path_ipynb, 'w', encoding='utf-8') as file:
        nbformat.write(notebook, file)

    if display_link:
        display(FileLink(out_path_ipynb))

def notebook_to_html(notebook, out_path_html, display_link):
    """ Save an instance of :class:`nbformat.notebooknode.NotebookNode` as html file."""
    from nbconvert import HTMLExporter
    from IPython.display import display, FileLink

    html_exporter = HTMLExporter()
    body, _ = html_exporter.from_notebook_node(notebook)

    with open(out_path_html, 'w', encoding='utf-8') as f:
        f.write(body)

    if display_link:
        display(FileLink(out_path_html))


def extract_traceback(notebook):
    """ Extracts information about an error from the notebook.

    Parameters
    ----------
    notebook: :class:`nbformat.notebooknode.NotebookNode`
        Executed notebook to find an error traceback.

    Returns
    -------
    bool
        Whether the executed notebook has an error traceback.
    int or None
        Number of a cell with a traceback.
        If None, then the notebook doesn't contain an error traceback.
    str
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
