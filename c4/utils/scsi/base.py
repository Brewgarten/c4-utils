"""
Copyright (c) IBM 2015-2017. All Rights Reserved.
Project name: c4-utils
This project is licensed under the MIT License, see LICENSE
"""
import logging

from abc import ABCMeta, abstractproperty

log = logging.getLogger(__name__)

class ControllerInfo(object):
    """
    SCSI controler information

    :param controller: controller id
    :type controller: int
    """
    def __init__(self, controller):
        self.controller = controller
        self.logicalDevices = {}
        self.physicalDevices = {}

    @property
    def logicalDevicesbyNameMap(self):
        """
        Logical device by name mapping
        """
        return {device.name: device
                for device in self.logicalDevices.values()}

    @property
    def physicalDevicesbyIdMap(self):
        """
        Physical device by id mapping
        """
        return {device.id: device
                for device in self.physicalDevices.values()}

class DevicesInfo(object):
    """
    SCSI devices information
    """
    LOGICAL_DEVICES_INFO_COMMAND = None
    PHYSICAL_DEVICES_INFO_COMMAND = None

    def __init__(self):
        self.controllers = {}

    # TODO: enforce abstract to be implemented, see http://stackoverflow.com/questions/11217878/python-2-7-combine-abc-abstractmethod-and-classmethod
    @classmethod
    def fromString(cls, logicalDevicesString, physicalDevicesString):
        pass

class LogicalDeviceInfo(object):
    """
    SCSI logical device information

    :param properties: properties
    :type properties: dict
    """
    __metaclass__ = ABCMeta

    def __init__(self, properties=None):
        self.properties = properties or {}
        self.physicalDevices = {}

    @property
    def isSSD(self):
        #  go through associated physical devices
        if all([physicalDevice.isSSD for physicalDevice in self.physicalDevices.values()]):
            return True
        return False

    @abstractproperty
    def name(self):
        pass

class PhysicalDeviceInfo(object):
    """
    SCSI physical device information

    :param properties: properties
    :type properties: dict
    """
    __metaclass__ = ABCMeta

    def __init__(self, properties=None):
        self.properties = properties or {}

    @abstractproperty
    def id(self):
        pass

    @abstractproperty
    def isSSD(self):
        pass

    @abstractproperty
    def serialNumber(self):
        pass
