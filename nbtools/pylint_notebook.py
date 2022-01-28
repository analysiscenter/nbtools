""" !!. """
import os
import sys

from .core import StringWithDisabledRepr, notebook_to_script



PYLINTRC_TEMPLATE = """
[DESIGN]
max-line-length={max_line_length}
variable-rgx=(.*[a-z][a-z0-9_]{{1,30}}|[a-z_])$ # snake_case + single letters
argument-rgx=(.*[a-z][a-z0-9_]{{1,30}}|[a-z_])$ # snake_case + single letters

[MESSAGE CONTROL]
disable=too-few-public-methods, unsubscriptable-object, no-member, too-many-lines, too-many-locals,
        arguments-renamed, arguments-differ, multiple-statements, invalid-name,
        missing-module-docstring, missing-final-newline, redefined-outer-name,
        wrong-import-position, no-name-in-module, import-error,
        unnecessary-semicolon, trailing-whitespace, trailing-newlines,
        {disable}

good-names=bar, df, fn
additional-builtins=display, get_ipython
"""


def generate_pylintrc(path, disable=(), enable=(), max_line_length=120, **pylint_params):
    """ !!. """
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

    with open(path, 'w') as file:
        file.write(pylintrc)

    return pylintrc


def pylint_notebook(path, options=(), disable=(), enable=(), printer=print,
                    remove_files=True, return_info=False, **pylint_params):
    """ !!. """
    from pylint import epylint as lint #pylint: disable=import-outside-toplevel


    # Convert notebook to a script
    path_script = os.path.splitext(path)[0] + '.py'
    script_name = os.path.basename(path_script)

    code, cell_line_numbers = notebook_to_script(path, path_script, return_info=True).values()

    # Create pylintrc file
    path_pylintrc = os.path.splitext(path)[0] + '.pylintrc'
    pylintrc = generate_pylintrc(path_pylintrc, disable=disable, enable=enable, **pylint_params)

    # Run pylint on script with pylintrc configuration
    pylint_cmdline = ' '.join([path_pylintrc, f'--rcfile {path_pylintrc}', *options])
    pylint_stdout, pylint_stderr = lint.py_run(pylint_cmdline, return_std=True)

    errors = pylint_stderr.getvalue()
    report = pylint_stdout.getvalue()

    # Prepare custom report
    output = []

    for line in report.split('\n'):
        if 'rated' in line:
            output.insert(0, line.strip(' '))
            output.insert(1, '–' * (len(line) - 1))

        elif path_script in line or script_name in line:
            line = line.replace(path_script, '__').replace(script_name, '__')

            # Locate the cell and line inside the cell
            code_line_number = int(line.split(':')[1])
            for cell_number, cell_ranges in cell_line_numbers.items():
                if code_line_number in cell_ranges:
                    cell_line_number = code_line_number - cell_ranges[0] - 1
                    break

            # Find error_code and error_name: for example, `C0123` and `invalid-name`
            position_left  = line.find('(') + 1
            position_right = line.find(')') - 1
            error_message = line[position_left : position_right]
            error_human_message = line[position_right + 2:]
            error_code, error_name, *_ = error_message.split(',')
            error_name = error_name.strip()

            # Make new message
            message = f'Cell {cell_number}:{cell_line_number}, code={error_code}, name={error_name}'
            message += f'\n     Pylint message ::: {error_human_message}\n'
            output.append(message)

    output = '\n'.join(output).strip()

    if remove_files:
        os.remove(path_script)
        os.remove(path_pylintrc)

    if printer is not None:
        printer(output)

    if return_info:
        return {
            'code' : StringWithDisabledRepr(code),
            'pylintrc' : StringWithDisabledRepr(pylintrc),
            'report' : StringWithDisabledRepr(output),
            'pylint_errors' : StringWithDisabledRepr(errors),
            'pylint_report' : StringWithDisabledRepr(report),
        }
    return
