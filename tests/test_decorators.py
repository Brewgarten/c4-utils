import pytest

from c4.utils.decorators import retry


def test_cls():

    @retry(attempts=3, interval=0.01)
    class Example(object):

        def __init__(self):
            self.counter = 0

        def foo(self):
            self.counter += 1
            raise RuntimeError()

    example = Example()

    with pytest.raises(RuntimeError):
        example.foo()

    assert example.counter == 3

def test_exceptions():

    class Example(object):

        def __init__(self):
            self.counter = 0

        @retry(attempts=3, interval=0.01, exceptions=NotImplementedError)
        def foo(self):
            self.counter += 1
            raise RuntimeError()

    example = Example()

    # make sure that we immediately raised the error since the error does not match the one we want to retry on
    with pytest.raises(RuntimeError):
        example.foo()

    assert example.counter == 1

def test_function():

    class Counter(object):

        def __init__(self):
            self.counter = 0

    @retry(attempts=3, interval=0.01)
    def foo(counter, b, c=3, d=None):
        counter.counter += 1
        raise RuntimeError()

    counter = Counter()
    with pytest.raises(RuntimeError):
        foo(counter, 2)

    assert counter.counter == 3

def test_method():

    class Example(object):

        def __init__(self):
            self.counter = 0

        @retry(attempts=3, interval=0.01)
        def foo(self):
            self.counter += 1
            raise RuntimeError()

    example = Example()

    with pytest.raises(RuntimeError):
        example.foo()

    assert example.counter == 3
