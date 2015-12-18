"""
This library contains utility functions

Timer
-----

The following example can be used to set up a timer that will call the ``hello``
function after 5 seconds, then wait 10 seconds and call ``hello`` again another
two times for a total of three calls.

.. code-block:: python

    def hello():
        print "hello"
    timer = Timer("ExampleTimer", hello, initial=5, repeat=3, interval=10)
    timer.start()

Stop Flag Process
-----------------

In multiprocess environments it may become necessary for child or other process to
have control over a particular process, especially stopping it. This can be done
using the :class:`~c4.utils.util.StopFlagProcess`. For example, in order to
allow the pool workers in the :class:`~c4.messaging.AsyncMessageServer` to stop
the server one can do the following:

Create a handler class that makes use of a stop flag variable and add it to the message
server as a handler

.. code-block:: python

    class Handler(object):

        def __init__(self):
            self.stopFlag = None

        def handleMessage(self, message):
            if message == "stop":
                self.stopFlag.set()
            else:
                print message

    handler = Handler()
    messageServer = AsyncMessageServer("tcp://127.0.0.1:5000", "MessageServer")
    messageServer.addHandler(handler.handleMessage)


Connect the stop flag of the handler class to the one of the message server

.. code-block:: python

    handler.stopFlag = messageServer.stopFlag

Worker Pool
-----------

Process or worker pools can be used to distribute and parallelize long running task
and computations. We can utilize the :class:`Worker` class effectively to achieve
this.

Create a task queue and a list of workers

.. code-block:: python

    tasks = multiprocessing.JoinableQueue()
    workerProcesses = [Worker(tasks).start() for i in range(10)]

Add tasks to the task queue

.. code-block:: python

    def work(one, two):
        ...perform long running task

    tasks.put((work, [1, 2]))

Stop the worker pool by filling up the task queue with ``None``, then terminating
and joining the worker processes

.. code-block:: python

    for i in range(10):
        tasks.put(None)
    for w in workerProcesses:
        w.terminate()
    for w in workerProcesses:
        w.join()

Functionality
-------------
"""

import collections

import copy
import fcntl
import inspect
import logging
import multiprocessing
import multiprocessing.managers
import os
import pkgutil
import re
import signal
import sys
import time
import traceback

import c4.utils.command
import c4.utils.logutil

log = logging.getLogger(__name__)

@c4.utils.logutil.ClassLogger
class EtcHosts(collections.OrderedDict):
    """
    A representation of the ``/etc/hosts`` file that allows
    management of host to ip resolution
    """

    def add(self, alias, ip, replace=False):
        """
        Add alias to specified ip.

        :param alias: alias/host name
        :type alias: str
        :param ip: ip address
        :type ip: str
        :param replace: replace existing ip entries for the alias with the new ip
        :type replace: bool
        :returns: alias
        :rtype: str
        """
        if ip not in self:
            self[ip] = set()
        if alias in self[ip]:
            self.log.warn("did not add alias '%s' to '%s' because it already exists", alias, ip)
            return None

        if replace:
            # check if alias already used for a different ip
            for existingIp, aliases in self.items():
                if alias in aliases:
                    # remove alias from the existing ip
                    self.log.warn("changing ip from '%s' to '%s' for alias '%s'", existingIp, ip, alias)
                    self[existingIp].remove(alias)
                    if not self[existingIp]:
                        del self[existingIp]

        self[ip].add(alias)
        return alias

    @staticmethod
    def fromString(string):
        """
        Load object from the specified ``/etc/hosts`` compatible string representation

        :param string: ``/etc/hosts`` compatible string representation
        :type string: str
        :returns: etcHosts object
        :rtype: :class:`~EtcHosts`
        """
        etcHosts = EtcHosts()
        for line in string.splitlines():
            # strip comments
            lineWithoutComments = line.split("#")[0]
            if lineWithoutComments.strip():
                entries = lineWithoutComments.split()
                ip = entries.pop(0).strip()
                etcHosts[ip] = set(entries)
        return etcHosts

    def toString(self):
        """
        Get an ``/etc/hosts`` compatible string representation

        :returns: string representation
        :rtype: str
        """
        entries = []
        for ip, aliases in self.items():
            sortedHostnames = sortHostnames(aliases)
            entries.append("{ip} {aliases}".format(ip=ip, aliases=" ".join(sortedHostnames)))
        return "\n".join(entries) + "\n"

@c4.utils.logutil.ClassLogger
class SharedDictWithLock(collections.MutableMapping, dict):
    """
    A dictionary class that can be shared across processes and performs
    automatic locking.
    """

    def __init__(self):
        self.manager = multiprocessing.managers.SyncManager()
        self.manager.start(disableInterruptSignal)
        self.dict = self.manager.dict()
        self.lock = self.manager.RLock()

    def __getitem__(self, key):
        try:
            return self.dict[key]
        except KeyError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        self.lock.acquire()
        self.dict[key] = value
        self.lock.release()

    def __delitem__(self, key):
        self.lock.acquire()
        try:
            del self.dict[key]
        except KeyError:
            raise KeyError(key)
        finally:
            self.lock.release()

    def keys(self):
        """
        Return a copy of the dictionary's list of keys.
        """
        return self.dict.keys()

    def values(self):
        """
        Return a copy of the dictionary's list of values.
        """
        return self.dict.values()

    def __iter__(self):
        raise NotImplementedError("Iterating over a shared dictionary is not supported")

    def __len__(self):
        return len(self.dict)

    def __str__(self, *args, **kwargs):
        return str(self.dict)

@c4.utils.logutil.ClassLogger
class StopFlagProcess(multiprocessing.Process):
    """
    A separate process that can be used to monitor and stop another process using a
    shared `stop flag`.

    :param process: process
    :type process: :class:`multiprocessing.Process`
    """
    def __init__(self, process):
        super(StopFlagProcess, self).__init__(name="{}-StopFlagProcess".format(process.name))
        self.process = process
        self.stopFlag = multiprocessing.Event()

    def run(self):
        """
        The implementation of the stop flag process. In particular we wait on the shared
        `stop flag` and then attempt to terminate the specified process
        """
        try:
            self.stopFlag.wait()
        except EOFError:
            # ignore broken sync manager pipe for the shared event when process is terminated
            pass
        except KeyboardInterrupt:
            # ignore interrupts when process is terminated
            pass
        except SystemExit:
            # ignore system exit events when process is terminated
            pass
        except:
            self.log.error(traceback.format_exc())
        try:
            self.process.terminate()
        except OSError as e:
            if str(e) == "[Errno 3] No such process":
                # ignore when process is already terminated
                pass
            else:
                self.log.error(traceback.format_exc())
        except:
            self.log.error(traceback.format_exc())

@c4.utils.logutil.ClassLogger
class Timer(multiprocessing.Process):
    """
    A timer that can be used to call a function at a specified time as well as
    repeatedly using an interval

    :param name: name of the timer process
    :type name: str
    :param function: a timer function to be called once the timer is reached
    :type function: func
    :param initial: initial wait time before timer function is fired for the first time (in seconds)
    :type initial: float
    :param repeat: how many times the timer function is to be repeated, use ``-1`` for infinite
    :type repeat: int
    :param interval: wait time between repeats (in seconds)
    :type interval: float
    """
    def __init__(self, name, function, initial=0, repeat=0, interval=0):
        super(Timer, self).__init__(name=name)
        self.initial = initial
        self.repeat = repeat
        self.interval = interval
        self.function = function

    def run(self):
        """
        Timer implementation
        """
        try:
            time.sleep(self.initial)
            if self.repeat < 0:
                while True:
                    self.function()
                    time.sleep(self.interval)
            else:
                while self.repeat >= 0:
                    self.function()
                    time.sleep(self.interval)
                    self.repeat -= 1
        except KeyboardInterrupt:
            self.log.debug("Exiting %s", self.name)
        except:
            self.log.debug("Forced exiting %s", self.name)
            self.log.error(traceback.format_exc())

@c4.utils.logutil.ClassLogger
class Worker(multiprocessing.Process):
    """
    A worker process that picks up tasks from the specified task queue

    :param taskQueue: task queue
    :type taskQueue: :class:`~multiprocessing.JoinableQueue`
    :param name: name
    :type name: str

    .. note::

        The task being put on the task queue need to be specified as a tuple
        using the following format: ``(function, [argument, ...])``

    """
    def __init__(self, taskQueue, name=None):
        super(Worker, self).__init__(name=name)
        self.taskQueue = taskQueue

    def run(self):
        """
        Worker implementation
        """
        running = True
        while running:
            task = self.taskQueue.get()
            if task:
                try:
                    (function, arguments) = task
                    function(*arguments)
                except:
                    self.log.debug(traceback.format_exc())
                    self.log.debug(task)
            else:
                running = False
            self.taskQueue.task_done()

    def start(self):
        """
        Start worker

        :returns: :class:`Worker`
        """
        super(Worker, self).start()
        return self

def addressesMatch(baseAddress, *potentialAddresses):
    """
    Check if potential addresses match base address

    :param baseAddress: base address
    :type baseAddress: str
    :param potentialAddresses: potential addresses
    :type potentialAddresses: str
    :returns: bool
    """
    # filter out None
    potentialAddresses = [p for p in potentialAddresses if p is not None]
    base = baseAddress.split("/")

    for potentialAddress in potentialAddresses:

        potential = potentialAddress.split("/")
        if len(base) == len(potential):

            match = True
            parts = zip(base, potential)
            for basePart, potentialPart in parts:
                if basePart != potentialPart:
                    if basePart != "*" and potentialPart != "*":
                        match = False
            if match:
                return True

    return False

def callWithVariableArguments(handler, *arguments, **keyValueArguments):
    """
    Call the handler method or function with a variable number of arguments

    :param handler: handler
    :type handler: method or func
    :param arguments: handler arguments
    :param keyValueArguments: handler key value arguments
    :returns: response
    """
    handlerArgSpec = inspect.getargspec(handler)
    if inspect.ismethod(handler):
        handlerArguments = handlerArgSpec.args[1:]
    elif inspect.isfunction(handler):
        handlerArguments = handlerArgSpec.args
    else:
        log.error("%s needs to be a method or function", handler)
        return

    if len(arguments) > len(handlerArguments):
        # more arguments than handler expects. Ignore them
        diff = len(arguments) - len(handlerArguments)
        log.debug("%s arguments given, when %s expects only %s, ignoring last %s",
                    len(arguments), handler, len(handlerArguments), diff)
        arguments = arguments[:-diff]

    elif len(arguments) < len(handlerArguments):
        # if we don't have enough arguments that handler expects then error out
        # only if there are no defaults specified
        if len(arguments) + len(handlerArgSpec.defaults) == len(handlerArguments):
            # if handler has specified N defaults then we can tolerate if last N arguments
            # aren't present
            arguments = list(arguments) + list(handlerArgSpec.defaults)
        else:
            log.error("Handler %s requires %s arguments[%s] (defaults:%s) but only %s [%s] given",
                      handler, len(handlerArguments), handlerArguments, handlerArgSpec.defaults,
                      len(arguments), arguments)
            return None

    if handlerArgSpec.varargs:
        arguments = list(arguments) + list(handlerArgSpec.varargs)

    if handlerArgSpec.keywords is not None:
        return handler(*arguments, **handlerArgSpec.keywords)

    return handler(*arguments)

def confirmPrompt(prompt=None, default="no"):
    """
    Present a confirmation dialog to the user.

    If confirmed do nothing else exit

    :param prompt: prompt message
    :type prompt: str
    :param default: default answer (yes | no)
    :type default: str
    """
    yes = ["y", "ye", "yes"]
    no = ["n", "no"]

    if not prompt:
        prompt = "Proceed?"
    if default == "yes":
        prompt += " [Y/n]: "
    else:
        prompt += " [y/N]: "

        while True:
            try:
                userInput = raw_input(prompt).lower()
            except:
                exit(1)

            if default is not None and not userInput:
                userInput = default
            if userInput in yes:
                return
            elif userInput in no:
                exit(1)

def disableInterruptSignal():
    """
    Set the interrupt signal of the current process to be ignored

    .. note::

        This may be necessary in sub processes, especially pools to
        handle :py:class:`~KeyboardInterrupt` and other exceptions correctly
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def exclusiveWrite(fileName, string, append=True, tries=3, timeout=1):
    """
    Perform an exclusive write to the specified file

    :param fileName: file name
    :type fileName: str
    :param string: string to be written to file
    :type string: str
    :param append: append to or overwrite the contents of the file
    :type append: bool
    :param tries: number of tries to acquire lock
    :type tries: int
    :param timeout: time out between retries (in seconds)
    :type timeout: float
    :raise OSError: if lock could not be acquired within specified tries
    """
    mode = 'w'
    if append:
        mode = 'a'
    with open(fileName, mode) as f:
        while tries > 0:
            try:
                fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                f.write(string)
                fcntl.lockf(f, fcntl.LOCK_UN)
                break
            except IOError:
                pass
            tries -= 1
            time.sleep(timeout)
        if tries < 1:
            raise OSError("Could not acquire lock on '{0}' before timeout".format(fileName))

def getFullModuleName(o):
    """
    Get the full module name of an object or class

    :param o: an object or class
    :returns: the full module name of the object

    .. note::

        This is necessary because when executing scripts the top level
        module is referenced as ``__main__`` instead of its full name.
        See `PEP 395 -- Qualified Names for Modules <http://legacy.python.org/dev/peps/pep-0395/>`_

    """
    if o.__module__ != "__main__":
        return o.__module__

    parentDirectory, filename = os.path.split(sys.modules["__main__"].__file__)
    moduleName = os.path.splitext(filename)[0]

    while os.path.exists(parentDirectory + "/__init__.py"):

        parentDirectory, directory = os.path.split(parentDirectory)
        moduleName = directory + '.' + moduleName

    return moduleName

def getModuleClasses(module, baseClass=None, includeSubModules=True):
    """
    Get all classes part of the specified module

    :param module: module
    :type module: mod
    :param baseClass: restrict classes by their base class
    :type baseClass: class
    :param includeSubModules: include sub modules in search
    :type includeSubModules: bool
    :returns: [class]
    """
    modules = [module]
    if includeSubModules:
        # load sub modules
        modules.extend(getSubModules(module))

    classes = set()
    for m in modules:
        for o in m.__dict__.values():
            # make sure object is a class and its module is a submodule
            if inspect.isclass(o) and o.__module__.startswith(module.__name__):
                classes.add(o)

    if baseClass:
        return [clazz for clazz in classes if issubclass(clazz, baseClass)]
    else:
        return list(classes)

def getSubModules(module, ignoreErrors=False):
    """
    Recursively find all sub modules of the specified module

    :param module: module
    :type module: mod
    :returns: [mod]
    """
    submodules = []
    if hasattr(module, "__path__"):
        for importer, moduleName, ispkg in pkgutil.iter_modules(module.__path__, module.__name__ + '.'):
            try:
                subModule = __import__(moduleName, fromlist=[moduleName])
                submodules.append(subModule)
                submodules.extend(getSubModules(subModule))
            except ImportError as ie:
                log.debug("Cannot import %s: %s", moduleName, ie)
                if not ignoreErrors:
                    raise

    return submodules

def isVirtualMachine():
    """
    Determine if we are in a virtual machine

    :returns: ``True`` if block devices indicate virtual machine, ``False`` otherwise
    :rtype: bool
    """
    try:
        lsblkCommand = ["/bin/lsblk",
                        "--ascii",
                        "--noheadings",
                        "--nodeps",
                        "--output",
                        "name,type"]
        lsblkOutput = c4.utils.command.execute(lsblkCommand, "Could not execute lsblk command")

        # filter out disk names
        diskNames = [info.split()[0].strip()
                     for info in lsblkOutput.splitlines()
                     if info and info.split()[1].strip() == "disk"]

        for diskName in diskNames:
            if diskName.startswith("xvd") or diskName.startswith("vd"):
                return True
        return False

    except Exception as e:
        log.error("Could not determine whether this is a virtual machine or not")
        log.exception(e)
        return False

def killProcessesUsingFileSystem(path):
    """
    Kill processes on the mounted file system containing specified path

    :param path: path
    :type path: str
    """
    try:
        c4.utils.command.execute(["/sbin/fuser", "-c", path])
    except:
        log.debug("No active processes on the mounted file system containing '%s'", path)
        return
    try:
        log.warn("All processes on the mounted file system containing '%s' are being killed", path)
        c4.utils.command.execute(["/sbin/fuser", "-c", "-k", path])
    except Exception as e:
        log.exception(e)

def naturalSortKey(string):
    """
    Convert string into a natural sort key that honors numbers and hyphens

    :param string: string
    :type string: str
    """
    key = []
    partPattern = re.compile("(/)")
    subpartPattern = re.compile("(-)")
    portionPattern = re.compile("(\d+)")
    for part in partPattern.split(string):
        for subpart in subpartPattern.split(part):
            for portion in portionPattern.split(subpart):
                if portion:
                    if portion.isdigit():
                        key.append(int(portion))
                    else:
                        key.append(portion)
    return key

def mergeDictionaries(one, two):
    """
    Merge two dictionaries

    :param one: first dictionary
    :type one: dict
    :param two: second dictionary
    :type two: dict
    :returns: merged dictionary
    :rtype: dict
    """
    if not isinstance(two, dict):
        return copy.deepcopy(two)

    oneKeys = set(one.keys())
    twoKeys = set(two.keys())

    inBothKeys = oneKeys.intersection(twoKeys)
    oneOnlyKeys = oneKeys - inBothKeys
    twoOnlyKeys = twoKeys - inBothKeys

    merged = {}

    # copy all that is in one
    for key in oneOnlyKeys:
        merged[key] = copy.deepcopy(one[key])

    # copy all that is in two
    for key in twoOnlyKeys:
        merged[key] = copy.deepcopy(two[key])

    # check the keys that are the same and copy the new values
    for key in inBothKeys:

        if isinstance(one[key], dict):
            merged[key] = mergeDictionaries(one[key], two[key])
        else:
            merged[key] = copy.deepcopy(two[key])

    return merged

def sortHostnames(hostnames):
    """
    Sort fully qualified hostnames based on their domain hierarchy. Note that aliases and
    non-qualified names will come after the fully qualified ones.

    :param hostnames: hostnames
    :type hostnames: [str]
    :returns: sorted hostnames
    :rtype: [str]
    """
    hostnameParts = []
    aliases = []
    for hostname in hostnames:
        parts = hostname.split(".")
        if len(parts) > 1:
            parts.reverse()
            hostnameParts.append(parts)
        else:
            aliases.append(hostname)

    hostnameParts.sort()
    aliases.sort()

    sortedHostnames = [".".join(reversed(hostnamePart)) for hostnamePart in hostnameParts]
    sortedHostnames.extend(aliases)
    return sortedHostnames