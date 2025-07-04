===========================
NBstat: resourse monitoring
===========================


This documentation explains all of the **nbstat** options and shows examples of its advanced usage. It can be also accessed via ``nbstat --help``.


Views
=====

The **nbstat** table information is, roughly: *for each Jupyter Notebook show all of its processes with system/device utilization information.*

Along with the **nbstat**, we provide following commands:

* **devicestat** — a transposed view of the same data: *for each NVIDIA device show all Jupyter Notebooks using it, along with other resources utilization.*
* **nbwatch** — continuously update information from the **nbstat** table in a full-screen terminal. Equivalent to ``nbstat --watch``.
* **devicewatch** — continuously update information from the **devicestat** table in a full-screen terminal. Equivalent to ``devicestat --watch``.

The first column of each table (Notebook name for **nbstat** or device ID for **devicestat**) is referred in this documentation as *index*: we apply additional filtering/sorting based on it.

Options
=======

Options are separated into four sections:

* Main options to filter the table and control how many processes are shown.
* Column options to control displayed information for each process.
* Table options to configure the formatting.
* Other options.

Main options
************

* ``positional argument`` — allows to filter the index (the first column) based on regular expression.

    * For example, ``nbstat .*_experiment_.*.ipynb`` would show only files with ``ipynb`` extension and ``_experiment_`` suffix in the name.

* ``-v``, ``-V`` — sets the verbosity level.

    * Default level is 0, which shows only notebooks that use at least one NVIDIA device and only processes that use devices.
    * ``-v`` — verbosity level 1. Shows all processes for notebooks that use at least one NVIDIA device.
    * ``-V`` — verbosity level 2. Shows all processes for all notebooks.

Column options
**************

* ``--show a b c``, ``--hide x y z`` — show or hide columns in the table.

    * Column are added in pre-defined places.
    * ``hide`` has priority over ``show``.
    * Adding too much columns will screw up the table formatting: especially true for very wide (``path``, ``kernel_id``) columns.
    * Possible values depend on the exact table view (**nbstat** or **devicestat**): the actual list is available on the ``--help`` page.
    * In most cases, following names are recognized:

        * process properties — ``process_name``, ``type``, ``path``, ``pid``, ``ppid``, ``ngid``, ``kernel_id``.
        * system resource usage — ``cpu``, ``rss``, ``status``, ``create_time``.
        * device resource usage — ``short_id``, ``process_memory``, ``temperature``, ``util``, ``power``, ``fan``.

* ``--show-all`` — display all available columns.

Table options
*************

* ``--show-similar`` — by default, parts of the rows are hidden if the value is the same as in the previous row. Use this parameter to change this behavior.
* ``--hide-supheader`` — by default, we show current time, driver and CUDA versions. Use this parameter to change this behavior.
* ``--hide-header`` — by default, we show a row with column names in the table. Use this parameter to change this behavior.
* ``--show-footnote``, ``--hide-footnote`` — show a row with total system resource usage.

    * By default, it is enabled if the table is refreshed continuously (``--watch``) and disabled otherwise.

* ``--show-separators``, ``--hide-separators`` — turn on/off all the table separators (lines between rows/columns).

    * By default, separators are enabled for **nbstat** and disabled for **devicestat**.

* ``--suppress-color`` — disable using colors in the displayed view.

Other options
*************

* ``-i``, ``-n``, ``--interval``, ``--watch`` — continuously update information from the table in a full-screen terminal.

    * If provided, a number sets the interval between ticks: ``nbstat -i 0.2``.

* ``-w``, ``--window`` — number of table updates to use for computing moving averages.


Keystrokes
==========

While in the ``watch`` mode, you can use keystrokes to change the displayed view:

* ``tab`` — swaps views, from ``nbwatch`` to ``devicewatch`` and back.
* ``v`` — changes verbosity of the displayed table.
* ``b`` — toggles bar representation for some of the resources: in addition to its value, show colored bar.
* ``m`` — toggles moving average column for some of the resources: values are averaged across the latest iterations.
* ``s`` — toggles table separators.
* ``F1-F8`` — toggles columns with resources.
* ``r`` — resets the behaviour to the defaults.

Sort
====

The **nbstat** table is sorted in the following way:

    * index items are sorted based on overall device usage and main process start time:

        * entries that use at least one NVIDIA device, sorted by starting time
        * entries that do not use NVIDIA devices, sorted by starting time. Note that those notebooks are shown only with verbosity level 2.

    * processes for each index item are shown in the following order:

        * the main process
        * processes that use at least one device, sorted by starting time
        * processes that do not use NVIDIA devices, sorted by starting time. Note that those processes are shown only with verbosity level >=1.

Usage examples
==============

Using plain **nbwatch** is enough to monitor your usual ML applications. In some situations, though, following snippets are helpful:

* ``nbstat .*.ipynb`` — to show only Jupyter Notebooks.
* ``nbstat .*/research/.*.ipynb`` — to show only Jupyter Notebooks in a specific directory.
* ``nbstat --show status cpu -i 0.1`` — additionally displays process status and CPU usage at an increased frequency.
* ``nbstat --hide type pid rss`` — display only the GPU-related columns for each process.
* ``nbstat -v``, ``nbstat -V`` is immensely helpful for ``multiprocessing``-related debugging.

    - Adding ``--show pid ppid`` can be nice to navigate through large number of processes.

* ``nbstat --device-memory-format GB`` — show GPU memory in GB: an increasingly more used option when using larger devices.

Using as a Python library
=========================

Sometimes, it is desired to get **nbstat** / **devicestat** information as a Python object to parse it manually. You can learn how to do it in the [tutorial](../../tutorials/NBstat.ipynb).


Troubleshooting: PID namespaces, user permissions and zombie processes
======================================================================

A `known problem <https://github.com/NVIDIA/nvidia-docker/issues/179>`_ of NVIDIA drivers is that **nvidia-smi** reports PIDs of processes on devices in the global namespace, not in the container namespace, which does not allow to match PIDs of container processes to their device PIDs. There are a few workarounds:

* [**recommended**] pass ``--pid=host`` flag to ``docker run``.

* patch NVIDIA driver to handle PID namespaces correctly.

* [Linux only] fallback on manually inspecting ``*/proc/PID/*`` files to identify the host PID for each process inside of the container.

While ``nbstat`` provides several fallbacks for `Linux` containers (and intend to provide support for more environments over time), the bullet-proof way is to use ``--pid=host`` option for ``docker run``. Adding it resolves most of the issues immediately.

One more thing that sometimes happens to NVIDIA devices is zombie processes: by incorrectly terminating a GPU-using process you can end up in a situation where device memory is held by not-existing process. As far as I know, there are no ways of killing them without rebooting, and ``nbstat`` just marks such processes with red color.

In order to inspect certain properties of processes, we rely on having all necessary permissions already provided at command run. ``nbstat`` has some fallbacks for some attributes, and I currently work on improving error handling in cases of denied access to files.



Contribute
==========

If you are interested to contribute, check out the `developer/contributor page <https://github.com/analysiscenter/nbtools/blob/master/nbtools/nbstat/DEV.md>`_. It contains detailed description about inner workings of the library, my design choices and motivation behind them, as well as discussion of complexities along the way.