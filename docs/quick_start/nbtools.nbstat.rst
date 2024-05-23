===========================
NBstat: resourse monitoring
===========================

The main tool of this package is **nbstat** / **nbwatch** command line utility. It is added at installation and shows the detailed resource utilization for each process of each running Jupyter Notebook. A gif is worth a thousand words:

.. image:: ../../images/nbwatch.gif
    :width: 90%

For more information, check out the full [user documentation:](nbtools/nbstat/README.md) explanation of different table views, command line options and ready-to-use snippets.


Troubleshooting: PID namespaces, user permissions and zombie processes
*****

A `known problem <https://github.com/NVIDIA/nvidia-docker/issues/179>`_ of NVIDIA drivers is that **nvidia-smi** reports PIDs of processes on devices in the global namespace, not in the container namespace, which does not allow to match PIDs of container processes to their device PIDs. There are a few workarounds:

* [**recommended**] pass ``--pid=host`` flag to ``docker run``.

* patch NVIDIA driver to handle PID namespaces correctly.

* [Linux only] fallback on manually inspecting ``*/proc/PID/*`` files to identify the host PID for each process inside of the container.

While ``nbstat`` provides several fallbacks for `Linux` containers (and intend to provide support for more environments over time), the bullet-proof way is to use ``--pid=host`` option for ``docker run``. Adding it resolves most of the issues immediately.

One more thing that sometimes happens to NVIDIA devices is zombie processes: by incorrectly terminating a GPU-using process you can end up in a situation where device memory is held by not-existing process. As far as I know, there are no ways of killing them without rebooting, and ``nbstat`` just marks such processes with red color.

In order to inspect certain properties of processes, we rely on having all necessary permissions already provided at command run. ``nbstat`` has some fallbacks for some attributes, and I currently work on improving error handling in cases of denied access to files.



Contribute
*****

If you are interested to contribute, check out the [developer/contributor page.](nbtools/nbstat/DEV.md) It contains detailed description about inner workings of the library, my design choices and motivation behind them, as well as discussion of complexities along the way.