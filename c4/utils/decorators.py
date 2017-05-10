"""
This library contains useful decorators

retry
-----

Add retry mechanism to classes, methods and functions

.. code-block:: python

    from c4.utils.decorators import retry

    @retry(attempts=3)
    class Example:

        def doSomething():
            ...


.. code-block:: python

    from c4.utils.decorators import retry

    class Example:

        @retry(interval=2)
        def doSomething():
            ...


.. code-block:: python

    from c4.utils.decorators import retry

    @retry(attempts=3)
    def doSomething():
        ...


Functionality
-------------
"""

import logging
from functools import wraps
import time


import c4.utils.util
import inspect

log = logging.getLogger(__name__)


def retry(attempts=3, interval=0.1, exceptions=None):
    """
    Decorator that wraps classes, method and function calls with a retry mechanism

    :param attempts: number of attempts
    :type attempts: int
    :param interval: interval between attempts in seconds
    :type interval: float
    :param exceptions: tuple of exceptions to retry on, by default we retry on
        all exceptions extending :class:`Exception`
    :type exceptions: tuple
    """
    if not exceptions:
        exceptions = (Exception,)

    def retryDecorator(item):
        """
        Decorator that distinguishes between classes and methods/functions
        """
        def retryWrapper(method):
            """
            Decorator that wraps method or function calls with a retry mechanism
            """
            @wraps(method)
            def wrapper(*args, **kwargs):
                """
                Actual retry decorator
                """
                latestException = None
                for attempt in range(attempts):
                    try:
                        return method(*args, **kwargs)
                    except exceptions as exception:
                        if inspect.ismethod(method):
                            arguments = args[1:]
                        else:
                            arguments = args
                        log.warn("'%s%s' caused '%r'", method.func_name, c4.utils.util.getFormattedArgumentString(arguments, kwargs), exception)
                        latestException = exception
                        if attempt < attempts:
                            time.sleep(attempt * interval + interval)
                raise latestException
            return wrapper

        if inspect.isclass(item):
            # add retry decorator to add external methods
            for name, method in inspect.getmembers(item, inspect.ismethod):
                if not name.startswith("_"):
                    setattr(item, name, retryWrapper(method))
            return item

        else:
            # add retry decorator to method/function
            return retryWrapper(item)

    return retryDecorator
