""" Utility functions. """
#pylint: disable=redefined-builtin, protected-access
import os
import re
from blessed import Terminal


COLORS = Terminal(kind=os.getenv('TERM'), force_styling=True)
COLORS._normal = '\x1b[0;10m'


COLOR_REPLACER = re.compile(r"\x1b\[[;\d]*[A-Za-z]").sub
def true_len(string):
    """ Compute actual length of the string, ignoring terminal symbols like color / formatters / system signals. """
    length = len(COLOR_REPLACER('', string))
    for symbol in '％℃':
        length += string.count(symbol)
    return length

def true_rjust(string, width, fillchar=' '):
    """ Justify the string to the right, using actual length as the width. """
    return fillchar * (width - true_len(string)) + string

def true_cjust(string, width, fillchar=' '):
    """ Justify the string to the center, using actual length as the width. """
    true_pad = width - true_len(string)
    left = true_pad // 2
    right = true_pad - left
    return fillchar * left + string + fillchar * right


def format_memory(number, format=3):
    """ Format memory in bytes to a desired format level. """
    level_to_unit = {1 : 'KB', 2 : 'MB', 3 : 'GB'}
    unit_to_level = {value : key for key, value in level_to_unit.items()}

    if isinstance(format, int):
        level, unit = format, level_to_unit[format]
    elif isinstance(format, str):
        level, unit = unit_to_level[format], format

    rounded = round(number / (1024 ** level), 1 if level>=3 else None)
    return rounded, unit
