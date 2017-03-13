import logging
import sys

import pytest


log = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s [%(levelname)s] <%(processName)s:%(process)s> [%(name)s(%(filename)s:%(lineno)d)] - %(message)s', level=logging.DEBUG)

pytestmark = pytest.mark.skipif("hjson" not in sys.modules, reason="only used when optional 'hjson' package is installed")

try:
    from c4.utils.hjsonutil import HjsonSerializable

    class Sample(HjsonSerializable):

        def __init__(self, a, b, c):
            self.a = a
            self.b = b
            self.c = c

        def toHjsonSerializable(self, includeClassInfo=False):
            serializableDict = HjsonSerializable.toHjsonSerializable(self, includeClassInfo=includeClassInfo)
            # remove some child property in a complex value
            del serializableDict["c"]["a"]
            return serializableDict

except ImportError:
    pass

def test_serialization():

    sample = Sample("test", 123, {"a": "test", "b": 123})
    hjsonString = sample.toHjson(includeClassInfo=True)
    log.fatal(hjsonString)
    hjsonString = sample.toHjson(includeClassInfo=True, pretty=True)
    log.fatal(hjsonString)
    # check that all of the properties are still there
    assert sample.a == "test"
    assert sample.b == 123
    assert sample.c == {"a": "test", "b": 123}

    # check that serialization works
    hjsonString += "\nd: test"
    loadedSample = Sample.fromHjson(hjsonString)
    assert isinstance(loadedSample, Sample)
    assert loadedSample.a == "test"
    assert loadedSample.b == 123
    assert loadedSample.c == {"b": 123}
    with pytest.raises(AttributeError):
        assert loadedSample.foo == "test"
