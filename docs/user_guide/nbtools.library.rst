========================================
Jupyter Notebooks: linting and execution
========================================

Other than `nbstat / nbwatch` monitoring utilities, this library provides a few useful tools for working with notebooks and GPUs.


pylint_notebook
***************

Shamelessly taken from `pylint page <https://pylint.pycqa.org/en/latest/>`_

Function that checks for errors in Jupyter Notebooks with Python code, tries to enforce a coding standard and looks for code smells. It can also look for certain type errors, it can recommend suggestions about how particular blocks can be refactored and can offer you details about the code's complexity.

Using it as easy as:

.. code-block:: python

    from nbtools import pylint_notebook
    pylint_notebook(path_to_ipynb,             # If not provided, use path to the current notebook
                    disable='invalid-name',    # Disable specified Pylint checks. Can be a list.
                    enable='import-error')     # Enable  specified Pylint checks. Can be a list.


Under the hood, it converts `.ipynb` notebook to `.py` script, creates a custom `.pylintrc` configuration, runs the `pylint` and removes all temporary files. Learn more about its usage in the [tutorial.](tutorials/NBstat.ipynb)

exec_notebook
*************

Provides a `eval`-like interface for running Jupyter Notebooks programmatically. We use it for running interactive tests, that are easy to work with: in case of any failures, one can jump right into fixing it with an already set-up environment.

.. code-block:: python

    from nbtools import exec_notebook
    exec_notebook(path_to_ipynb,                       # Which notebook to run
                  out_path_ipynb,                      # Where to save result
                  inputs={'learning_rate': 0.05,},     # Pass variables to notebook
                  outputs=['accuracy'])                # Extract variables from notebook


set_gpus, free_gpus
*******************

Select free device(s) and set `CUDA_VISIBLE_DEVICES` environment variable so that the current process sees only them.

Eliminates an enormous amount of bugs and unexpected behaviors related to GPU usage.

.. code-block:: python

    from nbtools import set_gpus, free_gpus
    used_gpus = set_gpus(n=2,                 # Number of devices to set.
                         min_free_memory=0.7, # Minimum amount of free memory on device to consider free.
                         max_processes=3)     # Maximum amount of  processes  on device to consider free.
    free_gpus(used_gpus)                      # Kill all processes on selected GPUs. Useful at teardown.

Other functions
***************

.. code-block:: python

    from nbtools import (in_notebook,         # Return True if executed inside of Jupyter Notebook
                         get_notebook_path,   # If executed in Jupyter Notebook, return its absolute path
                         get_notebook_name,   # If executed in Jupyter Notebook, return its name
                         notebook_to_script)  # Convert Jupyter Notebook to an executable Python script.
                                              # Works well with magics and command line executions.
