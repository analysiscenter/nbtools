# NBTools
Collection of tools for monitoring running Jupyter Notebooks and interacting with them.

The installation should be as easy as:
```
pip install py-nbtools
```


## **NBstat**

The main tool of this package is **nbstat** / **nbwatch** command line utility. It is added at installation and shows the detailed resource utilization for each process of each running Jupyter Notebook. A gif is worth a thousand words:

<img src="images/nbwatch.gif" width="90%"/>

While in the `watch` mode, you can hit buttons to modify the displayed view:

* `tab` — swaps views, from `nbwatch` to `devicewatch` and back.
* `b` — toggles bar representation for some of the resources: in addition to its value, show colored bar.
* `m` — toggles moving average column for some of the resources: values are averaged across the latest iterations.
* `s` — toggles table separators.

We also add the **devicestat** and **devicewatch** commands that show transposed view with the same information and parameters.

For more information, check out the full [user documentation:](nbtools/nbstat/README.md) explanation of different table views, command line options and ready-to-use snippets.


### PID namespaces and user permissions
A [known problem](https://github.com/NVIDIA/nvidia-docker/issues/179) of NVIDIA drivers is that **nvidia-smi** reports PIDs of processes on devices in the global namespace, not in the container namespace, which does not allow to match PIDs of container processes to their device PIDs. There are a few workarounds:
* pass `--pid=host` flag to `docker run`.
* patch NVIDIA driver to handle PID namespaces correctly.
* [Linux only] fallback on manually inspecting */proc/PID/* files to identify the host PID for each process inside of the container.

While `nbstat` provides several fallbacks for `Linux` containers (and intend to provide support for more environments over time), the bullet-proof way is to use `--pid=host` option for `docker run`.

The same goes for user permissions: in order to inspect certain properties of processes, we rely on having all necessary permissions already provided at command run.

### Contribute
If you are interested to contribute, check out the [developer/contributor page.](nbtools/nbstat/DEV.md) It contains detailed description about inner workings of the library, my design choices and motivation behind them, as well as discussion of complexities along the way.


## **pylint_notebook**
Shamelessly taken from [pylint page:](https://pylint.pycqa.org/en/latest/)

Function that checks for errors in Jupyter Notebooks with Python code, tries to enforce a coding standard and looks for code smells. It can also look for certain type errors, it can recommend suggestions about how particular blocks can be refactored and can offer you details about the code's complexity.

Using it as easy as:
```python
from nbtools import pylint_notebook
pylint_notebook(path_to_ipynb,             # If not provided, use path to the current notebook
                disable='invalid-name',    # Disable specified Pylint checks. Can be a list.
                enable='import-error')     # Enable  specified Pylint checks. Can be a list.
```

Under the hood, it converts `.ipynb` notebook to `.py` script, creates a custom `.pylintrc` configuration, runs the `pylint` and removes all temporary files. Learn more about its usage in the [tutorial.](tutorials/NBstat.ipynb)


## **set_gpus**
Select free device(s) and set `CUDA_VISIBLE_DEVICES` environment variable so that the current process sees only them.

Eliminates an enormous amount of bugs and unexpected behaviors related to GPU usage.

```python
from nbtools import set_gpus
set_gpus(n=2,                              # Number of devices to set.
         min_free_memory=0.7,              # Minimum amount of free memory on device to consider it free.
         max_processes=3)                  # Maximum amount of  processes  on device to consider it free.
```

## Other functions
```python
from nbtools import (in_notebook,          # Return True if executed inside of Jupyter Notebook
                     get_notebook_path,    # If executed in Jupyter Notebook, return its absolute path
                     get_notebook_name,    # If executed in Jupyter Notebook, return its name
                     notebook_to_script)   # Convert Jupyter Notebook to an executable Python script.
                                           # Works well with magics and command line executions.
```


## Goals
This library started as a container of tools, that I came across / developed in my years as an ML researcher. As some of the functions survived multiple refactoring iterations, I decided to share the library so it is easier to perfect them and test in different environments.

Another goal of the project is to show how to communicate with Jupyter API on real world examples: instead of reading through a number of stackoverflow threads, you can find the same information collected in one place and get a rough understanding of what is possible with it and what is not.

## Acknowledgements
The **nbstat** module builds on [**gpustat**](https://github.com/wookayin/gpustat) package. Using the **gpustat** for years gave me an idea about possible improvements, which are implemented in this library. While the implementation is different, reading through the code of **gpustat** was essential for development.

Animated GIFs are created by using [Terminalizer](https://github.com/faressoft/terminalizer): aside from usual problems with installation, the tool itself is great.
