"""
Copyright (c) IBM 2015-2017. All Rights Reserved.
Project name: c4-utils
This project is licensed under the MIT License, see LICENSE
"""
import json
import logging
import re

import c4.utils.scsi.base

log = logging.getLogger(__name__)

class LSIDevicesInfo(c4.utils.scsi.base.DevicesInfo):
    """
    LSI MegaRaid controller devices information
    """
    LOGICAL_DEVICES_INFO_COMMAND = "/opt/MegaRAID/storcli/storcli64 /call/vall show all J"
    PHYSICAL_DEVICES_INFO_COMMAND = "/opt/MegaRAID/storcli/storcli64 /call/eall/sall show all J"

    def __init__(self):
        super(LSIDevicesInfo, self).__init__()

    @classmethod
    def fromString(cls, logicalDevicesString, physicalDevicesString):
        """
        Parse the output of ``/opt/MegaRAID/storcli/storcli64 /call/vall show all J``
        and ``/opt/MegaRAID/storcli/storcli64 /call/eall/sall show all J``

        :param logicalDevicesString: logical devices string
        :type logicalDevicesString: str
        :param physicalDevicesString: physical devices string
        :type physicalDevicesString: str
        :returns: Adaptec devices information
        :rtype: :class:`LSIDevicesInfo`
        """
        info = LSIDevicesInfo()

        # for now only use one controller
        controllerInfo = c4.utils.scsi.base.ControllerInfo(0)

        controllerInfo.physicalDevices = cls.parsePhysicalDevicesString(physicalDevicesString)
        controllerInfo.logicalDevices = cls.parseLogicalDevicesString(logicalDevicesString)

        physicalDevicesByIdMap = controllerInfo.physicalDevicesbyIdMap

        for logicalDevice in controllerInfo.logicalDevices.values():
            for deviceId in logicalDevice.physicalDevices.keys():
                logicalDevice.physicalDevices[deviceId] = physicalDevicesByIdMap[deviceId]

        info.controllers[controllerInfo.controller] = controllerInfo

        return info

    @classmethod
    def parseLogicalDevicesString(cls, logicalDevicesString):
        """
        Parse the output of ``/opt/MegaRAID/storcli/storcli64 /call/vall show all J``

        :param logicalDevicesString: logical devices string
        :type logicalDevicesString: str
        :returns: logical device id to :class:`LSILogicalDeviceInfo` mapping
        :rtype: dict
        """
        controllers = {}
        for controller in json.loads(logicalDevicesString).get("Controllers", []):
            if controller["Command Status"]["Status"] == "Success":

                deviceInfos = controller["Response Data"]

                # get logical device information
                logicalDevices = {int(re.search("/c\d+/v(\d+)", key).group(1)): LSILogicalDeviceInfo(value[0])
                                            for key, value in deviceInfos.items()
                                            if re.search("/c\d+/v\d+", key)}

                for logicalDeviceNumber in logicalDevices.keys():
                    # update properties with additional information
                    logicalDevices[logicalDeviceNumber].properties.update(
                        deviceInfos["VD{logicalDeviceNumber} Properties".format(logicalDeviceNumber=logicalDeviceNumber)])

                    # add physical device mappings
                    physicalDeviceMappings = deviceInfos["PDs for VD {logicalDeviceNumber}".format(logicalDeviceNumber=logicalDeviceNumber)]
                    for physicalDeviceProperties in physicalDeviceMappings:
                        physicalDeviceID = physicalDeviceProperties["DID"]
                        logicalDevices[logicalDeviceNumber].physicalDevices[physicalDeviceID] = None

                # add logical devices information to controller
                controllers[controller["Command Status"]["Controller"]] = logicalDevices
            else:
                log.error("Could not parse controller information '%s'", controller["Command Status"])

        allLogicalDevices = {}
        for logicalDevices in controllers.values():
            allLogicalDevices.update(logicalDevices)
        return logicalDevices

    @classmethod
    def parsePhysicalDevicesString(cls, physicalDevicesString):
        """
        Parse the output of ``/opt/MegaRAID/storcli/storcli64 /call/eall/sall show all J``

        :param physicalDevicesString: physical devices string
        :type physicalDevicesString: str
        :returns: serial number to :class:`LSIPhysicalDeviceInfo` mapping
        :rtype: dict
        """
        controllers = {}
        for controller in json.loads(physicalDevicesString).get("Controllers", []):
            if controller["Command Status"]["Status"] == "Success":

                deviceInfos = controller["Response Data"]

                # get physical device information
                physicalDevices = {re.search(r"Drive /c\d+/(e\d+/s\d+)$", key).group(1): LSIPhysicalDeviceInfo(value[0])
                                   for key, value in deviceInfos.items()
                                   if re.search(r"Drive /c\d+/(e\d+/s\d+)$", key)}

                for physicalDevicePosition in physicalDevices.keys():
                    # update properties with additional information
                    detailedPhysicalDeviceInformation = deviceInfos["Drive /c0/{physicalDevicePosition} - Detailed Information".format(physicalDevicePosition=physicalDevicePosition)]

                    for detailKey, detailValue in detailedPhysicalDeviceInformation.items():
                        if detailKey != "Inquiry Data":
                            physicalDevices[physicalDevicePosition].properties.update(detailValue)

                # add physical devices information to controller
                controllers[controller["Command Status"]["Controller"]] = physicalDevices
            else:
                log.error("Could not parse controller information '%s'", controller["Command Status"])

        allPhysicalDevices = {}
        for physicalDevices in controllers.values():
            allPhysicalDevices.update({device.serialNumber: device
                                       for device in physicalDevices.values()})
        return allPhysicalDevices

class LSILogicalDeviceInfo(c4.utils.scsi.base.LogicalDeviceInfo):
    """
    LSI MegaRaid logical device information

    :param properties: properties
    :type properties: dict
    """
    def __init__(self, properties=None):
        super(LSILogicalDeviceInfo, self).__init__(properties=properties)

    @property
    def name(self):
        return self.properties["Name"]

class LSIPhysicalDeviceInfo(c4.utils.scsi.base.PhysicalDeviceInfo):
    """
    LSI MegaRaid physical device information

    :param properties: properties
    :type properties: dict
    """
    def __init__(self, properties=None):
        super(LSIPhysicalDeviceInfo, self).__init__(properties=properties)

    @property
    def id(self):
        return self.properties["DID"]

    @property
    def isSSD(self):
        if self.properties["Med"] == "SSD":
            return True
        return False

    @property
    def serialNumber(self):
        return self.properties["SN"]
