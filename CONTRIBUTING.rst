How To Contribute
=================

First off, thank you for considering contributing to ``structures``!
It's people like *you* who make it is such a great tool for everyone.

This document is mainly to help you to get started by codifying tribal knowledge and expectations and make it more accessible to everyone.
But don't be afraid to open half-finished PRs and ask questions if something is unclear!

Workflow
--------

- Contributions are accepted only via Pull Requests.
- No contribution is too small!
  Please submit as many fixes for typos and grammar bloopers as you can!
- Try to limit each pull request to *one* change only.
- *Always* add tests and docs for your code.
  This is a hard rule; patches with missing tests or documentation can't be merged.
- Make sure your changes pass our CI_.
  You won't get any feedback until it's green unless you ask for it.
- Once you've addressed review feedback, make sure to bump the pull request with a short note, so we know you're done.
- Don’t break backward compatibility.
  If you think breakage is completely necessary, create a change request describing pros and cons of a new api in comparison with the current api.

Code
----

- Obey `PEP 8`_ and `PEP 257`_.
  We use the ``"""``\ -on-separate-lines style for docstrings:

  .. code-block:: python

     def func(x):
         """
         Do something.

         :param str x: A very important parameter.

         :rtype: str
         """
- If you add or change public APIs, tag the docstring using ``..  versionadded:: 1.2.3 WHAT`` or ``..  versionchanged:: 1.2.3 WHAT``.
- Prefer single quotes (``'``) over double quotes (``"``) unless the string contains single quotes itself.

Tests
-----

- Currently all tests are implemented as examples in docstrings and are tested using pytest & doctest.
- To run the test suite, all you need is a recent tox_.
  It will ensure the test suite runs with all dependencies against all Python versions just as it will on Travis CI.
  If you lack some Python versions, you can can always limit the environments like ``tox -e py35,py36`` (in that case you may want to look into pyenv_, which makes it very easy to install many different Python versions in parallel).

Submitting Bugs and Bug Fixes
-----------------------------

First try to minimize your buggy structure.
If minimization revealed a bug in a core construct and the failing example spans a couple of lines, you should directly include the example into the buggy construct's docstring.
If you can't minimize your bug to core constructs or the failing example requires a custom struct, you should create a module in `<examples>`_ directory and put your struct in there (with a failing doctest).

Submitting Change Requests
--------------------------

If you want to change a core construct, you must update the docstring with an example of the change.

If you want to add or update an example structure, start with implementing/updating doctests of your structure.

Local Development Environment
-----------------------------

You can (and should) run our test suite using tox_.
However you’ll probably want a more traditional environment too.

First install `pipenv`_.

Next, get an up to date checkout of the ``structures`` repository:

.. code-block:: bash

    $ git checkout git@github.com:malinoff/structures.git

Change into the newly created directory install an editable version of ``structures`` along with its development requirements:

.. code-block:: bash

    $ cd structures
    $ pipenv install '-e .' --dev

At this point

.. code-block:: bash

   $ pipenv run pytest

should work and pass.

****

Thank you for considering contributing to ``structures``!

.. _`PEP 8`: https://www.python.org/dev/peps/pep-0008/
.. _`PEP 257`: https://www.python.org/dev/peps/pep-0257/
.. _tox: https://tox.readthedocs.io/
.. _pyenv: https://github.com/pyenv/pyenv
.. _pipenv: http://docs.python-guide.org/en/latest/dev/virtualenvs/#installing-pipenv
.. _CI: https://travis-ci.org/malinoff/structures/
