Welcome to NBtools
==================

Collection of tools for monitoring running Jupyter Notebooks and interacting with them.

Installation
*****

The installation should be as easy as:

.. code-block:: bash

   pip install py-nbtools

User guide
*****

.. toctree::
   :maxdepth: 2

   quick_start/nbtools
   api/modules

Goals
*****

This library started as a container of tools, that I came across / developed in my years as an ML researcher. As some of the functions survived multiple refactoring iterations, I decided to share the library so it is easier to perfect them and test in different environments.

Another goal of the project is to show how to communicate with Jupyter API on real world examples: instead of reading through a number of stackoverflow threads, you can find the same information collected in one place and get a rough understanding of what is possible with it and what is not.

Acknowledgements
*****

The **nbstat** module builds on `gpustat <https://pylint.pycqa.org/en/latest/>`_ package. Using the **gpustat** for years gave me an idea about possible improvements, which are implemented in this library. While the implementation is different, reading through the code of **gpustat** was essential for development.

Animated GIFs are created by using `Terminalizer <https://github.com/faressoft/terminalizer>`_: aside from the usual problems with installation, the tool itself is amazing.

