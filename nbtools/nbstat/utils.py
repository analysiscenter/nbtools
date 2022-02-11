""" Utility functions. """
#pylint: disable=redefined-builtin
import re
import platform
import linecache

import psutil



# Faster versions of some of `psutil` commands, available only on Linux
SYSTEM = platform.system()

def pid_to_name_generic(pid):
    """ Get `name` of a process by its PID. Platform-agnostic. """
    try:
        process = psutil.Process(pid)
        name = process.name()
    except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
        name = ''
    return name

def pid_to_name_linux(pid):
    """ Get `name` of a process by its PID on Linux. ~20% speed-up, compared to the `generic` version. """
    try:
        line = linecache.getline(f'/proc/{pid}/status', 1)
        name = line.strip().split()[1]
    except Exception: #pylint: disable=broad-except
        name = ''
    return name

pid_to_name = pid_to_name_linux if SYSTEM == 'Linux' else pid_to_name_generic


def pid_to_ngid_generic(pid):
    """ Get NGID of a process by its PID. """
    return pid

def pid_to_ngid_linux(pid):
    """ Get NGID of a process by its PID on Linux. Used as the PID on host for a process inside a container. """
    try:
        line = linecache.getline(f'/proc/{pid}/status', 5)
        ngid = line.strip().split()[1]
        ngid = int(ngid)
    except Exception: #pylint: disable=broad-except
        ngid = pid
    return ngid or pid

pid_to_ngid = pid_to_ngid_linux if SYSTEM == 'Linux' else pid_to_ngid_generic



# Utilities to work with strings containing terminal sequences
COLOR_REPLACER = re.compile(r"\x1b\[[;\d]*[A-Za-z]").sub
def true_len(string):
    """ Compute printable length of the string, ignoring terminal symbols like color / formatters / system signals. """
    length = len(COLOR_REPLACER('', string))
    for symbol in '％℃':
        length += string.count(symbol)
    return length

def true_rjust(string, width, fillchar=' '):
    """ Justify the string to the right, using printable length as the width. """
    return fillchar * (width - true_len(string)) + string

def true_center(string, width, fillchar=' '):
    """ Justify the string to the center, using printable length as the width. """
    true_pad = width - true_len(string)
    left = true_pad // 2
    right = true_pad - left
    return fillchar * left + string + fillchar * right



class FiniteList(list):
    """ List with finite number of elements: if the size is more """
    def __init__(self, *args, size=10, **kwargs):
        self.size = size
        super().__init__(*args, **kwargs)

    def append(self, obj):
        """ Append to the list. If length is bigger than allowed, remove the first element. """
        if len(self) >= self.size:
            self.pop(0)
        super().append(obj)

    def get_average(self, size=None):
        """ Compute average value of the last `size` elements.
        Returns `None`, if there are less than `size // 2` elements in the list.
        """
        size = size or self.size
        if len(self) > size // 2:
            sublist = self[-size:]
            return round(sum(sublist) / len(sublist))
        return None



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
