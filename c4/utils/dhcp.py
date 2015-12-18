"""
This library contains DHCP and DNS utility functions

Functionality
-------------
"""

import logging
import datetime

log = logging.getLogger(__name__)

class Lease(object):
    """
    A utility class that represents a DHCP lease with optional DNS information

    :param leaseEpochTime: lease time in seconds since epoch
    :type leaseEpochTime: int
    :param mac: MAC address
    :type mac: str
    :param ip: IP address
    :type ip: str
    :param hostname: hostname
    :type hostname: str
    :param clientId: DHCP client id
    :type clientId: str
    """
    def __init__(self, leaseEpochTime, mac, ip, hostname=None, clientId=None):
        self.leaseEpochTime = int(leaseEpochTime)
        self.leaseTime = datetime.datetime.fromtimestamp(self.leaseEpochTime)
        self.mac = mac
        self.ip = ip
        self.hostname = hostname
        self.clientId = clientId

    @staticmethod
    def fromString(string):
        """
        Load lease info from the specified string

        :param string: a lease string
        :type string: str
        :returns: :class:`~Lease` or ``None``
        """
        info = string.split()
        for i, value in enumerate(info):
            if value == "*":
                info[i] = None
        return Lease(*info)

    def __str__(self):
        return str(self.__dict__)

class LeaseMap(object):
    """
    A DHCP/DNS information class that can be used to lookup information on
    leases such hostnames, IP addresses, and MAC addresses
    """
    def __init__(self):
        self.leases = []

    @staticmethod
    def fromString(string):
        """
        Load lease infos from the specified string

        :param string: a lease infos string
        :type string: str
        :returns: :class:`~LeaseMap`
        """
        leaseMap = LeaseMap()
        lines = string.splitlines()
        for line in lines:
            lease = Lease.fromString(line)
            if lease:
                leaseMap.leases.append(lease)
            else:
                log.error("could not parse lease from '%s'", line)
        return leaseMap

    @staticmethod
    def fromFile(fileName):
        """
        Load lease infos from the specified file

        :param fileName: a file with lease infos
        :type fileName: str
        :returns: :class:`~LeaseMap`
        """
        leaseMap = LeaseMap()
        with open(fileName) as leaseFile:
            string = leaseFile.read()
            leaseMap = LeaseMap.fromString(string)
        return leaseMap

    def getHostnameByIP(self, ip):
        """
        Get hostname for IP the address

        :param ip: IP address
        :type ip: str
        :returns: str
        """
        for lease in self.leases:
            if lease.ip == ip:
                return lease.hostname
        return None

    def getIPByHostname(self, hostname):
        """
        Get IP address for the hostname

        :param hostname: hostname
        :type hostname: str
        :returns: str
        """
        for lease in self.leases:
            if lease.hostname == hostname:
                return lease.ip
        return None

    def getMACByHostname(self, hostname):
        """
        Get MAC address for the hostname

        :param hostname: hostname
        :type hostname: str
        :returns: str
        """
        for lease in self.leases:
            if lease.hostname == hostname:
                return lease.mac
        return None
