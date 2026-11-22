About Docs
===========

Prerequisite
-------------

::

    pip install sphinx sphinx-intl sphinx_rtd_theme


How to compile these documents?
--------------------------------

For Linux:

::

    make html

For Windows, use the batch file `make.bat`:

::

    make.bat html


The generated HTML is written to ``_build/html``. The ``.readthedocs.yaml`` file in the repository root lets you host these documents on Read the Docs.

How to generate Simplified-Chinese translation?
------------------------------------------------

First, the documents should be written in English and saved to the folder `docs`.

When the original texts are completed, use these commands to generate translation files:

::

    sphinx-build -b gettext . _build/gettext
    sphinx-intl update -p _build/gettext -l zh_CN

And then, update the translation texts by editing the `*.po` files in `locales/zh_CN/LC_MESSAGES`.

The translation is done when all of the `msgstr` fields are filled. You can compile the simplified-chinese documents by the following command, to check the results:

::

    sphinx-build -b html -D language=zh_CN . _build/html/zh_CN
