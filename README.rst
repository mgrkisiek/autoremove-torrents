Auto Remove Torrents
====================
|Build| |License| |Python|

Automatically remove torrents according to your strategies, so you never have to worry about disk space again.
On every run, ``autoremove-torrents`` checks each torrent against your rules (ratio, seeding time, free space, labels, trackers and more) and removes the ones that match, optionally with their data.

Supported clients: **qBittorrent**, **Transmission**, **Deluge**, **μTorrent** and **rTorrent** (directly over SCGI/XML-RPC or through **ruTorrent**).

Readme in other languages: `简体中文 <README-cn.rst>`_ (may lag behind this English version).

.. |Build| image:: https://github.com/mgrkisiek/autoremove-torrents/actions/workflows/build.yml/badge.svg
   :target: https://github.com/mgrkisiek/autoremove-torrents/actions/workflows/build.yml
.. |License| image:: https://img.shields.io/badge/license-MIT-blue.svg
   :target: LICENSE
.. |Python| image:: https://img.shields.io/badge/python-3.9%2B-blue.svg
   :target: pyproject.toml

About this fork
---------------
This is a maintained fork of `jerrymakesjelly/autoremove-torrents`_, which is the original project and the version published on PyPI. This fork adds:

* **rTorrent** client support: SCGI (TCP or UNIX socket), XML-RPC over HTTP(S), and ruTorrent's ``httprpc`` plugin, with data deletion through ruTorrent's ``erasedata`` plugin.
* **Label filters** (``labels``, ``excluded_labels``, ``all_labels``) for qBittorrent tags and labels in Transmission, Deluge, μTorrent and rTorrent.
* A **Docker image** that runs on a schedule and reads credentials from environment variables.
* Compatibility fixes for recent qBittorrent releases.

See the `changelog`_ for details.

.. _jerrymakesjelly/autoremove-torrents: https://github.com/jerrymakesjelly/autoremove-torrents
.. _changelog: docs/changelog.rst

Installation
------------
Requires Python 3.9 or later.

With pip
++++++++
::

    pip install git+https://github.com/mgrkisiek/autoremove-torrents.git

``pip install autoremove-torrents`` installs the original project from PyPI, without the features of this fork.

With Docker
+++++++++++
The container runs ``autoremove-torrents`` every 5 minutes (configurable)::

    git clone https://github.com/mgrkisiek/autoremove-torrents.git
    cd autoremove-torrents
    cp config.example.yml config.yml   # edit your strategies
    cp .env.example .env               # fill in host, username and password
    docker compose up -d
    docker compose logs -f

``${VAR}`` placeholders in ``config.yml`` are filled in from ``.env``, so passwords never have to be written in the config. See `Install and Run`_ for all options.

.. _Install and Run: docs/inst.rst

Configuration
-------------
By default, ``autoremove-torrents`` reads ``config.yml`` from the current directory. A configuration contains one or more tasks; each task connects to a client and runs one or more strategies::

    my_task:
      client: qbittorrent
      host: http://127.0.0.1:8080
      username: admin
      password: adminadmin
      strategies:
        my_strategy:
          categories: IPT
          remove: seeding_time > 1209600 or ratio > 1
      delete_data: true

This removes torrents in the ``IPT`` category that have been seeding for more than 14 days **or** have a ratio above 1, together with their data.

rTorrent through ruTorrent::

    seedbox:
      client: rtorrent
      host: https://seedbox.example.com/rutorrent/plugins/httprpc/action.php
      username: ${RUTORRENT_USERNAME}
      password: ${RUTORRENT_PASSWORD}
      strategies:
        done_seeding:
          labels: autobrr_auto
          remove: ratio > 2 or seeding_time > 1209600
      delete_data: true

The ``${VAR}`` placeholders are only filled in by the Docker container; write the values directly when running without Docker.
See `config.example.yml <config.example.yml>`_ and the `configuration reference`_ for every filter, condition and client option.

.. _configuration reference: docs/config.rst

Usage
-----
::

    autoremove-torrents [--conf=config.yml] [--view] [--task=NAME] [--log=DIR] [--debug]

* ``--view`` / ``-v``: only show which torrents would be removed, without removing anything. **Use this first** to check new strategies.
* ``--conf`` / ``-c``: path to the configuration file.
* ``--task`` / ``-t``: run only this task.
* ``--log`` / ``-l``: directory for log files (must exist).
* ``--debug`` / ``-d``: write debug logs.

Scheduling without Docker
+++++++++++++++++++++++++
Run it from cron, for example every 15 minutes::

    */15 * * * * /usr/local/bin/autoremove-torrents --conf=/path/to/config.yml --log=/path/to/logs

Development
-----------
::

    git clone https://github.com/mgrkisiek/autoremove-torrents.git
    cd autoremove-torrents
    python -m venv .venv && . .venv/bin/activate
    pip install -e ".[test]"
    pytest --deselect tests/test_clients/test_clients.py::test_client

``test_client`` needs real torrent clients, which the CI workflow starts as Docker services. See `CONTRIBUTING.md <CONTRIBUTING.md>`_.

License and credits
-------------------
MIT License, see `LICENSE <LICENSE>`_. Originally created by `jerrymakesjelly`_ and contributors; thanks to everyone who worked on the original project.

.. _jerrymakesjelly: https://github.com/jerrymakesjelly
