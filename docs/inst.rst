.. _inst:

Install and Run
===============

Install
-------

There are two ways to install ``autoremove-torrents``: with pip, or as a Docker container.

.. note::

   This is a fork of `jerrymakesjelly/autoremove-torrents <https://github.com/jerrymakesjelly/autoremove-torrents>`_.
   The ``autoremove-torrents`` package on PyPI is the original project, which doesn't include rTorrent support,
   labels or the Docker image, so install this fork from GitHub.

Install with pip
++++++++++++++++

.. code-block:: bash

   pip install git+https://github.com/mgrkisiek/autoremove-torrents.git

Or from a local clone:

.. code-block:: bash

   git clone https://github.com/mgrkisiek/autoremove-torrents.git
   cd autoremove-torrents
   pip install .

Run with Docker
+++++++++++++++

The Docker image runs ``autoremove-torrents`` on a schedule (every 5 minutes by default).
Your ``config.yml`` is mounted into the container, and ``${VAR}`` placeholders in it are filled in from environment variables,
so passwords can stay in an ``.env`` file instead of the config.

.. code-block:: bash

   git clone https://github.com/mgrkisiek/autoremove-torrents.git
   cd autoremove-torrents
   cp config.example.yml config.yml   # then edit your strategies
   cp .env.example .env               # then fill in host, username and password
   docker compose up -d
   docker compose logs -f

Settings in ``.env``:

* ``INTERVAL``: seconds between runs (default ``300``).
* ``EXTRA_ARGS``: extra arguments for every run, e.g. ``--view`` to preview without removing anything.
* ``PUID``/``PGID``: user and group the container runs as; they must be able to write the ``logs`` directory.

To preview a single run: ``docker compose run --rm autoremove-torrents --view``.

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
