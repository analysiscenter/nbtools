""" Command line interface of `nbstat`.
Also provides `nbwatch`, `devicestat` and `devicewatch` functions.
"""
#pylint: disable=redefined-outer-name, too-many-nested-blocks
import sys
import traceback
from inspect import cleandoc
from time import time
from argparse import ArgumentParser, RawTextHelpFormatter

from blessed import Terminal

from .resource import Resource
from .resource_formatter import NBSTAT_FORMATTER, DEVICESTAT_FORMATTER, GPUSTAT_FORMATTER
from .resource_inspector import ResourceInspector



def main(name, interval=None):
    """ Run command `name`. If `interval` is given, continuously output it to a terminal in fullscreen mode. """
    # Attach SIGPIPE handler to properly handle broken pipe
    try: # sigpipe not available under windows. just ignore in this case
        import signal # pylint: disable=import-outside-toplevel
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception: # pylint: disable=broad-except
        pass

    # Make parameters for requested view
    inspector = ResourceInspector()
    formatter, view_args = make_parameters(name)

    # Parse interval
    interval = view_args.get('interval') or interval
    interval = max(interval, 0.1) if interval is not None else None
    view_args['interval'] = interval

    # Print table
    if not interval:
        output_once(inspector, name, formatter, view_args)
    else:
        # If in `watch` mode, prepare other handler as well
        other_name = 'devicewatch' if name.startswith('nb') else 'nbwatch'
        other_formatter, other_view_args = make_parameters(other_name)
        other_view_args['interval'] = interval

        output_looped(inspector, name, formatter, view_args,
                      other_name, other_formatter, other_view_args,
                      interval=interval)


def output_once(inspector, name, formatter, view_args):
    """ Output visualization to a stdout once. """
    try:
        view = inspector.get_view(name=name, formatter=formatter, **view_args)
        print(view)
    except Exception as e: # pylint: disable=broad-except
        _ = e
        print('Error on getting system information!' + str(e))
        raise e

def output_looped(inspector, name, formatter, view_args,
                  other_name, other_formatter, other_view_args, interval=0.5):
    """ Output visualization to a stdout once each `interval` seconds in a fullscreen mode. """
    terminal = Terminal()

    initial_view_args = dict(view_args)
    initial_other_view_args = dict(other_view_args)

    with terminal.cbreak(), terminal.fullscreen():
        try: # catches keyboard interrupts to exit gracefully
            counter = 0
            while True:
                counter += 1

                try: # catches `nbstat` exceptions
                    # Print the view
                    start_time = time()
                    view = inspector.get_view(name=name, formatter=formatter, **view_args)
                    start_position = terminal.clear if counter % 10 == 0 else terminal.move(0, 0)
                    print(start_position, view, ' ', terminal.clear_eol, sep='')

                    # Wait for the input key
                    remaining_time = interval - (time() - start_time)
                    if remaining_time > 0.0:
                        inkey = terminal.inkey(timeout=remaining_time)
                    else:
                        inkey = terminal.inkey(timeout=interval)

                    if inkey:
                        recognized = True

                        # Tab to switch views. Re-print immediately
                        if inkey.code in [terminal.KEY_TAB, terminal.KEY_BTAB]:
                            # Swap every variable
                            name, other_name = other_name, name
                            formatter, other_formatter = other_formatter, formatter
                            view_args, other_view_args = other_view_args, view_args
                            initial_view_args, initial_other_view_args = initial_other_view_args, initial_view_args

                        elif inkey == 's':
                            view_args['separate_index'] = not view_args['separate_index']
                        elif inkey == 'r':
                            view_args = dict(initial_view_args)
                        elif inkey == 'b':
                            formatter.toggle_bars()
                        elif inkey == 'm':
                            if formatter[Resource.DEVICE_UTIL]:
                                formatter[Resource.DEVICE_UTIL_MA] = not formatter[Resource.DEVICE_UTIL_MA]
                        elif inkey == 'q':
                            raise KeyboardInterrupt
                        else:
                            recognized = False

                        if recognized:
                            view = inspector.get_view(name=name, formatter=formatter, **view_args)
                            print(terminal.clear, view, ' ', terminal.clear_eol, sep='')
                        else:
                            print(f'Unrecognized key={inkey}, code={inkey.code}.')

                except Exception: # pylint: disable=broad-except
                    sys.stderr.write(traceback.format_exc())
                    sys.stderr.write('Error on getting system information!')
                    sys.exit(1)

        except KeyboardInterrupt:
            return 0

def nbstat():
    """ Collect all running Jupyter Notebooks and Python scripts. For each of their processes,
    show detailed information on their device usage and other resource utilization.
    """
    return main('nbstat')

def nbwatch():
    """ Collect all running Jupyter Notebooks and Python scripts. For each of their processes,
    continuously show detailed information on their device usage and other resource utilization.
    """
    return main('nbwatch', interval=1.)

def devicestat():
    """ Collect information about all NVIDIA devices. For each of them,
    show detailed information about utilization and processes.
    """
    return main('devicestat')

def devicewatch():
    """ Collect information about all NVIDIA devices. For each of them,
    continuously show detailed information about utilization and processes.
    """
    return main('devicewatch', interval=1.)



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
    'window': 20,
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

    'force_styling' : True,
    'process_memory_format' : 'GB',
    'device_memory_format' : 'MB',
}

def make_parameters(name):
    """ Parse parameters from command line into dictionary.
    Use `store_const` instad of `store_true` to keep `None` values, if not passed explicitly
    """
    # Set defaults
    defaults = dict(DEFAULTS)
    if 'device' in name:
        defaults.update({'separate_index' : False,})

    if 'watch' in name:
        defaults.update({'add_footnote' : True})

    # Fetch formatter: used to tell which columns can be shown/hidden from the table in documentation
    view = NAME_TO_VIEW[name]
    formatter = VIEW_TO_FORMATTER[view]

    # Command line arguments
    argv = sys.argv[1:]
    if 'device' in name:
        argv = [arg for arg in argv if arg not in ['-v', '-V']]


    # General doc
    docstring = cleandoc(globals()[name].__doc__)
    help_verbose_0 = 'Default `verbose=0` shows only script/notebooks that use devices.' if 'nb' in name else ''
    help_watch = '\nSet `interval` to continuously update displayed table.' if 'watch' not in name else '\n'
    help_keystrokes = (
        'While in the `watch` mode, you can use keystrokes to modify displayed view:'
        '\n  - `tab` — swaps views, from `nbwatch` to `devicewatch` and back.'
        '\n  - `b` — toggles bar representation for some of the resources: in addition to its value, show colored bar.'
        '\n  - `m` — toggles moving averages for some of the resources: values are averaged across the last iterations.'
        '\n  - `s` — toggles table separators.')
    parser = ArgumentParser(description='\n'.join([docstring, help_verbose_0, help_watch, help_keystrokes]),
                            formatter_class=RawTextHelpFormatter)
    linesep = '\n '

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
    parser.add_argument('-i', '--interval', '-n', '--watch', nargs='?', type=float, help=help_interval)

    help_window = 'Number of table updates to use for computing moving averages.'
    parser.add_argument('-w', '--window', nargs='?', type=int, help=help_window + linesep)

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
    group_separators.add_argument('--show-separators', action='store_const', const=True, dest='separators',
                                  help='Turn on all the table separators.')
    group_separators.add_argument('--hide-separators', action='store_const', const=False, dest='separators',
                                  help='Turn off all the table separators.')

    parser.add_argument('--suppress-color', action='store_const', const=False, dest='force_styling',
                        help='Disable colors in the visualization.')

    # Merge defaults and passed arguments
    parser.set_defaults(**defaults)
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
        if resource in formatter:
            formatter[resource] = True

    for resource in args.pop('hide'):
        if resource in formatter:
            formatter[resource] = False

    return formatter, args


if __name__ == '__main__':
    nbwatch()
