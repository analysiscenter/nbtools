# Developer documentation of **NBstat**
On this page, I explain the inner structure of the module.

It is highly recommended to read the [user documentation](README.md) before proceeding.


## Pre-goals
Before writing any code, I had following goals and requirements in mind:
* Ease of adding new columns and ways to extract information from the system and devices.
* Ease of creating new views for the same data: rearranging columns, adding table elements (column separators, for example), etc.
* Cross-platform usage: rely on **psutil** to work with processes on both Linux and Windows.
    * The **psutil** is quite slow, and on Linux-based OS we can speed up things by an order of magnitude. The code should be reasonably easy to modify to use custom functions for interacting with system resources.
* Avoid external dependencies as much as possible: the code should be self-contained and clean.
    * This led to writing custom `ResourceTable` class, with API inspired by the `pandas.DataFrame`. As tables in this module contain information about devices, Jupyter Notebooks and Python processes, the efficiency of storing and aggregating tables is not really a priority: all of the tables are small. Nevertheless, on tables with 1000 or less rows the code is actually faster.

Below I explain how these goals are achieved and which code is responsible for what. At the end of this page, you can see a list of possible further improvements.


## General idea
On a high level, `nbstat` collects information about Python processes, running Jupyter notebooks and NVIDIA devices into tables, combines them into one view and transforms it in a colored string. For each of the primitives, there are three main purposes:
* Define structure of the resulting view:
    * `ResourceFormatter` — defines both *which* resources to request from the system and *how* to display them.
* Collect information from system.
    * Performed by `ResourceInspector`.
    * `ResourceInspector.get_device_table` — information about NVIDIA devices, gathered by **nvidia-smi** API.
    * `ResourceInspector.get_process_table` — information about running Python processes, gathered by **psutil**.
    * `ResourceInspector.get_notebook_table` — information about running Jupyter Notebooks, gathered by Jupyter API.
* Format information into colored string.
    * Split across `Resource`, `ResourceEntry` and `ResourceTable` classes.
    * Each of them has `to_format_data` method, which returns the data, required to create colored string representation of the object.
    * Methods are called recursively: `ResourceTable.to_format_data` combines strings, returned from each of its entry, etc.


## Class hierarchy
Going from the very bottom to the top, I use following class structure:

* `Resource` — an enumeration of possible properties of a process.
    * The reason to use enum is to use the same named unique constants throughout the code: no strange *str* keys.
    * Along with natural resources like **CPU**, **DEVICE_TEMPERATURE** we consider processes **NAME**, **PATH** and other properties to be a resource.
    * Moreover, even some of the table elements and aliases are part of this enumeration.
    * Each Resource member is aliased into one or more string values. For example, `Resource.DEVICE_UTIL <=> 'util'`. Values of the enumeration are lists of aliases, which allows to easily add more string identifiers, if needed. Those aliases are used, for example, when user passes `--show util` from the command line.
    * Knowing the member of enumeration, we can create column **header** and its **main style** by calling `to_format_data` method.

* `ResourceEntry` — container for `resource : value` pairs. Describes all known properties of one process.
    * Essentially, a dictionary with an additional `to_format_data` method.
    * `__getitem__` and `get` recognize resources' aliases as keys.
    * By using `to_format_data` we can create **string** and its **style** for requested resource.
    * The overall string representation is created by combining **main style**, which comes from the header, **style** and **string**.
    * The reason for having multiple styles is to be able to highlight some of the column rows independently of the others: for example, if the device temperature is higher than 40℃.
    * The method is essentially a huge switch on resource type.
    * Note that we can't create formatted string knowing just the pair of `resource : value`, as some of the columns require knowing multiple values at once. For example, to create **device memory** column we combine the **current used** and **total memory available** columns.

* `ResourceTable` — container for multiple `ResourceEntry` instances. Describes the same set of properties for a number of processes.
    * Essentially, a budget version of `pd.DataFrame`. Provides a `to_pd` method for convenience, which can be used only if **pandas** is already installed.
    * Under the hood, is a list of `ResourceEntries`, which are in turn dictionaries.
    * Has the concept of *index*, which allows to split the table into subtables on unique values of *indexing* column.
    * Can be sorted and filtered, based on column or unique values in index.
    * `to_format_data` method can be used to create **string** and its **style** for requested resource. Currently not used, and the projected use of this method is to display aggregated information about the entire (sub)table.
    * `format` method controls the overall process of creation of table's string representation:
        * for each column:
            * based on the `Resource` of the column, create **header_string** and the **main_style**.
            * for each `ResourceEntry` in the table, create their **strings** and **styles**.
            * knowing all of the strings in the column, rjust them to have the same width.
            * add styled strings to the overall table representation lines.
        * add table separator elements.
    * Note that addition of `supheader` with driver info and `footnote` with system-wide resource utilization happens outside of this class.
    * A lot of methods like `merge`, `update`, `sort` are used only once or twice. Nevertheless, their implementation in the `ResourceTable` class itself makes it easy to add new features.

* `ResourceInspector` — controller class to gather information into `ResourceTables`, aggregate them into **views**, convert to string representations and apply final formatting polishes.
    * Methods `get_*_table` collect data into tables:
        * `get_device_table` — information about NVIDIA devices, gathered by **nvidia-smi** API.
        * `get_notebook_table` — information about running Jupyter Notebooks, gathered by Jupyter API.
        * `get_process_table` — information about running Python processes, gathered by **psutil**.
    * Methods `make_*_table` aggregate information from those three tables into one, filter and sort it.
    * `get_view` wraps the entire process of getting information, aggregation into one table, formatting data into colored string and adding supheader/footnote to it.
    * Caches some of the calls to **nvidia-smi** and **psutil**, allowing for better efficiency when used in `--watch` mode.

* `ResourceFormatter` — a sequence to define the overall structure of a table.
    * Essentially, a list, where each element describes the resource, whether it is included by default, and additional parameters of its visualization. For example, `{'resource' : Resource.RSS, 'include' : False, 'min_width' : 10}`.
    * Using `include=True/False` instead of adding/removing elements from the list allows to show additional columns in the table in the desired places.
    * For example, using `--show pid` sets the `include` flag of this resource to `True` and automatically places this column next to `status`.
    * Moreover, at the data collection step, we request only those resources, which have the `include=True` flag.
    * For convenience, `__getitem__` is overloaded to recognize `Resources` and their aliases as keys. It returns True if this resource has `include=True` flag.
    * Knowing the entire formatter in advance allows us to list all of the available columns in the `--help`: they are guaranteed to work and require no manual modifications to documentation.
    * The reason for it to be a `list` instead of `dict` is to allow duplicates.


Other that those primitives, it is worth to mention:
* [`blessed.Terminal`](https://github.com/jquast/blessed) is used for interacting with terminal, adding colors and other control sequences to the formatted strings
    * `length` and `rjust` methods are absolutely amazing and are actual blessing.
* `cli.py` contains parsing of command line arguments and logic for working with keystrokes in full-screen terminal mode.

Along the code, I've left a lot of dev comments and docstrings. The recommended order of reading it should be:
* resource_inspector.py
* resource.py
* resource_formatter.py
* resource_table.py
* resource_entry.py
* cli.py

## Adding new Resources
To add new tracked property, one should:
* add it to `Resource` enumeration.
* add a way to collect it in either of `ResourceInspector.get_*_table` methods.
* add a way to visually represent it in `Resource` and `ResourceEntry`.
* add it in some of the formatters.

## Known problems
* **PID namespaces.** In order to create the final table, we need to merge tables with device and process information on PIDs. It is a [known problem](https://github.com/NVIDIA/nvidia-docker/issues/179) that **nvidia-smi** reports PIDs of processes on devices in the global namespace, not in the container namespace, which does not allow to match PIDs of container processes to their device PIDs. There are a few workarounds:
    * pass `--pid=host` flag to `docker run`.
    * patch NVIDIA driver to handle PID namespaces correctly.
    * [Linux only] fallback on manually inspecting */proc/PID/* files to identify the host PID for each process inside of the container.
        * We use */proc/PID/status:NGID* field as (possible) host PID and merge tables on it, if possible.
        * I've added a mechanism of adding more such fallbacks, so it should be easier to make **nbstat** work in different environments.

    While we have some fallbacks, setting `--pid=host` ensures correct working and thus preferred.

* **User permissions.** Access to some of the information about a process can be restricted by user permissions, and there is nothing we can do.
    * We have some placeholders to use instead of actual data, but currently the best way to avoid the problem is to run `nbstat` with root permissions.

* **Sort API exposition to command line.** `ResourceTable` class allows for complex sorts on its columns / index values. Despite that, exposing sort functionality to command line is non-trivial:
    * Different command line arguments for sorting index and regular columns.
    * A lot of parameters even for a simple sort: resource, ascending/descending, placeholder value if missing.
    * Sorting on column will most definitely break existing sort.
    * Most of the resource-related sorts are actually unusable. For example, sorting `nbwatch` output on **CPU** usage would make the entire table swap rows on ~each tick, making it both unreadable and unwatchable.

    Currently, I think the best way to go forward is to wait for actual use cases and their motivation. In case we find a new desired ordering of the view, adding pre-defined and well-behaved sorts seems to be the best option.

## Post-goals
In no particular order:

* Test on more environments.
* Work with Jupyter Notebooks, initialized from *VSCode.*
* Add more fallbacks to match pids, reported from **nvidia-smi**, to actually visible processes.
* Add more fallbacks for missing / unavailable resources.
* Detect and report any permission-related issues during data collection.
* Add cursor and scrolling to `--watch` mode.
