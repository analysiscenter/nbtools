""" Utility functions. """
#pylint: disable=redefined-builtin


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
