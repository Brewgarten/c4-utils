"""
This library that contains a flexible JSON serializable Enum implementation.

An enum can be created by extending the Enum base class and specifying valid
name-value pairs as follows:

.. code-block:: python

    class Example(Enum):

        A = "a"
        B = "b"
        C = "c"

    example = Example.A
    example.name == "A"
    example.value == "a"

Convert a string into an enum. This will raise an ``AttributeError`` if the string
does not match one of the specified enums.

.. code-block:: python

    example = Example.valueOf("A")

"""
import inspect

import c4.utils.jsonutil

class Enum(c4.utils.jsonutil.JSONSerializable):
    """
    A flexible JSON serializable Enum implementation.

    :param name: valid enum name
    :type name: str
    """
    def __init__(self, name):
        super(Enum, self).__init__()
        self._name = name

    @property
    def name(self):
        """
        Name
        """
        return self._name

    @property
    def value(self):
        """
        Value
        """
        return getattr(self, self.name)

    @classmethod
    def getEnumConstants(cls):
        """
        Return all enum elements

        :returns: list of enums
        :rtype: [:class:`Enum`]
        """
        enums = []
        for attribute in inspect.classify_class_attrs(cls):
            if all([not attribute.name.startswith("_"),
                    attribute.kind == "data",
                    attribute.defining_class == cls]):
                enums.append(attribute.object)
        return enums

    @classmethod
    def valueOf(cls, string):
        """
        Create an enum from the string

        :param string: string
        :type string: str
        :raises AttributeError: if the string cannot be mapped to a valid enum
        :return: :class:`Enum`
        """
        return getattr(cls, string)

    @classmethod
    def fromJSONSerializable(clazz, d):
        """
        Convert a dictionary from JSON into a respective Python
        objects. By default the dictionary is returned as is.

        :param d: the JSON dictionary
        :type d: dict
        :returns: modified dictionary or Python objects
        """
        return clazz.valueOf(d["name"])

    def toJSONSerializable(self, includeClassInfo=False):
        """
        Convert object to some JSON serializable Python object such as
        str, list, dict, etc.

        :param includeClassInfo: include class info in JSON, this
            allows deserialization into the respective Python objects
        :type includeClassInfo: bool
        :returns: JSON serializable Python object
        """
        if includeClassInfo:
            serializableDict = {"name": self.name}
            serializableDict[self.classAttribute] = self.typeAsString
            return serializableDict
        else:
            return self.name

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self, *args, **kwargs):
        return hash(repr(self))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self, *args, **kwargs):
        return "{0}.{1}".format(self.__class__.__name__, self.name)

    def __str__(self, *args, **kwargs):
        return "{0}.{1} = {2}".format(self.__class__.__name__, self.name, self.value)

    def __lt__(self, other):
        return self.value < other.value

    def __gt__(self, other):
        return self.value > other.value

    def __le__(self, other):
        return self.value <= other.value

    def __ge__(self, other):
        return self.value >= other.value

    class __metaclass__(type):

        def __getattribute__(self, name, *args, **kwargs):
            value = type.__getattribute__(self, name)
            # check if enum value and convert accordingly
            if (type(name) in (str, unicode) and not name.startswith("__")) and not callable(value):
                return self(name)
            return value

