import pytest

from c4.utils.enum import Enum

class Example(Enum):

    A = "a"
    B = "b"
    C = "c"

def test_enums():

    example = Example.A
    assert isinstance(example, Example)
    assert example.name == "A"
    assert example.value == "a"
    assert Example.A is not Example.A
    assert Example.A != Example.B
    assert Example.A < Example.B
    assert Example.B > Example.A
    assert Example.A <= Example.B
    assert Example.B >= Example.B

    roleString = str(example)
    roleRepresentation = repr(example)
    jsonString = example.toJSON(True)

    assert '"A"' == example.toJSON(False)

    example = Example.fromJSON(jsonString)
    assert isinstance(example, Example)
    assert str(example) == roleString
    assert repr(example) == roleRepresentation

    with pytest.raises(AttributeError):
        Example.NOTAVALUE

    assert Example.valueOf("A") == Example.A

    with pytest.raises(AttributeError):
        Example.valueOf("NOTAVALUE")

def test_getEnumConstants():

    assert set(Example.getEnumConstants()) == set([Example.A, Example.B, Example.C])
