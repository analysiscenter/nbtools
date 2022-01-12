""" Utility functions. """
#pylint: disable=redefined-builtin, protected-access
import os
import re
from blessed import Terminal


COLORS = Terminal(kind=os.getenv('TERM'), force_styling=True)
COLORS._normal = u'\x1b[0;10m'


COLOR_REPLACER = re.compile(r"\x1b\[[;\d]*[A-Za-z]").sub
def true_len(string):
    """ !!. """
    length = len(COLOR_REPLACER('', string))
    for symbol in '％℃':
        length += string.count(symbol)
    return length

def true_rjust(string, width, fillchar=' '):
    """ !!. """
    return fillchar * (width - true_len(string)) + string

def true_cjust(string, width, fillchar=' '):
    """ !!. """
    true_pad = width - true_len(string)
    left = true_pad // 2
    right = true_pad - left
    return fillchar * left + string + fillchar * right


def format_memory(number, format=3):
    """ !!. """
    level_to_unit = {1 : 'KB', 2 : 'MB', 3 : 'GB'}
    unit_to_level = {value : key for key, value in level_to_unit.items()}

    if isinstance(format, int):
        level, unit = format, level_to_unit[format]
    elif isinstance(format, str):
        level, unit = unit_to_level[format], format

    rounded = round(number / (1024 ** level), 1 if level>=3 else None)
    return rounded, unit
