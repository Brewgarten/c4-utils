import pytest
import re
import signal

from multiprocessing import Process

from c4.utils.util import EtcHosts, exclusiveWrite, isVirtualMachine, getModuleClasses, mergeDictionaries, sortHostnames

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

    monkeypatch.setattr("c4.execute", baremetal)
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

    import c4.messaging
    assert c4.messaging.Peer in getModuleClasses(c4.messaging)
    assert c4.messaging.MessageClient in getModuleClasses(c4.messaging)
    assert c4.messaging.PeerRouter in getModuleClasses(c4.messaging, baseClass=Process)
    assert c4.messaging.DealerRouter in getModuleClasses(c4.messaging, baseClass=c4.utils.util.NamedProcess)

    assert c4.messaging.Envelope("from","to","action").typeAsString == "c4.Envelope"

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

def __getCmd():
    cmdline = bytes(open('/proc/self/cmdline', 'rb').read())
    argv = cmdline.split(chr(0))
    name = cmdline.replace(chr(0), ' ')
    return name.rstrip(chr(0) + ' '), argv, len(cmdline)

def test_setProcessName():
    import ctypes
    from c4.utils.util import Argv, setProcessName

    pname = "test_setProcessName"
    name, argv, size = __getCmd()
    setProcessName(pname)
    nname, _, nsize = __getCmd()

    assert nsize == size, 'nsize:{0}, size:{1}, nname{2}'.format(nsize, size, nname)
    assert nname != name, 'nname:{0}, name:{1}'.format(nname, name)
    assert nname.rstrip(chr(0)) == pname, 'nname:{0}, pname:{1}'.format(nname, pname)
    assert nsize <= Argv.instance().allocatedSize, 'nsize:{0}, alloc:{1}'.format(Argv.instance().allocatedSize)

def test_namedProcess():
    from c4.utils.util import NamedProcess
    from multiprocessing import Queue
    from types import DictType

    def checkName(q, myname):
        name, _, size = __getCmd()
        r = {'name-check' : 'name:{0} myname:{1}'.format(name, myname) if name != myname else ''}
        if hasattr(q, 'put'):
            q.put(r)
        else:
            q['return'] = r

    q = Queue()
    proc = NamedProcess(name='forked-proc', target=checkName, args=(q, 'forked-proc'))
    proc.start()
    v = q.get()
    assert v['name-check'] == '', v['name-check']
    proc.join()

    q = {}
    proc = NamedProcess(name='un-forked-proc', target=checkName, args=(q, 'un-forked-proc'))
    proc.run()
    v = q['return']
    assert v['name-check'] != '', v['name-check']

    q = {}
    proc = NamedProcess(name='un-forked-proc', target=checkName, args=(q, 'un-forked-proc'), setParentName=True)
    proc.run()
    v = q['return']
    assert v['name-check'] == '', v['name-check']

def test_reaper():
    from c4.utils.util import NamedProcess, setupReaper
    import time

    def status(pid):
        try:
            f = file('/proc/{0}//status'.format(pid))
            f.readline()
            line = f.readline()
        except:
            line = ''
        return line

    def iszombie(pid):
        line = status(pid).split()
        return len(line) > 1 and line[1] == 'Z'

    pids = []
    setupReaper()

    for i in range(5):
        c = NamedProcess(name="reap-{0}".format(i), target=lambda :time.sleep(0.5))
        c.start()
        pids.append(c.pid)

    time.sleep(1)
    zombies = filter(iszombie, pids)

    # reset signal handler
    signal.signal(signal.SIGCHLD, 0)

    assert len(zombies) == 0, '{0} zombies : pids:{1}, status:{2}'.format(len(zombies), zombies, map(status, zombies))

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
