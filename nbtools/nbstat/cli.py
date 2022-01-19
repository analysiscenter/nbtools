""" !!. """
#pylint: disable=redefined-outer-name
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from time import time, sleep
from blessed import Terminal

from .resource_formatter import NBSTAT_FORMATTER, DEVICESTAT_FORMATTER, GPUSTAT_FORMATTER
from .resource_inspector import ResourceInspector



def main(name, interval=None):
    """ !!. """
    # Attach SIGPIPE handler to properly handle broken pipe
    try: # sigpipe not available under windows. just ignore in this case
        import signal # pylint: disable=import-outside-toplevel
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception: # pylint: disable=broad-except
        pass

    formatter, view_args = make_parameters(name)

    # Create handler to get formatted table
    inspector = ResourceInspector(formatter)
    partial_function = lambda: inspector.get_view(name, **view_args)

    # Print table
    interval = view_args.pop('interval') or interval
    if not interval:
        output_once(partial_function)
    else:
        output_looped(partial_function, interval=interval)


NAME_TO_VIEW = {
    'nbstat' : 'nbstat', 'nbwatch' : 'nbstat',
    'devicestat' : 'devicestat', 'devicewatch' : 'devicestat',
    'gpustat' : 'gpustat', 'gpuwatch' : 'gpustat',
}

VIEW_TO_FORMATTER = {
    'nbstat' : NBSTAT_FORMATTER,
    'devicestat' : DEVICESTAT_FORMATTER,
    'gpustat' : GPUSTAT_FORMATTER,
}

DEFAULTS = {
    'index_condition' : None,
    'interval' : 0.0,
    'verbose' : 0,

    'show_all' : False,
    'show' : [],
    'hide' : [],
    'hide_similar' : True,

    'add_supheader' : True,
    'add_header' : True,
    'add_footnote' : False,

    'separate_supheader' : False,
    'separate_header' : True,
    'separate_index' : True,

    'process_memory_format' : 'GB',
    'device_memory_format' : 'MB',
}

def make_parameters(name):
    """ !!. """
    # Set defaults
    defaults = dict(DEFAULTS)
    if 'device' in name:
        defaults.update({'separate_index' : False,})

    if 'watch' in name:
        defaults.update({'add_footnote' : True})

    # Fetch formatter: used to tell which columns can be shown/hidden from the table in documentation
    view = NAME_TO_VIEW[name]
    formatter = VIEW_TO_FORMATTER[view]

    # Parse command line arguments
    # Use `store_const` instad of `store_true` to keep `None` values, if not passed explicitly
    docstring = globals()[name].__doc__.strip()
    help_verbose_0 = '\nDefault `verbose=0` shows only script/notebooks that use devices.' if 'nb' in name else ''
    linesep = '\n '
    parser = ArgumentParser(description=f'{docstring} {help_verbose_0 }', formatter_class=RawTextHelpFormatter)

    # Positional argument: filtering condition on index
    parser.add_argument('index_condition', nargs='?',
                        help=('Regular expression for filtering entries in the table index. '
                              'For example, `.*.ipynb` allows to look only at Jupyter Notebooks.'))

    # NB-specific argument: verbosity
    if 'nb' in name:
        group_verbose = parser.add_mutually_exclusive_group()
        help_verbose_1 = 'Set `verbose=1`: show all processes for entries with at least one used device.'
        help_verbose_2 = 'Set `verbose=2`: show all processes for all entries.'
        group_verbose.add_argument('-v', action='store_const', const=1, dest='verbose', help=help_verbose_1)
        group_verbose.add_argument('-V', action='store_const', const=2, dest='verbose', help=help_verbose_2)

    # Interval
    if 'watch' in name:
        help_interval = 'Interval (in seconds) between table updates.'
    else:
        help_interval = ('If provided, then the watch mode is used. '
                         'Value sets the interval (in seconds) between table updates.')
    parser.add_argument('-i', '--interval', '-n', '--watch', nargs='?', type=float, help=help_interval + linesep)

    # Show / hide columns by their aliases
    help_show = ('Additional columns to gather information about and show in the table.\n'
                 f'By default, following columns are not included: \n{formatter.excluded_names}')
    help_hide = ('Columns to exclude from the table, which also stops gathering information about them.\n'
                 f'By default, following columns are included: \n{formatter.included_names}')
    parser.add_argument('--show', nargs='*', help=help_show)
    parser.add_argument('--hide', nargs='*', help=help_hide)
    parser.add_argument('--show-all', action='store_const', const=True, help='Show all possible columns.')
    parser.add_argument('--hide-all', action='store_const', const=True,
                        help='Why would you ever want this? Does nothing.' + linesep)

    # Hidable columns
    help_changeable = 'Use this parameter to change this behavior.'
    help_hidable = f'By default, parts of rows with the same values as in previous row are hidden. {help_changeable}'
    parser.add_argument('--show-similar', action='store_const', const=False, dest='hide_similar', help=help_hidable)

    parser.add_argument('--hide-supheader', action='store_const', const=False, dest='add_supheader',
                        help=f'By default, we show current time, driver and CUDA versions. {help_changeable}')
    parser.add_argument('--hide-header', action='store_const', const=False, dest='add_header',
                        help=f'By default, we show a row with column names in the table. {help_changeable}')

    if 'watch' in name:
        parser.add_argument('--hide-footnote', action='store_const', const=False, dest='add_footnote',
                            help=f'By default, we show a row with total resource usage. {help_changeable}{linesep}')
    else:
        parser.add_argument('--show-footnote', action='store_const', const=True, dest='add_footnote',
                            help=f'Show a row with total system resource usage. {linesep}')

    parser.add_argument('--process-memory-format', type=str, default='GB',
                        help='Units of measurements for non-device memory stats, `GB` by default.')
    parser.add_argument('--device-memory-format', type=str,
                        help='Units of measurements for device memory stats, `MB` by default.' + linesep)

    # Separators
    group_separators = parser.add_mutually_exclusive_group()
    group_separators.add_argument('--add-separators', action='store_const', const=True, dest='separators',
                                  help='Turn on all the table separators.')
    group_separators.add_argument('--hide-separators', action='store_const', const=False, dest='separators',
                                  help='Turn off all the table separators.')

    # Merge defaults and passed arguments
    parser.set_defaults(**defaults)
    argv = list(sys.argv[1:])
    args = vars(parser.parse_args(argv))

    # Update
    separators = args.pop('separators')
    if separators is not None:
        for key in ['separate_supheader', 'separate_header', 'separate_index']:
            args[key] = separators

    if args.pop('hide_all'):
        pass

    # Update formatter with cmd arguments
    if args.pop('show_all'):
        formatter.include_all()

    for resource in args.pop('show'):
        formatter[resource] = True

    for resource in args.pop('hide'):
        formatter[resource] = False


    return formatter, args


def output_once(partial_function):
    """ !!. """
    try:
        view = partial_function()
        print(view)
    except Exception as e: # pylint: disable=broad-except
        _ = e
        print('Error on getting system information!' + str(e))
        raise e

def output_looped(partial_function, interval=0.5):
    """ !!. """
    terminal = Terminal()

    with terminal.fullscreen():
        try:
            counter = 0
            while True:
                counter += 1
                try:
                    start_time = time()
                    view = partial_function()
                    start_position = terminal.clear if counter % 10 == 0 else terminal.move(0, 0)
                    print(start_position, view, ' ', terminal.clear_eol, sep='')

                    remaining_time = interval - (time() - start_time)
                    if remaining_time > 0.0:
                        sleep(remaining_time)

                except Exception as e: # pylint: disable=broad-except
                    _ = e
                    sys.stderr.write('Error on getting system information!' + str(e))
                    sys.exit(1)

        except KeyboardInterrupt:
            return 0

def nbstat():
    """ N!!. """
    return main('nbstat')

def nbwatch():
    """ NW!!. """
    return main('nbwatch', interval=1.)

def devicestat():
    """ D!!. """
    return main('devicestat')

def devicewatch():
    """ DB!!. """
    return main('devicewatch', interval=1.)

if __name__ == '__main__':
    nbwatch()
