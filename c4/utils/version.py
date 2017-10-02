"""
Copyright (c) IBM 2015-2017. All Rights Reserved.
Project name: c4-utils
This project is licensed under the MIT License, see LICENSE
"""
import re

import distutils.version

class BasicVersion(distutils.version.Version):
    """
    Basic version class that roughly follows :class:`~distutils.version.StrictVersion` but
    adds support for:

    - single digit versions, e.g., 1, 2, etc.
    - development releases, e.g., 1.2.dev3, 1.2.3d10
    """
    RELEASE_DESIGNATIONS = {
        "a": "alpha",
        "alpha": "alpha",
        "b": "beta",
        "beta": "beta",
        "d": "dev",
        "dev": "dev",
    }

    VERSION_PART_REGEX = re.compile(r"^(\d+)? ([a-z]+)? (\d+)?$",
                                    re.VERBOSE)

    def __cmp__ (self, other):
        if isinstance(other, str):
            other = BasicVersion(other)
        elif not isinstance(other, BasicVersion):
            raise ValueError("'{0}' must be of type '{1}'".format(other, BasicVersion))

        versionPartComparison = cmp(self.parts, other.parts)
        if versionPartComparison == 0:

            if self.release:
                if other.release:

                    # compare release designations
                    releaseComparison = cmp(self.release, other.release)
                    if releaseComparison == 0:
                        # compare release numbers
                        return cmp(self.releaseNumber, other.releaseNumber)
                    else:
                        return releaseComparison

                else:
                    # version has release designation
                    return -1

            else:
                if other.release:
                    # other version has release designation
                    return 1
                else:
                    # neither has release
                    return 0

        else:
            return versionPartComparison

    def __str__ (self):

        versionString = [str(part) for part in self.parts]
        if self.release:
            versionString.append(self.release)
            if self.releaseNumber != 0:
                versionString.append(str(self.releaseNumber))
        return ".".join(versionString)

    def parse(self, versionString):

        parts = [part.strip() for part in versionString.strip().split(".")]

        # add 0 implicitely for single version numbers, e.g., 2 -> 2.0
        if len(parts) == 1:
            parts.append("0")

        # first numbers must be integers
        try:
            self.parts = [int(part) for part in parts[:-1]]
        except Exception:
            raise ValueError("Version '{0}' must start with a sequence of numbers, e.g., 1.2.3".format(versionString))

        match = self.VERSION_PART_REGEX.match(parts[-1])
        if match is None:
            raise ValueError("Version '{0}' ends with an invalid '{1}' part".format(versionString, parts[-1]))

        # add trailing version number, e.g., 2dev3 -> 2
        if match.group(1):
            self.parts.append(int(match.group(1)))

        # remove trailing zeros, e.g., 1.0.0 -> 1
        while self.parts[-1] == 0 and len(self.parts) > 1:
            self.parts.pop()

        # set release designation
        if match.group(2):
            if match.group(2) not in self.RELEASE_DESIGNATIONS.keys():
                errorString = "Release designation '{0}' is invalid, allowed are '{1}'"
                raise ValueError(errorString.format(match.group(2),
                                                    ",".join(sorted(self.RELEASE_DESIGNATIONS.keys()))))
            else:
                self.release = self.RELEASE_DESIGNATIONS[match.group(2)]

        else:
            self.release = None

        # set release number
        self.releaseNumber = int(match.group(3)) if match.group(3) else 0

class RPMVersion(distutils.version.Version):
    """
    Basic RPM version class that roughly follows :class:`~distutils.version.StrictVersion` but
    adds support for:

    - release designations, e.g., 2.1.0-10.20, etc.
    """
    def __cmp__ (self, other):
        if isinstance(other, str):
            other = RPMVersion(other)
        elif not isinstance(other, RPMVersion):
            raise ValueError("'{0}' must be of type '{1}'".format(other, RPMVersion))

        versionComparison = cmp(self.version, other.version)
        if versionComparison == 0:
            return cmp(self.release, other.release)
        else:
            return versionComparison

    def __str__ (self):

        version = ".".join([str(part) for part in self.version.parts])
        release = ".".join([str(part) for part in self.release.parts])
        return "{version}-{release}".format(version=version, release=release)

    def parse(self, versionString):

        try:
            version, release = versionString.split("-", 1)
        except Exception:
            raise ValueError("Version '{0}' must follow format 'version-release'".format(versionString))

        self.version = BasicVersion(version)

        # sanitize release part by removing dist and architecture
        releaseParts = []
        for part in release.split("."):
            try:
                releaseParts.append(str(int(part)))
            except Exception:
                pass
        self.release = BasicVersion(".".join(releaseParts))
