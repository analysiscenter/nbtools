# NBTools
Collection of tools for monitoring running Jupyter Notebooks and interacting with them.

The installation should be as easy as:
```
pip install py-nbtools
```


## **NBstat**

The main tool of this package is **nbstat** / **nbwatch** command line utility. It is added at installation and shows the detailed resource utilization for each process of each running Jupyter Notebook. A gif is worth a thousand words:

<img src="images/nbwatch.gif" width="90%"/>

For more information, check out the full [user documentation:](nbtools/nbstat/README.md) explanation of different table views, command line options and ready-to-use snippets.


### Troubleshooting: PID namespaces, user permissions and zombie processes
A [known problem](https://github.com/NVIDIA/nvidia-docker/issues/179) of NVIDIA drivers is that **nvidia-smi** reports PIDs of processes on devices in the global namespace, not in the container namespace, which does not allow to match PIDs of container processes to their device PIDs. There are a few workarounds:
* [recommended] pass `--pid=host` flag to `docker run`.
* patch NVIDIA driver to handle PID namespaces correctly.
* [Linux only] fallback on manually inspecting */proc/PID/* files to identify the host PID for each process inside of the container.

While `nbstat` provides several fallbacks for `Linux` containers (and intend to provide support for more environments over time), the bullet-proof way is to use `--pid=host` option for `docker run`. Adding it resolves most of the issues immediately.

One more thing that sometimes happens to NVIDIA devices is zombie processes: by incorrectly terminating a GPU-using process you can end up in a situation where device memory is held by not-existing process. As far as I know, there are no ways of killing them without rebooting, and `nbstat` just marks such processes with red color.

In order to inspect certain properties of processes, we rely on having all necessary permissions already provided at command run. `nbstat` has some fallbacks for some attributes, and I currently work on improving error handling in cases of denied access to files.



### Contribute
If you are interested to contribute, check out the [developer/contributor page.](nbtools/nbstat/DEV.md) It contains detailed description about inner workings of the library, my design choices and motivation behind them, as well as discussion of complexities along the way.

## Library
Other than `nbstat / nbwatch` monitoring utilities, this library provides a few useful tools for working with notebooks and GPUs.


### **pylint_notebook**
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

### **exec_notebook**
Provides a `eval`-like interface for running Jupyter Notebooks programmatically. We use it for running interactive tests, that are easy to work with: in case of any failures, one can jump right into fixing it with an already set-up environment.

```python
from nbtools import exec_notebook
exec_notebook(path_to_ipynb,                       # Which notebook to run
              out_path_ipynb,                      # Where to save result
              inputs={'learning_rate': 0.05,},     # Pass variables to notebook
              outputs=['accuracy'])                # Extract variables from notebook
```


### **set_gpus, free_gpus**
Select free device(s) and set `CUDA_VISIBLE_DEVICES` environment variable so that the current process sees only them.

Eliminates an enormous amount of bugs and unexpected behaviors related to GPU usage.

```python
from nbtools import set_gpus, free_gpus
used_gpus = set_gpus(n=2,                # Number of devices to set.
                     min_free_memory=0.7,# Minimum amount of free memory on device to consider free.
                     max_processes=3)    # Maximum amount of  processes  on device to consider free.
free_gpus(used_gpus)                     # Kill all processes on selected GPUs. Useful at teardown.
```

### Other functions
```python
from nbtools import (in_notebook,         # Return True if executed inside of Jupyter Notebook
                     get_notebook_path,   # If executed in Jupyter Notebook, return its absolute path
                     get_notebook_name,   # If executed in Jupyter Notebook, return its name
                     notebook_to_script)  # Convert Jupyter Notebook to an executable Python script.
                                          # Works well with magics and command line executions.
```


## Goals
This library started as a container of tools, that I came across / developed in my years as an ML researcher. As some of the functions survived multiple refactoring iterations, I decided to share the library so it is easier to perfect them and test in different environments.

Another goal of the project is to show how to communicate with Jupyter API on real world examples: instead of reading through a number of stackoverflow threads, you can find the same information collected in one place and get a rough understanding of what is possible with it and what is not.

## Acknowledgements
The **nbstat** module builds on [**gpustat**](https://github.com/wookayin/gpustat) package. Using the **gpustat** for years gave me an idea about possible improvements, which are implemented in this library. While the implementation is different, reading through the code of **gpustat** was essential for development.

Animated GIFs are created by using [Terminalizer](https://github.com/faressoft/terminalizer): aside from the usual problems with installation, the tool itself is amazing.
