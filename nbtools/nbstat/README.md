# NBstat

A command-line utility to monitor running Jupyter Notebooks, their system and NVIDIA device utilization.

This documentation explains all of the `nbstat` options and shows examples of its advanced usage. It can be also accessed via `nbstat --help`.

For more in-depth look at the inner workings, check out the [DEV documentation](DEV.md).

<img src="./../../images/nbstat.gif" width="70%"/>

## Views

The `nbstat` table information is, roughy, `for each Jupyter Notebook show all of its processes with system/device utilization information`. Along with the `nbstat`, we provide following commands:

* `devicestat` — a transposed view of the same data: `for each NVIDIA device show all Jupyter Notebooks using it, along with other resources utilization`.
* `nbwatch` — continuously update information from the `nbstat` table in a fullscreen terminal. Equivalent to `nbstat --watch`.
* `devicewatch` — continuously update information from the `devicestat` table in a fullscreen terminal. Equivalent to `devicestat --watch`.

The first column of each table (Notebook name for `nbstat` or device ID for `devicestat`) is referred in this documentation as *index*: we apply additional filterings/sortings based on it.



## Options

Options are separated into four sections:

* main options to filter the table and control how many processes are shown.
* column options to control displayed information for each process.
* table options to configure the formatting.
* other options.

<br />

### Main options
* `positional argument` — allows to filter the index (the first column) based on regular expression.
    * For example, `nbstat .*_experiment_.*.ipynb` would show only files with `ipynb` extension and `_experiment_` suffix in the name.

<br />

* `-v`, `-V` — sets the verbosity level.
    * Default level is 0, which shows only notebooks that use at least one NVIDIA device and only processes that use devices.
    * `-v` — verbosity level 1. Shows all processes for notebooks that use at least one NVIDIA device.
    * `-V` — verbosity level 2. Shows all processes for all notebooks.

### Column options
* `--show a b c`, `--hide x y z ` — show or hide columns in the table.
    * `hide` has priority over `show`.
    * Adding too much columns will screw up table formatting: especially true for very wide (`path`, `kernel_id`) columns.
    * Possible values depend on the exact table view (`nbstat` or `devicestat`): the actual list is available on the `--help` page.
    * In most cases, following names are recognized:
        * process properties — `process_name`, `type`, `path`, `pid`, `ppid`, `ngid`, `kernel_id`.
        * system resource usage — `cpu`, `rss`, `status`, `create_time`.
        * device resource usage — `short_id`, `process_memory`, `temperature`, `util`, `power`, `fan`.
* `--show-all` — display all available columns.

### Table options
* `--show-similar` — by default, parts of the rows are hidden if the value is the same as in the previous row. Use this parameter to change this behavior.
* `--hide-supheader` — by default, we show current time, driver and CUDA versions. Use this parameter to change this behavior.
* `--hide-header` — by default, we show a row with column names in the table. Use this parameter to change this behavior.
* `--show-footnote`, `--hide-footnote` — show a row with total system resource usage. By default, it is enabled if the table is refreshed continuously (`--watch`) and disabled otherwise.
* `--add-separators`, `--hide-separators` — turn on/off all the table separators (lines between rows/columns).
* `--supress-color` — disable using colors in the displayed view.

### Other options
* `-i`, `-n`, `--interval`, `--watch` — continuously update information from the table in a fullscreen terminal.


## Sort
The `nbstat` table is sorted in the following way:
* index items are sorted based on overall device usage and main process start time:
    * entries that use at least one NVIDIA device, sorted by starting time
    * entries that do not use any NVIDIA devices, sorted by starting time. Note that those notebooks are shown only with verbosity level 2.
* processes for each index item are shown in the following order:
    * the main process
    * processes that use at least one device, sorted by starting time
    * processes that do not use any NVIDIA devices, sorted by starting time. Note that those processes are shown only with verbosity level >=1.

## Usage examples
Using plain `nbwatch` is enough to monitor your usual ML applications. In some situations, following snippets can be helpful:

* `nbstat .*.ipynb` — to show only Jupyter Notebooks.
* `nbstat -v`, `nbstat -V` is immensely helpful for `multiprocessing`-related debugging. Adding `--show pid ppid` can also be to navigate through processes.

## Using as a Python library
In some cases, it is desired to get the table with `nbstat` / `devicestat` information as a Python object to parse it manually. You can learn how to do it in the [tutorial].