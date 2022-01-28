""" !!. """


class StringWithDisabledRepr(str):
    """ String with disabled repr. Used to avoid cluttering repr from function outputs. """
    def __repr__(self):
        return f'<StringWithDisabledRepr at {hex(id(self))}. Use `str`/`print` explicitly!>'


def notebook_to_script(path_notebook, path_script, ignore_markdown=True, return_info=False):
    import nbformat #pylint: disable=import-outside-toplevel
    notebook = nbformat.read(path_notebook, as_version=4)

    code_lines = []
    cell_line_numbers = {}

    for i, cell in enumerate(notebook['cells'], start=1):
        if ignore_markdown and cell['cell_type'] != 'code':
            continue

        cell_lines = cell['source'].split('\n')
        cell_lines.insert(0, f'\n### [{i}] cell')

        # Remove cell/line magics
        for j, line in enumerate(cell_lines):
            if line.startswith('%') or line.startswith('!'):
                cell_lines[j] = '### ' + line

        code_line_number = len(code_lines)
        cell_line_numbers[i] = range(code_line_number, code_line_number + len(cell_lines))

        code_lines.extend(cell_lines)

    code = '\n'.join(code_lines).strip()

    with open(path_script, 'w') as file:
        file.write(code)

    if return_info:
        return {'code': StringWithDisabledRepr(code),
                'cell_line_numbers': cell_line_numbers}
    return

