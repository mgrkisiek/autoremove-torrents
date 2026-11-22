.. _inst:

Install and Run
===============

Install
-------

There are two ways to install ``autoremove-torrents``, but I highly recommend installing from pip. 

Install from pip
++++++++++++++++

.. code-block:: bash

   pip install autoremove-torrents

Install from GitHub
+++++++++++++++++++

.. code-block:: bash

   git clone https://github.com/jerrymakesjelly/autoremove-torrents.git
   cd autoremove-torrents
   pip install .

Run
---

Just type the following command line in your terminal:

.. code-block:: bash

   autoremove-torrents

``autoremove-torrents`` will look for the ``config.yml`` in the current working directory. For more command line arguments, please see the table below.

Arguments List
++++++++++++++

.. note::

   When you are using the full name of the arguments, you need to lead the values of the arguments with a equal sign. But if you are using the abbreviation, you only need a space to lead the argument values.

.. list-table::
   :header-rows: 1

   * - Arugments
     - Argument Abbreviations
     - Description
   * - `--view`
     - `-v`
     - Run and see which torrents will be removed, but don't really remove them.
   * - `--conf`
     - `-c`
     - Specify the path of the configuration file.
   * - `--task`
     - `-t`
     - Run a specific task only. The argument value is the task name.
   * - `--log`
     - `-l`
     - Sepcify the path of the log file.
   * - `--debug`
     - `-d`
     - Enable debug mode and output more logs.

For example:

.. code-block:: bash

   autoremove-torrents --view --conf=/home/myserver/autoremove-torrents/config.yml

Also, it equals to:

.. code-block:: bash

   autoremove-torrents -v -c /home/myserver/autoremove-torrents/config.yml


Uninstall
---------

Whether autoremove-torrents was installed from PyPI or from a GitHub checkout with ``pip install .``, uninstall it with pip:

.. code-block:: bash

    pip uninstall autoremove-torrents

.. note::

   Versions installed with the deprecated ``python3 setup.py install`` command are not tracked by pip. Remove the ``autoremove_torrents-*.egg`` directory from your ``site-packages`` and the ``autoremove-torrents`` script from your ``bin`` directory manually.
