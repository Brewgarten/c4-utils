import pytest

from c4.utils.version import BasicVersion, RPMVersion

class TestBasicVersion():

    def test_comparison(self):

        assert BasicVersion("1.2") == BasicVersion("1.2")
        assert BasicVersion("1.2") == "1.2"

        assert BasicVersion("1.2") == BasicVersion("1.2.0.0")

        assert BasicVersion("1.2") > BasicVersion("1.2alpha")
        assert BasicVersion("1.2beta") < BasicVersion("1.2")
        assert BasicVersion("1.2a") < BasicVersion("1.2beta")
        assert BasicVersion("1.2.dev123") < BasicVersion("1.2dev456")

    def test_parsing(self):

        # short version
        version = BasicVersion("1")
        assert version.parts == [1]
        assert version.release is None
        assert version.releaseNumber == 0

        # long version
        version = BasicVersion("1.2.3.4")
        assert version.parts == [1, 2, 3, 4]
        assert version.release is None
        assert version.releaseNumber == 0

        # release versions
        version = BasicVersion("1.2.3dev456")
        assert version.parts == [1, 2, 3]
        assert version.release == "dev"
        assert version.releaseNumber == 456

        version = BasicVersion("1.2.3.a456")
        assert version.parts == [1, 2, 3]
        assert version.release == "alpha"
        assert version.releaseNumber == 456

        version = BasicVersion("1.2beta")
        assert version.parts == [1, 2]
        assert version.release == "beta"
        assert version.releaseNumber == 0

        # must start with number
        with pytest.raises(ValueError):
            BasicVersion("invalid")

        # cannot have multiple special release designation
        with pytest.raises(ValueError):
            BasicVersion("1.2a.3b")

        # special release designation must be last part
        with pytest.raises(ValueError):
            BasicVersion("1.2a.3")

        # invalid release designation
        with pytest.raises(ValueError):
            BasicVersion("1.2test")

class TestRPMVersion():

    def test_comparison(self):

        assert RPMVersion("1.2-0") == RPMVersion("1.2-0")
        assert RPMVersion("1.2-0") == "1.2-0"

        assert RPMVersion("1.2-0") == RPMVersion("1.2.0.0-0")

        assert RPMVersion("1.2-100") > RPMVersion("1.2-0")
        assert RPMVersion("1.2-1.2.3") < RPMVersion("1.2-1.3")

    def test_parsing(self):

        # short version
        version = RPMVersion("1-0")
        assert version.version.parts == [1]
        assert version.release.parts == [0]

        # long version
        version = RPMVersion("1.2.3.4-5.6.7")
        assert version.version.parts == [1, 2, 3, 4]
        assert version.release.parts == [5, 6, 7]

        # must follow format
        with pytest.raises(ValueError):
            RPMVersion("invalid")
