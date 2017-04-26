import pytest

from c4.utils.command import execute, CommandException

def test_execute_withOutput():
    response = execute(["ls", "/"])
    assert response is not None

def test_execute_withoutOutput():
    response = execute(["touch", "/tmp/test"])
    assert response is None

def test_execute_fail():
    try:
        execute(["ls", "/test"], "/test does not exist")
    except CommandException as e:
        assert "No such file or directory" in e.error

def test_execute_exception():
    with pytest.raises(CommandException):
        execute(["ls", "/test"])

def test_execute_unknownCommand():
    try:
        execute(["testcommand"])
    except CommandException as e:
        assert "No such file or directory" in e.error
