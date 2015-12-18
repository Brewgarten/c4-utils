from c4.utils.jsonutil import JSONSerializable

class Sample(JSONSerializable):

    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def toJSONSerializable(self, includeClassInfo=False):
        serializableDict = JSONSerializable.toJSONSerializable(self, includeClassInfo=includeClassInfo)
        # remove some child property in a complex value
        del serializableDict["c"]["a"]
        return serializableDict

def test_dictHasType():

    sample = Sample("test", 123, {"a": "test", "b": 123})
    sampleTypeString = sample.typeAsString

    test = {
        JSONSerializable.classAttribute : sampleTypeString
    }

    # check comparison with object
    assert JSONSerializable.dictHasType(test, sample)
    assert JSONSerializable.dictHasType(test, JSONSerializable()) == False
    # check comparison with class
    assert JSONSerializable.dictHasType(test, Sample)
    assert JSONSerializable.dictHasType(test, JSONSerializable) == False

def test_serialization():

    sample = Sample("test", 123, {"a": "test", "b": 123})
    jsonString = sample.toJSON(includeClassInfo=True)
    # check that all of the properties are still there
    assert sample.a == "test"
    assert sample.b == 123
    assert sample.c == {"a": "test", "b": 123}

    # check that serialization works
    loadedSample = Sample.fromJSON(jsonString)
    assert isinstance(loadedSample, Sample)
    assert loadedSample.a == "test"
    assert loadedSample.b == 123
    assert loadedSample.c == {"b": 123}
