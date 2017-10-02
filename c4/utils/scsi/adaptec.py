"""
Copyright (c) IBM 2015-2017. All Rights Reserved.
Project name: c4-utils
This project is licensed under the MIT License, see LICENSE
"""
import logging
import re

import c4.utils.scsi.base

log = logging.getLogger(__name__)

class AdaptecDevicesInfo(c4.utils.scsi.base.DevicesInfo):
    """
    Adaptec controller devices information
    """
    LOGICAL_DEVICES_INFO_COMMAND = "/usr/Adaptec_Event_Monitor/arcconf getconfig 1 ld"
    PHYSICAL_DEVICES_INFO_COMMAND = "/usr/Adaptec_Event_Monitor/arcconf getconfig 1 pd"

    def __init__(self):
        super(AdaptecDevicesInfo, self).__init__()

    @classmethod
    def fromString(cls, logicalDevicesString, physicalDevicesString):
        """
        Parse the output of ``arcconf getconfig 1 ld`` and ``arcconf getconfig 1 pd``

        :param logicalDevicesString: logical devices string
        :type logicalDevicesString: str
        :param physicalDevicesString: physical devices string
        :type physicalDevicesString: str
        :returns: Adaptec devices information
        :rtype: :class:`AdaptecDevicesInfo`
        """
        info = AdaptecDevicesInfo()

        controllers = int(re.search("Controllers found:\s+(\d+)", logicalDevicesString).group(1))

        if controllers == 0:
            return info

        # for now only use one controller
        controllerInfo = c4.utils.scsi.base.ControllerInfo(0)

        controllerInfo.physicalDevices = cls.parsePhysicalDevicesString(physicalDevicesString)
        controllerInfo.logicalDevices = cls.parseLogicalDevicesString(logicalDevicesString)

        for logicalDevice in controllerInfo.logicalDevices.values():
            for serialNumber in logicalDevice.physicalDevices.keys():
                logicalDevice.physicalDevices[serialNumber] = controllerInfo.physicalDevices[serialNumber]

        info.controllers[controllerInfo.controller] = controllerInfo

        return info

    @classmethod
    def parseLogicalDevicesString(cls, logicalDevicesString):
        """
        Parse the output of ``arcconf getconfig 1 ld``

        :param logicalDevicesString: logical devices string
        :type logicalDevicesString: str
        :returns: logical device id to :class:`AdaptecLogicalDeviceInfo` mapping
        :rtype: dict
        """
        logicalDevices = {}

        # go through device information
        currentDeviceNumber = None
        for line in logicalDevicesString.splitlines():

            logicalDeviceNumber = re.search("(Logical device number)\s+(\d+)", line)
            if logicalDeviceNumber is not None:
                currentDeviceNumber = int(logicalDeviceNumber.group(2))
                logicalDevices[currentDeviceNumber] = AdaptecLogicalDeviceInfo({
                    logicalDeviceNumber.group(1): currentDeviceNumber
                })

            elif currentDeviceNumber is not None:
                # go through attributes
                attributeInfoLine = line.strip()

                if (not attributeInfoLine or
                        attributeInfoLine.startswith("------") or
                        attributeInfoLine.startswith("Logical device segment information") or
                        attributeInfoLine.startswith("Command completed")):
                    # ignore these lines
                    pass
                elif attributeInfoLine.startswith("Segment "):

                    # logical to physical mapping
                    serialNumber = re.search("\(Controller:\d+,Enclosure:\d+,Slot:\d+\)\s+(\S+)", line).group(1)
                    logicalDevices[currentDeviceNumber].physicalDevices[serialNumber] = None

                else:
                    # add attributes and their values
                    attribute, value = attributeInfoLine.split(" : ")
                    logicalDevices[currentDeviceNumber].properties[attribute.strip()] = value.strip()

        return logicalDevices

    @classmethod
    def parsePhysicalDevicesString(cls, physicalDevicesString):
        """
        Parse the output of ``arcconf getconfig 1 pd``

        :param physicalDevicesString: physical devices string
        :type physicalDevicesString: str
        :returns: serial number to :class:`AdaptecPhysicalDeviceInfo` mapping
        :rtype: dict
        """
        physicalDevices = {}

        # go through device information
        currentDeviceNumber = None
        for line in physicalDevicesString.splitlines():

            line = line.strip()
            deviceNumber = re.search("(Device #)(\d+)", line)
            if deviceNumber is not None:
                currentDeviceNumber = int(deviceNumber.group(2))
                physicalDevices[currentDeviceNumber] = AdaptecPhysicalDeviceInfo({
                    deviceNumber.group(1): currentDeviceNumber
                })

            elif currentDeviceNumber is not None:
                # go through attributes
                attributeInfoLine = line.strip()

                if (not attributeInfoLine or
                        attributeInfoLine.startswith("------") or
                        attributeInfoLine.startswith("Command completed")):
                    # ignore these lines
                    pass
                elif attributeInfoLine.startswith("Device is a"):

                    if attributeInfoLine == "Device is an Enclosure services device":
                        log.debug("Removing non-hard disk device '%s'", currentDeviceNumber)
                        del physicalDevices[currentDeviceNumber]
                        currentDeviceNumber = None
                    elif attributeInfoLine == "Device is a Hard drive":
                        log.debug("found hard drive device '%s'", currentDeviceNumber)

                else:
                    # add attributes and their values
                    attribute, value = attributeInfoLine.split(" : ")
                    # FIXME: use information from Reported Channel,Device(T:L)       : 0,0(0:0) as id
                    physicalDevices[currentDeviceNumber].properties[attribute.strip()] = value.strip()

        return {device.serialNumber: device
                for device in physicalDevices.values()}

class AdaptecLogicalDeviceInfo(c4.utils.scsi.base.LogicalDeviceInfo):
    """
    Adaptec logical device information

    :param properties: properties
    :type properties: dict
    """
    def __init__(self, properties=None):
        super(AdaptecLogicalDeviceInfo, self).__init__(properties=properties)

    @property
    def name(self):
        return self.properties["Logical device name"]

class AdaptecPhysicalDeviceInfo(c4.utils.scsi.base.PhysicalDeviceInfo):
    """
    Adaptec physical device information

    :param properties: properties
    :type properties: dict
    """
    def __init__(self, properties=None):
        super(AdaptecPhysicalDeviceInfo, self).__init__(properties=properties)

    @property
    def id(self):
        return self.properties["Serial number"]

    @property
    def isSSD(self):
        if self.properties["SSD"] == "Yes":
            return True
        return False

    @property
    def serialNumber(self):
        return self.properties["Serial number"]
