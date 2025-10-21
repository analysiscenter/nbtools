""" Command line interface of `nbstat`.
Also provides `nbwatch`, `devicestat` and `devicewatch` functions.
"""
import sys
import traceback
from inspect import cleandoc
from time import time
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from blessed import Terminal

from .resource import Resource
from .resource_formatter import NBSTAT_FORMATTER, DEVICESTAT_FORMATTER, GPUSTAT_FORMATTER
from .resource_inspector import ResourceInspector
from .utils import true_len



def main(name, interval=None):
    """ Run command `name`. If `interval` is given, continuously output it to a terminal in fullscreen mode. """
    # Attach SIGPIPE handler to properly handle broken pipe
    try: # sigpipe not available under windows. just ignore in this case
        import signal  # noqa: E402
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:  # noqa: BLE001, S110
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
    except Exception as e:
        _ = e
        print('Error on getting system information!' + str(e))
        raise e

def output_looped(inspector, name, formatter, view_args,
                  other_name, other_formatter, other_view_args, interval=0.5):
    """ Output visualization to a stdout once each `interval` seconds in a fullscreen mode. """
    terminal = Terminal()

    initial_view_args = dict(view_args)
    initial_other_view_args = dict(other_view_args)
    initial_formatter = formatter.copy()
    initial_other_formatter = other_formatter.copy()

    with terminal.fullscreen(), terminal.cbreak(), terminal.hidden_cursor():
        try: # catches keyboard interrupts to exit gracefully
            counter = 0
            prev_len = 0
            force_clear = False

            while True:
                counter += 1

                try: # catches `nbstat` exceptions
                    # Get the view
                    start_time = time()
                    view = inspector.get_view(name=name, formatter=formatter, **view_args)
                    current_len = true_len(view)
                    view_args['vertical_change'] = 0

                    # Select starting position: if needed, redraw the entire screen, otherwise just move cursor position
                    if abs(current_len - prev_len) > 100 or force_clear or (counter % 100 == 0):
                        start_position = terminal.clear
                        force_clear = False
                        counter = 0
                    else:
                        start_position = terminal.move(0, 0)
                    prev_len = current_len

                    # Actual print
                    print(start_position, view, sep='', end='', flush=True)

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
                            initial_formatter, initial_other_formatter = initial_other_formatter, initial_formatter

                        # Additional lines. TODO: a separate screen with textual help...?
                        elif inkey == 'f':
                            view_args['add_footnote'] = not view_args['add_footnote']
                        elif inkey == 'h':
                            view_args['add_help'] = not view_args['add_help']

                        # General controls
                        elif inkey == 's':
                            view_args['separate_index'] = not view_args['separate_index']
                        elif inkey == 'S':
                            view_args['separate_header'] = not view_args['separate_header']
                            view_args['separate_table'] = not view_args['separate_table']
                        elif inkey == 'r':
                            view_args = dict(initial_view_args)
                            formatter = initial_formatter.copy()
                        elif inkey == 'b':
                            formatter.toggle_bars()
                        elif inkey == 'm':
                            if formatter[Resource.DEVICE_UTIL]:
                                formatter[Resource.DEVICE_UTIL_MA] = not formatter[Resource.DEVICE_UTIL_MA]
                        elif inkey == 'v':
                            view_args['verbose'] = 2 - view_args['verbose'] # toggle between `0` and `2`

                        # F1-F4: regular stats
                        elif inkey.code == terminal.KEY_F1:
                            formatter[Resource.PID] = not formatter[Resource.PID]
                        elif inkey.code == terminal.KEY_F2:
                            formatter[Resource.PPID] = not formatter[Resource.PPID]
                        elif inkey.code == terminal.KEY_F3:
                            formatter[Resource.CPU] = not formatter[Resource.CPU]
                        elif inkey.code == terminal.KEY_F4:
                            formatter[Resource.RSS] = not formatter[Resource.RSS]

                        # F5-F8: device stats
                        elif inkey.code == terminal.KEY_F5:
                            if Resource.DEVICE_SHORT_ID in formatter:
                                formatter[Resource.DEVICE_SHORT_ID] = not formatter[Resource.DEVICE_SHORT_ID]
                            if Resource.DEVICE_ID in formatter:
                                formatter[Resource.DEVICE_ID] = not formatter[Resource.DEVICE_ID]
                        elif inkey.code == terminal.KEY_F6:
                            formatter[Resource.DEVICE_PROCESS_MEMORY_USED] = \
                                not formatter[Resource.DEVICE_PROCESS_MEMORY_USED]
                        elif inkey.code == terminal.KEY_F7:
                            formatter[Resource.DEVICE_UTIL] = not formatter[Resource.DEVICE_UTIL]
                        elif inkey.code == terminal.KEY_F8:
                            formatter[Resource.DEVICE_TEMP] = not formatter[Resource.DEVICE_TEMP]

                        # shift F1-F4
                        elif inkey.code == terminal.KEY_F13:
                            formatter[Resource.TYPE] = not formatter[Resource.TYPE]
                        elif inkey.code == terminal.KEY_F14:
                            formatter[Resource.STATUS] = not formatter[Resource.STATUS]
                        elif inkey.code == terminal.KEY_F15:
                            formatter[Resource.CREATE_TIME] = not formatter[Resource.CREATE_TIME]
                        elif inkey.code == terminal.KEY_F16:
                            formatter[Resource.PATH] = not formatter[Resource.PATH]

                        # Vertical scroll
                        elif inkey.code == terminal.KEY_DOWN:
                            view_args['vertical_change'] = +1
                        elif inkey.code == terminal.KEY_UP:
                            view_args['vertical_change'] = -1
                        elif inkey.code == terminal.KEY_PGDOWN:
                            view_args['vertical_change'] = +terminal.height // 2
                        elif inkey.code == terminal.KEY_PGUP:
                            view_args['vertical_change'] = -terminal.height // 2

                        elif inkey == 'q':
                            raise KeyboardInterrupt
                        else:
                            recognized = False

                        if recognized:
                            force_clear = True
                        else:
                            print(f'\nUnrecognized key={inkey}, code={inkey.code}.')

                except Exception as e:  # noqa: BLE001
                    sys.stderr.write(traceback.format_exc())
                    sys.stderr.write('Error on getting system information!')
                    sys.stderr.write(str(e))
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

    'add_header' : True,
    'add_footnote' : False,
    'add_help': False,

    'use_cache': False,
    'vertical_change': 0,

    'separate_header': True,
    'separate_index': True,
    'separate_table': True,

    'force_styling' : True,
    'process_memory_format' : 'GB',
    'device_memory_format' : 'MB',
}

def make_parameters(name):
    """ Parse parameters from the command line into a dictionary.
    Use `store_const` instad of `store_true` to keep `None` values, if not passed explicitly
    """
    # Set defaults
    defaults = dict(DEFAULTS)
    if 'device' in name:
        defaults.update({'separate_index' : False,})

    if 'watch' in name:
        defaults.update({'use_cache': True, 'add_footnote': True, 'add_help': True})

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
    help_keystrokes = ('While in the `watch` mode, you can use keystrokes to modify the displayed view. '
                       'Hit `h` to toggle help.')
    parser = ArgumentParser(description='\n'.join([docstring, help_verbose_0, help_watch, help_keystrokes]),
                            formatter_class=RawDescriptionHelpFormatter)
    linesep = '\n '

    # Positional argument: filtering condition on index
    parser.add_argument('index_condition', nargs='?',
                        help=('Regular expression for filtering processes, applied to their path. '
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
    parser.add_argument('-i', '--interval', nargs='?', type=float, help=help_interval)

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

    parser.add_argument('--hide-header', action='store_const', const=False, dest='add_header',
                        help=f'By default, we show a row with column names in the table. {help_changeable}')

    if 'watch' in name:
        parser.add_argument('--hide-footnote', action='store_const', const=False, dest='add_footnote',
                            help=f'By default, we show info about resource usage. {help_changeable}{linesep}')
        parser.add_argument('--hide-help', action='store_const', const=False, dest='add_help',
                            help=f'By default, we show valid key strokes. {help_changeable}{linesep}')
    else:
        parser.add_argument('--show-footnote', action='store_const', const=True, dest='add_footnote',
                            help=f'Show info about resource usage. {linesep}')
        parser.add_argument('--show-help', action='store_const', const=True, dest='add_footnote',
                            help=f'Show valid key strokes. {linesep}')

    parser.add_argument('--process-memory-format', type=str, default='GB',
                        help='Units of measurements for non-device memory stats like RSS, `GB` by default.')
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
        for key in ['separate_header', 'separate_index', 'separate_footnote']:
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
