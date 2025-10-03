""" Functions for code quality control of Jupyter Notebooks using ruff. """
import os
import subprocess
import tempfile
from .core import StringWithDisabledRepr, get_notebook_path, notebook_to_script


RUFF_TOML_TEMPLATE = """line-length = {max_line_length}

[lint]
select = [
    "F",       # Pyflakes 
    "E",       # pycodestyle (Error)
    "W",       # pycodestyle (Warning)
    "N",       # pep8-naming
    "RET",     # flake8-return
    "S",       # flake8-bandit
    "SLF",     # flake8-self
    "BLE",     # flake8-blind-except
    "UP",      # pyupgrade
    "YTT",     # flake8-2020
]

ignore = [
    {ignore_rules}
]

[lint.per-file-ignores] 
"__init__.py" = ["F401"]        # unused-import
"utils_notebook.py" = ["F401"]  # unused-import
"""


def generate_ruff_toml(path, ignore=(), max_line_length=120, **ruff_params):
    """ Create `ruff.toml` file.

    Parameters
    ----------
    path : str
        Path to save the file.
    ignore : sequence
        Which checks to ignore. Each element should be a rule code.
    max_line_length : int
        Allowed line length.
    ruff_params : dict
        Additional parameters for ruff configuration.
    """
    ignore = [ignore] if isinstance(ignore, str) else ignore
    
    # Build the full ignore list including defaults
    default_ignore = [
        "FBT",     # flake8-boolean-trap
        "E402",    # module-import-not-at-top-of-file
        "E731",    # lambda-assignment
        "F403",    # undefined-local-with-import-star
        "F405",    # undefined-local-with-import-star-usage
        "UP015",   # redundant-open-modes
        "RET504",  # unnecessary-assign
        "NPY002",  # numpy-legacy-random
        "S101",
        "S301",
        "S102",
    ]
    
    all_ignore = default_ignore + list(ignore)
    ignore_str = ',\n    '.join(f'"{rule}"' for rule in all_ignore)
    
    ruff_toml = RUFF_TOML_TEMPLATE.format(
        ignore_rules=ignore_str,
        max_line_length=max_line_length
    )

    with open(path, 'w', encoding='utf-8') as file:
        file.write(ruff_toml)

    return ruff_toml


def ruff_notebook(path=None, config=None, ignore=(), printer=print,
                  remove_files=True, return_info=False, **ruff_params):
    """ Execute ``ruff`` for a provided Jupyter Notebook.

    Under the hood, roughly does the following:
        - Creates a ``ruff.toml`` file next to the ``path``, if needed.
        - Converts the notebook to `.py` file next to the ``path``.
        - Runs ``ruff`` with the configuration.
        - Create a report and display it, if needed.

    Parameters
    ----------
    path : str, optional
        Path to the Jupyter notebook. If not provided, the current notebook is used.
    config : str, None
        Path to a ruff config file. If not provided, a temporary one is created.
    printer : callable or None
        Function to display the report.
    remove_files : bool
        Whether to remove temporary files after execution.
    return_info : bool
        Whether to return a dictionary with intermediate results.
    ignore : sequence
        Which rules to ignore. Each element should be a rule code (e.g., 'E402').
    ruff_params : dict
        Additional parameters for ruff configuration.
    """
    try:
        subprocess.run(['ruff', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exception:
        raise ImportError('Install ruff') from exception

    path = path or get_notebook_path()
    if path is None:
        raise ValueError('Provide path to Jupyter Notebook or run `ruff_notebook` inside of it!')

    # Convert notebook to a script
    path_script = os.path.splitext(path)[0] + '.py'
    script_name = os.path.basename(path_script)

    code, cell_line_numbers = notebook_to_script(path_notebook=path, path_script=path_script, return_info=True).values()

    # Create ruff config file
    if config is None:
        path_ruff_toml = os.path.splitext(path)[0] + '.ruff.toml'
        ruff_toml = generate_ruff_toml(path_ruff_toml, ignore=ignore, **ruff_params)
    else:
        path_ruff_toml = config
        # Open config for output
        if return_info:
            with open(path_ruff_toml, 'r', encoding='utf-8') as configfile:
                ruff_toml = configfile.read()

    # Run ruff on script with configuration
    try:
        result = subprocess.run([
            'ruff', 'check', path_script, '--config', path_ruff_toml, '--output-format', 'full'
        ], capture_output=True, text=True, check=False)
        
        report = result.stdout
        errors = result.stderr
    except Exception as e:
        report = ""
        errors = str(e)

    # Prepare custom report
    output = []
    
    if not report.strip() and not errors.strip():
        output.append("No issues found.")
    else:
        # Parse ruff's full format output
        lines = report.split('\n')
        current_error = None
        
        for line in lines:
            if not line.strip():
                continue
                
            # Look for error code lines like "E401 [*] Multiple imports on one line"
            if line and not line.startswith(' ') and not line.startswith('-->') and not line.startswith('|') and not line.startswith('help:'):
                # This is an error header line
                current_error = {'code': '', 'message': '', 'line': 0, 'cell': -1}
                parts = line.split(' ', 2)
                if len(parts) >= 2:
                    current_error['code'] = parts[0]
                    if len(parts) >= 3:
                        # Remove [*] if present and get message
                        message = parts[2]
                        if message.startswith('[*] '):
                            message = message[4:]
                        current_error['message'] = message
            
            # Look for location lines like "--> /tmp/test_notebook.py:9:1"
            elif line.strip().startswith('-->') and current_error is not None:
                location_part = line.strip()[4:].strip()  # Remove "-> "
                if path_script in location_part:
                    try:
                        # Extract line number from "filename:line:col"
                        filename_part = location_part.split(':')
                        if len(filename_part) >= 2:
                            code_line_number = int(filename_part[1])
                            current_error['line'] = code_line_number
                            
                            # Locate the cell and line inside the cell
                            for cell_number, cell_ranges in cell_line_numbers.items():
                                if code_line_number in cell_ranges:
                                    cell_line_number = code_line_number - cell_ranges[0]
                                    current_error['cell'] = cell_number
                                    current_error['cell_line'] = cell_line_number
                                    break
                            else:
                                current_error['cell'] = -1
                                current_error['cell_line'] = code_line_number
                            
                            # Add to output
                            message = f'Cell {current_error["cell"]}:{current_error["cell_line"]}, code={current_error["code"]}'
                            message += f'\n     Ruff message ::: {current_error["message"]}\n'
                            output.append(message)
                    except (ValueError, IndexError):
                        pass

        if errors.strip():
            output.append(f'\nRuff errors:\n{errors}')

    output_text = '\n'.join(output).strip()

    if remove_files:
        if os.path.exists(path_script):
            os.remove(path_script)
        if config is None and os.path.exists(path_ruff_toml):
            os.remove(path_ruff_toml)

    if printer is not None:
        printer(output_text)

    if return_info:
        enumerated_code = code.split('\n')
        n_digits = len(str(len(enumerated_code)))
        enumerated_code = [f'{i:0>{n_digits}}    ' + item
                           for i, item in enumerate(enumerated_code, start=1)]
        enumerated_code = '\n'.join(enumerated_code)

        return {
            'report': StringWithDisabledRepr(output_text),
            'code': StringWithDisabledRepr(code),
            'enumerated_code': StringWithDisabledRepr(enumerated_code),
            'ruff_toml': StringWithDisabledRepr(ruff_toml if config is None else ''),
            'ruff_errors': StringWithDisabledRepr(errors),
            'ruff_report': StringWithDisabledRepr(report),
        }
    return None


# Backward compatibility alias
pylint_notebook = ruff_notebook