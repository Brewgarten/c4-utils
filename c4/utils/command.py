"""
This library contains methods for executing commands, capturing their output
and raising exceptions accordingly.

Functionality
-------------
"""

import logging
import os
import shlex
import subprocess
from pwd import getpwuid
from os import geteuid

log = logging.getLogger(__name__)

class CommandException(Exception):
    """
    The exception being thrown in case of an error

    :param command: the command array
    :type command: [str]
    :param returnCode: return code
    :type returnCode: int
    :param output: output
    :type output: str
    :param error: error output
    :type error: str
    :param message: message
    :type message: str
    """
    def __init__(self, command, returnCode, output=None, error=None, message=None):
        self.command = command
        self.returnCode = returnCode
        self.output = output
        self.error = error
        self.message = message

    def __str__(self):
        string = "Command '%s' returned non-zero exit status %d" % (" ".join(self.command), self.returnCode)
        if self.message:
            string = "%s: %s" % (self.message, string)
        if self.output:
            string = "%s\n%s" % (string, self.output)
        if self.error:
            string = "%s\n%s" % (string, self.error)
        return string

def execute(command, errorMessage=None, finallyClause=None, user=None):
    """
    Execute command, e.g.:

    .. code-block:: python

        execute(["/usr/lpp/mmfs/bin/mmstartup", "-a"], "Could not startup GPFS")

    :param command: the command array
    :type command: [str]
    :param errorMessage: the message to be displayed in case of an error
    :type errorMessage: str
    :param finallyClause: the function executed in the finally clause in case of an error
    :type finallyClause: func
    :returns: output
    :raises: :class:`CommandException`
    """
    try:
        if user and getpwuid(geteuid()).pw_name == user:
            user = None

        if user:
            log.debug("Executing: %s as %s" % (" ".join(command), user))
            command = ["/usr/bin/sudo", "-u", user] + command
        else:
            log.debug("Executing: %s" % " ".join(command))
        # kick off process
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # retrieve output and errors
        output, error = process.communicate()
        output = output.rstrip()
        error = error.rstrip()

        # check return code
        returnCode = process.poll()
        if returnCode:
            raise CommandException(command, returnCode, output, error, errorMessage)
        if output:
            log.debug(output)
            return output
    except OSError as e:
        raise CommandException(command, -1, error=str(e), message=errorMessage)
    except Exception as e:
        raise e
    finally:
        if finallyClause:
            finallyClause()

def run(command, workingDirectory=None):
    """
    Run command using the current or specified working directory
    :param command: command
    :type command: str
    :param workingDirectory: working directory
    :type str
    :returns: tuple of stdout, stderr and return code
    :rtype: (stdout, stderr, status)
    """
    if not workingDirectory:
        workingDirectory = os.getcwd()

    if not os.path.exists(workingDirectory):
        return "", "Path '{path}' does not exist".format(path=workingDirectory), 1

    log.debug("Running '%s' on '%s'", command, workingDirectory)
    process = subprocess.Popen(
        [part for part in shlex.split(command)],
        cwd=workingDirectory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # retrieve output and errors
    stdout, stderr = process.communicate()
    stdout = stdout.rstrip()
    stderr = stderr.rstrip()

    # check return code
    status = process.poll()

    return stdout, stderr, status
