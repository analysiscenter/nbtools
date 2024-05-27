""" Functions for code quality control of Jupyter Notebooks. """
#pylint: disable=import-outside-toplevel
import os
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout

from .core import StringWithDisabledRepr, get_notebook_path, notebook_to_script



PYLINTRC_TEMPLATE = """
[DESIGN]
max-line-length={max_line_length}
variable-rgx=(.*[a-z][a-z0-9_]{{1,30}}|[a-z_])$ # snake_case + single letters
argument-rgx=(.*[a-z][a-z0-9_]{{1,30}}|[a-z_])$ # snake_case + single letters

[MESSAGE CONTROL]
disable=too-few-public-methods, unsubscriptable-object, no-member, too-many-lines, too-many-locals,
        arguments-renamed, arguments-differ, multiple-statements, invalid-name,
        missing-module-docstring, missing-final-newline, redefined-outer-name,
        wrong-import-position, no-name-in-module, import-error, unused-wildcard-import,
        unnecessary-semicolon, trailing-whitespace, trailing-newlines,
        {disable}

good-names=bar, df, fn
additional-builtins=display, get_ipython
"""


def generate_pylintrc(path, disable=(), enable=(), max_line_length=120, **pylint_params):
    """ Create `pylintrc` file.

    Parameters
    ----------
    path : str
        Path to save the file.
    disable : sequence
        Which checks to disable. Each element should be either a code or a name of the check.
    enable : sequence
        Which checks to enable. Each element should be either a code or a name of the check.
        Has priority over `disable`.
    max_line_length : int
        Allowed line length.
    pylint_params : dict
        Additional parameter of linting. Each is converted to a separate valid entry in the `pylintrc` file.
    """
    disable = [disable] if isinstance(disable, str) else disable
    enable = [enable] if isinstance(enable, str) else enable
    disable = [item.replace('_', '-') for item in disable]
    enable = [item.replace('_', '-') for item in enable]

    pylintrc = PYLINTRC_TEMPLATE.format(disable=','.join(disable),
                                        max_line_length=max_line_length)

    for item in enable:
        if item in pylintrc:
            pylintrc = (pylintrc.replace(item, '')
                                .replace('=, ', '=')
                                .replace(', ,', ','))

    for key, value in pylint_params.items():
        key = key.replace('_', '-')
        if isinstance(value, list):
            value = ', '.join(value)
        pylintrc += f'\n{key}={value}'

    with open(path, 'w', encoding='utf-8') as file:
        file.write(pylintrc)

    return pylintrc


def pylint_notebook(path=None, options=(), config=None, disable=(), enable=(), printer=print,
                    remove_files=True, return_info=False, **pylint_params):
    """ Execute ``pylint`` for a provided Jupyter Notebook.

    Under the hood, roughly does the following:
        - Creates a ``.pylintrc`` file next to the ``path``, if needed.
        - Converts the notebook to `.py` file next to the ``path``.
        - Runs ``pylint`` with additional options.
        - Create a report and display it, if needed.

    Parameters
    ----------
    path : str, optional
        Path to the Jupyter notebook. If not provided, the current notebook is used.
    options : sequence
        Additional options for ``pylint`` execution.
    config : str, None
        Path to a pylint config in the ``.pylintrc`` format.
        Note, if config is not None, then `disable` and `enable` are not used.
    printer : callable or None
        Function to display the report.
    remove_files : bool
        Whether to remove ``.pylintrc`` and ``.py`` files after the execution.
    return_info : bool
        Whether to return a dictionary with intermediate results.
        It contains the notebook code string, as well as ``pylint`` stdout and stderr.
    disable : sequence
        Which checks to disable. Each element should be either a code or a name of the check.
    enable : sequence
        Which checks to enable. Each element should be either a code or a name of the check.
        Has priority over ``disable``.
    max_line_length : int
        Allowed line length.
    pylint_params : dict
        Additional parameter of linting. Each is converted to a separate valid entry in the ``.pylintrc`` file.
    """
    try:
        from pylint.lint import Run
        from pylint.reporters.text import TextReporter
    except ImportError as exception:
        raise ImportError('Install pylint') from exception


    path = path or get_notebook_path()
    if path is None:
        raise ValueError('Provide path to Jupyter Notebook or run `pylint_notebook` inside of it!')

    # Convert notebook to a script
    path_script = os.path.splitext(path)[0] + '.py'
    script_name = os.path.basename(path_script)

    code, cell_line_numbers = notebook_to_script(path_notebook=path, path_script=path_script, return_info=True).values()

    # Create pylintrc file
    if config is None:
        path_pylintrc = os.path.splitext(path)[0] + '.pylintrc'
        pylintrc = generate_pylintrc(path_pylintrc, disable=disable, enable=enable, **pylint_params)
    else:
        path_pylintrc = config

        # Open config for output
        if return_info:
            with open(path_pylintrc, 'r', encoding='utf-8') as rcfile:
                pylintrc = rcfile.read()

    # Run pylint on script with pylintrc configuration
    pylint_cmdline = [path_pylintrc, f'--rcfile={path_pylintrc}', *options]

    # Run pylint and catch messagies
    with redirect_stdout(StringIO()) as pylint_stdout, redirect_stderr(StringIO()) as pylint_stderr:
        reporter = TextReporter(pylint_stdout)
        Run(pylint_cmdline, reporter=reporter, exit=False)

        report = pylint_stdout.getvalue()
        errors = pylint_stderr.getvalue()

    # Prepare custom report
    output = []

    for line in report.split('\n'):
        # error line is a str in the format:
        # "filename.py:line_num:position_num: error_code: error_text (error_name)"
        if 'rated' in line:
            output.insert(0, line.strip(' '))
            output.insert(1, '–' * (len(line) - 1))

        elif path_script in line or script_name in line:
            line = line.replace(path_script, '__').replace(script_name, '__')
            line_semicolon_split = line.split(':')

            # Locate the cell and line inside the cell
            code_line_number = int(line_semicolon_split[1])
            for cell_number, cell_ranges in cell_line_numbers.items():
                if code_line_number in cell_ranges:
                    cell_line_number = code_line_number - cell_ranges[0]
                    break
            else:
                cell_number, cell_line_number = -1, code_line_number

            # Find error_code and error_name: for example, `C0123` and `invalid-name`
            error_code = line_semicolon_split[3].strip()

            error_message = line_semicolon_split[4].strip()
            error_name_start  = error_message.rfind('(')

            error_human_message = error_message[:error_name_start].strip()
            error_name = error_message[error_name_start+1:-1]

            # Make new message
            message = f'Cell {cell_number}:{cell_line_number}, code={error_code}, name={error_name}'
            message += f'\n     Pylint message ::: {error_human_message}\n'
            output.append(message)

    output = '\n'.join(output).strip()

    if remove_files:
        os.remove(path_script)
        if config is None:
            os.remove(path_pylintrc)

    if printer is not None:
        printer(output)

    if return_info:
        enumerated_code = code.split('\n')
        n_digits = len(str(len(enumerated_code)))
        enumerated_code = [f'{i:0>{n_digits}}    ' + item
                           for i, item in enumerate(enumerated_code, start=1)]
        enumerated_code = '\n'.join(enumerated_code)

        return {
            'report' : StringWithDisabledRepr(output),

            'code' : StringWithDisabledRepr(code),
            'enumerated_code' : StringWithDisabledRepr(enumerated_code),

            'pylintrc' : StringWithDisabledRepr(pylintrc),
            'pylint_errors' : StringWithDisabledRepr(errors),
            'pylint_report' : StringWithDisabledRepr(report),
        }
    return None
