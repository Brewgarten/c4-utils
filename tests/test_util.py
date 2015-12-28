import pytest
import re

from multiprocessing import Process

from c4.utils.util import (EtcHosts,
                           callWithVariableArguments,
                           exclusiveWrite,
                           isVirtualMachine,
                           getModuleClasses,
                           mergeDictionaries,
                           sortHostnames, getVariableArguments)

def test_EtcHosts():

    etcHosts = EtcHosts.fromString("""
127.0.0.1   localhost localhost.localdomain
::1         localhost localhost.localdomain
# test comment
10.1.0.1    node1.nodedomain       node1
10.1.0.2 node2.nodedomain # commented out node2
10.1.0.3 node3.nodedomain.com node3 node3alias""")

    for ip in ["127.0.0.1", "10.1.0.1", "10.1.0.2", "10.1.0.3"]:
        assert ip in etcHosts

    assert etcHosts["127.0.0.1"] == set(["localhost", "localhost.localdomain"])
    assert etcHosts["::1"] == set(["localhost", "localhost.localdomain"])
    assert etcHosts["10.1.0.1"] == set(["node1.nodedomain", "node1"])
    assert etcHosts["10.1.0.2"] == set(["node2.nodedomain"])
    assert etcHosts["10.1.0.3"] == set(["node3.nodedomain.com", "node3", "node3alias"])

    # check adding new alias to exising ip
    assert etcHosts.add("node2", "10.1.0.2")
    # make sure we cannot add the same alias again
    assert etcHosts.add("node2", "10.1.0.2") is None
    # check adding alias to a new ip
    assert etcHosts.add("newNode", "10.1.0.4")
    # update ip for alias
    assert etcHosts.add("node1", "192.168.0.1", replace=True)
    # update ip for second alias and check that original ip has been removed
    assert etcHosts.add("node1.nodedomain", "192.168.0.1", replace=True)
    assert "10.1.0.1" not in etcHosts
    assert etcHosts["192.168.0.1"] == set(["node1.nodedomain", "node1"])

    etcHostsString = etcHosts.toString()
    assert etcHostsString
    # check sorting
    assert re.search("localhost.localdomain localhost", etcHostsString, re.MULTILINE)
    assert re.search("node2.nodedomain node2", etcHostsString, re.MULTILINE)
    assert re.search("node3.nodedomain.com node3 node3alias", etcHostsString, re.MULTILINE)
    assert re.search("newNode", etcHostsString, re.MULTILINE)
    assert re.search("node1.nodedomain node1", etcHostsString, re.MULTILINE)

class TestVariableArguments():

    def test_noArguments(self):

        def noArguments():
            return True

        assert getVariableArguments(noArguments) == ({}, [], {})
        assert callWithVariableArguments(noArguments)

        assert getVariableArguments(noArguments, "test") == ({}, ["test"], {})
        assert callWithVariableArguments(noArguments, "test")

        assert getVariableArguments(noArguments, a="test") == ({}, [], {"a": "test"})
        assert callWithVariableArguments(noArguments, a="test")

        assert getVariableArguments(noArguments, "test", a="test") == ({}, ["test"], {"a": "test"})
        assert callWithVariableArguments(noArguments, "test", a="test")

    def test_noArgumentsWithVarargs(self):

        def noArgumentsWithVarargs(*v):
            return v

        assert getVariableArguments(noArgumentsWithVarargs) == ({}, [], {})
        assert callWithVariableArguments(noArgumentsWithVarargs) == ()

        assert getVariableArguments(noArgumentsWithVarargs, "test") == ({}, ["test"], {})
        assert callWithVariableArguments(noArgumentsWithVarargs, "test") == ("test",)

        assert getVariableArguments(noArgumentsWithVarargs, a="test") == ({}, [], {"a": "test"})
        assert callWithVariableArguments(noArgumentsWithVarargs, a="test") == ()

        assert getVariableArguments(noArgumentsWithVarargs, "test", a="test") == ({}, ["test"], {"a": "test"})
        assert callWithVariableArguments(noArgumentsWithVarargs, "test", a="test") == ("test",)

    def test_noArgumentsWithKeywords(self):

        def noArgumentsWithKeywords(**keywords):
            return keywords

        assert getVariableArguments(noArgumentsWithKeywords) == ({}, [], {})
        assert callWithVariableArguments(noArgumentsWithKeywords) == {}

        assert getVariableArguments(noArgumentsWithKeywords, "test") == ({}, ["test"], {})
        assert callWithVariableArguments(noArgumentsWithKeywords, "test") == {}

        assert getVariableArguments(noArgumentsWithKeywords, a="test") == ({}, [], {"a": "test"})
        assert callWithVariableArguments(noArgumentsWithKeywords, a="test") == {"a": "test"}

        assert getVariableArguments(noArgumentsWithKeywords, "test", a="test") == ({}, ["test"], {"a": "test"})
        assert callWithVariableArguments(noArgumentsWithKeywords, "test", a="test") == {"a": "test"}

    def test_oneArgument(self):

        def oneArgument(a):
            return a

        assert getVariableArguments(oneArgument) == ({'a': '_notset_'}, [], {})
        assert callWithVariableArguments(oneArgument) is None

        assert getVariableArguments(oneArgument, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgument, "test") == "test"

        assert getVariableArguments(oneArgument, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgument, a="test") == "test"

        assert getVariableArguments(oneArgument, "test", "test") == ({"a": "test"}, ["test"], {})
        assert callWithVariableArguments(oneArgument, "test", "test") == "test"

        assert getVariableArguments(oneArgument, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneArgument, "test", b="test") == "test"

        assert getVariableArguments(oneArgument, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneArgument, "test", "test", c="test") == "test"

    def test_oneArgumentWithVarargs(self):

        def oneArgumentWithVarargs(a, *v):
            return a, v

        assert getVariableArguments(oneArgumentWithVarargs) == ({'a': '_notset_'}, [], {})
        assert callWithVariableArguments(oneArgumentWithVarargs) is None

        assert getVariableArguments(oneArgumentWithVarargs, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgumentWithVarargs, "test") == ("test", ())

        assert getVariableArguments(oneArgumentWithVarargs, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgumentWithVarargs, a="test") == ("test", ())

        assert getVariableArguments(oneArgumentWithVarargs, "test", "test") == ({"a": "test"}, ["test"], {})
        assert callWithVariableArguments(oneArgumentWithVarargs, "test", "test")  == ("test", ("test",))

        assert getVariableArguments(oneArgumentWithVarargs, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneArgumentWithVarargs, "test", b="test")  == ("test", ())

        assert getVariableArguments(oneArgumentWithVarargs, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneArgumentWithVarargs, "test", "test", c="test")  == ("test", ("test",))

    def test_oneArgumentWithKeywords(self):

        def oneArgumentWithKeywords(a, **keywords):
            return a, keywords

        assert getVariableArguments(oneArgumentWithKeywords) == ({'a': '_notset_'}, [], {})
        assert callWithVariableArguments(oneArgumentWithKeywords) is None

        assert getVariableArguments(oneArgumentWithKeywords, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgumentWithKeywords, "test") == ("test", {})

        assert getVariableArguments(oneArgumentWithKeywords, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneArgumentWithKeywords, a="test") == ("test", {})

        assert getVariableArguments(oneArgumentWithKeywords, "test", "test") == ({"a": "test"}, ["test"], {})
        assert callWithVariableArguments(oneArgumentWithKeywords, "test", "test") == ("test", {})

        assert getVariableArguments(oneArgumentWithKeywords, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneArgumentWithKeywords, "test", b="test") == ("test", {"b": "test"})

        assert getVariableArguments(oneArgumentWithKeywords, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneArgumentWithKeywords, "test", "test", c="test") == ("test", {"c": "test"})

    def test_oneKeywordArgument(self):

        def oneKeywordArgument(a="a"):
            return a

        assert getVariableArguments(oneKeywordArgument) == ({"a": "a"}, [], {})
        assert callWithVariableArguments(oneKeywordArgument) == "a"

        assert getVariableArguments(oneKeywordArgument, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgument, "test") == "test"

        assert getVariableArguments(oneKeywordArgument, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgument, a="test") == "test"

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(oneKeywordArgument, "test", a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgument, "test", a="test") == "test"

        assert getVariableArguments(oneKeywordArgument, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneKeywordArgument, "test", b="test") == "test"

        assert getVariableArguments(oneKeywordArgument, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneKeywordArgument, "test", "test", c="test") == "test"

    def test_oneKeywordArgumentWithVarargs(self):

        def oneKeywordArgumentWithVarargs(a="a", *v):
            return a, v

        assert getVariableArguments(oneKeywordArgumentWithVarargs) == ({"a": "a"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs) == ("a", ())

        assert getVariableArguments(oneKeywordArgumentWithVarargs, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs, "test") == ("test", ())

        assert getVariableArguments(oneKeywordArgumentWithVarargs, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs, a="test") == ("test", ())

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(oneKeywordArgumentWithVarargs, "test", a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs, "test", a="test") == ("test", ())

        assert getVariableArguments(oneKeywordArgumentWithVarargs, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs, "test", b="test") == ("test", ())

        assert getVariableArguments(oneKeywordArgumentWithVarargs, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneKeywordArgumentWithVarargs, "test", "test", c="test") == ("test", ("test",))

    def test_oneKeywordArgumentWithKeywords(self):

        def oneKeywordArgumentWithKeywords(a="a", **keywords):
            return a, keywords

        assert getVariableArguments(oneKeywordArgumentWithKeywords) == ({"a": "a"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords) == ("a", {})

        assert getVariableArguments(oneKeywordArgumentWithKeywords, "test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords, "test") == ("test", {})

        assert getVariableArguments(oneKeywordArgumentWithKeywords, a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords, a="test") == ("test", {})

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(oneKeywordArgumentWithKeywords, "test", a="test") == ({"a": "test"}, [], {})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords, "test", a="test") == ("test", {})

        assert getVariableArguments(oneKeywordArgumentWithKeywords, "test", b="test") == ({"a": "test"}, [], {"b": "test"})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords, "test", b="test") == ("test", {"b": "test"})

        assert getVariableArguments(oneKeywordArgumentWithKeywords, "test", "test", c="test") == ({"a": "test"}, ["test"], {"c": "test"})
        assert callWithVariableArguments(oneKeywordArgumentWithKeywords, "test", "test", c="test") == ("test", {"c": "test"})

    def test_combinedArguments(self):

        def combinedArguments(a, b="b"):
            return a, b

        assert getVariableArguments(combinedArguments) == ({"a": "_notset_", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArguments) is None

        assert getVariableArguments(combinedArguments, b="test") == ({"a": "_notset_", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArguments, b="test") is None

        assert getVariableArguments(combinedArguments, "test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArguments, "test") == ("test", "b")

        assert getVariableArguments(combinedArguments, a="test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArguments, a="test") == ("test", "b")

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArguments, "test" , "test", a="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArguments, "test", "test", a="test") == ("test", "test")

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArguments, "test" , "test", b="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArguments, "test", "test", b="test") == ("test", "test")

        assert getVariableArguments(combinedArguments, "test" , "test", c="test") == ({"a": "test", "b": "test"}, [], {"c": "test"})
        assert callWithVariableArguments(combinedArguments, "test", "test", "test", c="test") == ("test", "test")

    def test_combinedArgumentsWithVarargs(self):

        def combinedArgumentsWithVarargs(a, b="b", *v):
            return a, b, v

        assert getVariableArguments(combinedArgumentsWithVarargs) == ({"a": "_notset_", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs) is None

        assert getVariableArguments(combinedArgumentsWithVarargs, b="test") == ({"a": "_notset_", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, b="test") is None

        assert getVariableArguments(combinedArgumentsWithVarargs, "test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, "test") == ("test", "b", ())

        assert getVariableArguments(combinedArgumentsWithVarargs, a="test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, a="test") == ("test", "b", ())

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArgumentsWithVarargs, "test" , "test", a="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, "test", "test", a="test") == ("test", "test", ())

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArgumentsWithVarargs, "test" , "test", b="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, "test", "test", b="test") == ("test", "test", ())

        assert getVariableArguments(combinedArgumentsWithVarargs, "test" , "test", c="test") == ({"a": "test", "b": "test"}, [], {"c": "test"})
        assert callWithVariableArguments(combinedArgumentsWithVarargs, "test", "test", "test", c="test") == ("test", "test", ("test",))

    def test_combinedArgumentsWithKeywords(self):

        def combinedArgumentsWithKeywords(a, b="b", **keywords):
            return a, b, keywords

        assert getVariableArguments(combinedArgumentsWithKeywords) == ({"a": "_notset_", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords) is None

        assert getVariableArguments(combinedArgumentsWithKeywords, b="test") == ({"a": "_notset_", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, b="test") is None

        assert getVariableArguments(combinedArgumentsWithKeywords, "test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, "test") == ("test", "b", {})

        assert getVariableArguments(combinedArgumentsWithKeywords, a="test") == ({"a": "test", "b": "b"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, a="test") == ("test", "b", {})

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArgumentsWithKeywords, "test" , "test", a="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, "test", "test", a="test") == ("test", "test", {})

        # note that here the keyword replaces the actual argument so we do not get back any left overs
        assert getVariableArguments(combinedArgumentsWithKeywords, "test" , "test", b="test") == ({"a": "test", "b": "test"}, [], {})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, "test", "test", b="test") == ("test", "test", {})

        assert getVariableArguments(combinedArgumentsWithKeywords, "test" , "test", c="test") == ({"a": "test", "b": "test"}, [], {"c": "test"})
        assert callWithVariableArguments(combinedArgumentsWithKeywords, "test", "test", "test", c="test") == ("test", "test", {"c": "test"})

def test_exclusiveWrite(tmpdir):
    processes = []
    testProcesses = 100
    for number in range(testProcesses):
        process = Process(target=exclusiveWrite, args=(str(tmpdir.join("test")), "{0}:testtest\n".format(number)))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    counter = 0
    with tmpdir.join("test").open() as f:
        for line in f:
            counter = counter + 1
    assert counter == testProcesses

def test_exclusiveWrite_fail(tmpdir):
    with pytest.raises(OSError):
        exclusiveWrite(str(tmpdir.join("test")), "test", tries=0)

    with tmpdir.join("test").open() as f:
        assert not f.read()

def test_isVirtualMachine(monkeypatch):

    def baremetal(command, errorMessage=None):
        return """sda  disk
sdb  disk
sdc  disk
sdd  disk
sde  disk
sdf  disk
sdh  disk
sdi  disk
sdj  disk
sdk  disk
sdg  disk
sdl  disk"""

    monkeypatch.setattr("c4.utils.command.execute", baremetal)
    assert isVirtualMachine() == False

    def vm(command, errorMessage=None):
        return """xvdc disk
xvdg disk
xvdb disk
xvdf disk
xvda disk
xvde disk"""

    monkeypatch.setattr("c4.utils.command.execute", vm)
    assert isVirtualMachine()

def test_getModuleClasses():
    import c4.utils.command
    assert c4.utils.command.CommandException in getModuleClasses(c4.utils.command)
    assert c4.utils.command.CommandException in getModuleClasses(c4.utils.command, baseClass=Exception)

    import c4.utils.jsonutil
    assert c4.utils.jsonutil.JSONSerializable in getModuleClasses(c4.utils.jsonutil)

def test_mergeDictionaries():

    one = {"same": 1,
           "valueChange1": 1,
           "valueChange2": {"test": "test"},
           "valueChange3": {"test": {"test2": "test"}},
           "onlyInOne": 1
           }

    two = {"same": 1,
           "valueChange1": 2,
           "valueChange2": {"test": "newValue"},
           "valueChange3": {"test": {"test2": "newValue"}},
           "onlyInTwo1": 1,
           "onlyInTwo2": {"test": "test"}
           }

    merged = mergeDictionaries(one, two)

    assert merged["same"] == 1
    assert merged["onlyInOne"] == 1
    assert merged["onlyInTwo1"] == 1
    assert merged["onlyInTwo2"] == {"test": "test"}
    assert merged["valueChange1"] == 2
    assert merged["valueChange2"] == {"test": "newValue"}
    assert merged["valueChange3"] == {"test": {"test2": "newValue"}}

def test_sortHostnames():

    assert sortHostnames(["localhost", "localhost.localdomain"]) == ["localhost.localdomain", "localhost"]
    assert sortHostnames(["localhost.localdomain", "localhost"]) == ["localhost.localdomain", "localhost"]
    assert sortHostnames(["localhost", "localhost.localdomain", "localhost4", "localhost4.localdomain4"]) == ["localhost.localdomain", "localhost4.localdomain4", "localhost", "localhost4"]
    assert sortHostnames(["a.b.c", "a", "b"]) == ["a.b.c", "a", "b"]
    assert sortHostnames(["b", "a", "a.b.c"]) == ["a.b.c", "a", "b"]
    assert sortHostnames(["a.b.c", "b.b.c", "a"]) == ["a.b.c", "b.b.c", "a"]
    assert sortHostnames(["b.b.c", "a", "a.b.c"]) == ["a.b.c", "b.b.c", "a"]
    assert sortHostnames(["a.b.c", "b.b", "c.b.c", "a"]) == ["b.b", "a.b.c", "c.b.c", "a"]
    assert sortHostnames(["a", "c.b.c", "b.b", "a.b.c"]) == ["b.b", "a.b.c", "c.b.c", "a"]
