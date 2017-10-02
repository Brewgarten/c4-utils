"""
Copyright (c) IBM 2015-2017. All Rights Reserved.
Project name: c4-utils
This project is licensed under the MIT License, see LICENSE

Functionality
-------------
"""

import logging
import re

import c4.utils.command
import c4.utils.enum
import c4.utils.jsonutil
import c4.utils.scsi.adaptec
import c4.utils.scsi.lsi

log = logging.getLogger(__name__)

class DiskTypes(c4.utils.enum.Enum):
    """
    Enumeration of disk types
    """
    HDD = "hdd"
    SSD = "ssd"

class BlockDeviceMapping(object):

    INFO_COMMAND = "/bin/ls /sys/bus/scsi/devices/*/block"

    def __init__(self):
        self.devices = {}

    @property
    def deviceNamebyIDMap(self):
        """
        Linux device name by block device id mapping
        """
        return {int(re.search("\d+:\d+:(\d+):\d+", blockDevice).group(1)): name
                for blockDevice, name in self.devices.items()}

    @property
    def IDbyDeviceNameMap(self):
        """
        Block device id by linux device name mapping
        """
        return {name: int(re.search("\d+:\d+:(\d+):\d+", blockDevice).group(1))
                for blockDevice, name in self.devices.items()}

    @classmethod
    def fromString(cls, string):
        """
        Parse the output of ``ls /sys/bus/scsi/devices/*/block``

        :param string: string
        :type string: str
        """
        mapping = BlockDeviceMapping()

        def chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i+n]
        mapping.devices = {re.search("/sys/bus/scsi/devices/(\d+:\d+:\d+:\d+)/block", blockDevice).group(1): name
                           for blockDevice, name in chunks(string.split(), 2)}
        return mapping

class DeviceMap(c4.utils.jsonutil.JSONSerializable):
    """
    A node to device mapping which looks like

    .. code-block:: python

        {
            "nodes": {
                "rack1-data1": {
                    "disks": {
                        "sda": Disk,
                        "sdb": Disk
                    }
                    "name": "rack1-data1"
                }
            }
        }
    """
    def __init__(self):
        self.nodes = {}

    def addDefaultPartitions(self, filesystem="gpfs"):
        """
        Add a default GPFS partition that takes up all the space to
        each disk

        :param filesystem: optional file system name
        :type filesystem: str
        :returns: :class:`DeviceMap`
        """
        for node in self.nodes.values():
            for disk in node.disks.values():
                disk.setPartition(1, Partition(filesystem))
        return self

    def __repr__(self):
        return str(self.__dict__)

class Disk(c4.utils.jsonutil.JSONSerializable):
    """
    A class representing a linux disk which contains partitions

    :param name: name of the disk (e.g., sdb)
    :type name: str
    :param diskType: disk type
    :type diskType: :class:`DiskType`
    :param model: model name
    :type model: str
    """
    def __init__(self, name, diskType, model, nsdList=None, size=0):
        self.name = name
        self.partitions = {}
        if not isinstance(diskType, DiskTypes):
            raise ValueError("'%s' is not an enum of DiskType")
        self.type = diskType
        self.model = model
        self.nsdList = nsdList if nsdList else []
        self.size = size

    def addPartition(self, partition):
        """
        Add partition to the disk

        :param partition: partition
        :type partition: :class:`Partition`
        :returns: :class:`Disk`
        """
        index = len(self.partitions.keys()) + 1
        # TODO: check partition boundaries before adding (or make this an allocation routine)
        self.partitions[index] = partition
        return self

    def setPartition(self, index, partition):
        """
        Set partition to the specified index

        :param index: partition index
        :type index: int
        :param partition: partition
        :type partition: :class:`Partition`
        :returns: :class:`Disk`
        """
        self.partitions[index] = partition
        return self

    def hasSpaceLeft(self):
        """
        Check if there is any space left on the disk,
        meaning the partitions haven't filled up the disk yet

        :returns: True or False
        """
        # check if we have any partitions
        if not self.partitions:
            return True
        # check if the last partition fills up the disk
        totalUsed = 0;
        for index, part in self.partitions.items():
            totalUsed = totalUsed + part.percent

        if totalUsed < 100:
            return True
        else:
            return False

    def __repr__(self):
        return str(self.__dict__)

class Node(c4.utils.jsonutil.JSONSerializable):
    """
    A class representing a node which contains disks

    :param name: name of the node (e.g., rack1-master1)
    :type name: str
    """
    def __init__(self, name):
        self.name = name
        self.disks = {}

    def __repr__(self):
        return str(self.__dict__)

class Partition(c4.utils.jsonutil.JSONSerializable):
    """
    A disk partition

    :param filesystem: name of the file system
    :type filesystem: str
    :param percent: partition size represented in disk percentage (e.g., 25%)
    :type percent: int
    """
    def __init__(self, filesystem, percent=100):
        self.percent = percent
        self.filesystem = filesystem

    def __repr__(self):
        return str(self.__dict__)

def addAdaptecControllerInformation(disks, devicesInfo):
    """
    Add Adaptec SCSI controller information.

    The controller inserts the logical device name into the Linux block
    information as the model name. Hence we are able to match up information
    based on the name of the logical devices.

    :param disks: disks
    :type disks: dict
    :param devicesInfo: Adaptec devices information
    :type: :class:`~c4.utils.scsi.AdaptecDevicesInfoLSILogicalDeviceInfo`
    """
    if not isinstance(devicesInfo, c4.utils.scsi.adaptec.AdaptecDevicesInfo):
        raise ValueError("devices info parameter needs to be of type '{0}'".format(c4.utils.scsi.adaptec.AdaptecDevicesInfo))
    logicalDevicesByName = devicesInfo.controllers[0].logicalDevicesbyNameMap

    for name, disk in disks.items():
        # check if model matches pattern
        if disk.model.startswith("JBOD"):
            # look up logical device
            logicalDevice = logicalDevicesByName[disk.model]
            if logicalDevice.isSSD:
                disks[name].type = DiskTypes.SSD

def addLSIControllerInformation(disks, devicesInfo, blockDeviceMapping):
    """
    Add LSI SCSI controller information.

    The controller sets the model of devices to something like ``MR9361-8i``.

    Here we match up the logical device id with the scsi bus id in Linux
    in order to retrieve additional information and replace the model name
    with the logical device name

    :param disks: disks
    :type disks: dict
    :param devicesInfo: Adaptec devices information
    :type: :class:`~c4.utils.scsi.AdaptecDevicesInfoLSILogicalDeviceInfo`
    """
    if not isinstance(devicesInfo, c4.utils.scsi.lsi.LSIDevicesInfo):
        raise ValueError("devices info parameter needs to be of type '{0}'".format(c4.utils.scsi.lsi.LSIDevicesInfo))
    if not isinstance(blockDeviceMapping, BlockDeviceMapping):
        raise ValueError("block device mapping parameter needs to be of type '{0}'".format(BlockDeviceMapping))
    blockDeviceIdByDeviceName = blockDeviceMapping.IDbyDeviceNameMap
    logicalDevicesByBlockDeviceId = devicesInfo.controllers[0].logicalDevices

    for name, disk in disks.items():
        # check if model matches pattern
        if disk.model.startswith("MR"):
            # look up logical device
            blockDeviceId = blockDeviceIdByDeviceName[name]
            logicalDevice = logicalDevicesByBlockDeviceId[blockDeviceId]
            # replace model with logical device name (just like Adaptec does it)
            disks[name].model = logicalDevice.name
            if logicalDevice.isSSD:
                disks[name].type = DiskTypes.SSD

def getAvailableDisks(lsblkOutput, includePartitions=False):
    """
    Get available disk information

    :param lsblkOutput: output of ``lsblk --ascii --bytes --noheadings --output name,type,size,rota,mountpoint,fstype,model``
    :type lsblkOutput: str
    :param includePartitions: include the partitions as part of getting the disks.
    :type includePartitions: boolean
    """
    disks = {}
    lines = lsblkOutput.splitlines()
    currentDevice = None
    for line in lines:
        try:
            line = line.strip().split('"')
            diskInfo  = { line[i].strip(" ="):line[i+1] for i in range(0, len(line), 2) if i + 1 < len(line) }
            name, deviceType, size = diskInfo['NAME'], diskInfo['TYPE'], diskInfo['SIZE']
        except:
            log.info("Unable to parse %s", line)
            continue

        if deviceType == "disk":

            # make sure device is at least ~10MB
            if int(size) > 10000000:

                # detect virtual disks
                if name.startswith("xvd") or name.startswith("vd"):
                    disks[name] = Disk(name, DiskTypes.HDD, "virtual", size=size)
                else:
                    rotational = int(diskInfo["ROTA"])
                    model = diskInfo["MODEL"]
                    if rotational == 0:
                        disks[name] = Disk(name, DiskTypes.SSD, model, size=size)
                    else:
                        disks[name] = Disk(name, DiskTypes.HDD, model, size=size)
                currentDevice = name

        elif deviceType == "part":
            if includePartitions:
                try:
                    deviceName = re.search(r'([a-z]+)', name).group(1)
                except Exception as exception:
                    deviceName = "unknown"
                    log.error(exception)

                if deviceName in disks:
                    if name not in disks[deviceName].partitions:
                        disks[deviceName].partitions[name] = size

            if currentDevice is not None:

                # check if a mount point and file system exists
                if "MOUNTPOINT" in diskInfo and diskInfo["MOUNTPOINT"]:
                    mountpoint = diskInfo["MOUNTPOINT"]
                    if mountpoint in ("/", "/boot", "[SWAP]"):
                        log.debug("ignoring '%s' because existing partition '%s' has mountpoint '%s'",
                                  currentDevice, name[2:], mountpoint)
                        del disks[currentDevice]
                        currentDevice = None
                    else:
                        log.warn("'%s' has existing partition '%s' with mountpoint '%s' that will be repartitioned",
                                  currentDevice, name[2:], mountpoint)

        else:
            log.debug("ignoring '%s' because is has type '%s'", name, deviceType)

    return disks


def getAvailableDevices(nodes, user="root", includePartitions=False):
    """
    Get available devices for the specified nodes.

    .. code-block:: python

        nodes = ['rack1-master1','rack1-data1']
        devices = getAvailableDevices(nodes)

    .. note::

        Only those devices that are not formatted or mounted will be selected

    Where `devices` yields something like

    .. code-block:: python

        {
            "nodes": {
                "rack1-data1": {
                    "disks": {
                        "sda": Disk,
                        "sdb": Disk
                    }
                    "name": "rack1-data1"
                }
            }
        }

    :param nodes: nodes
    :type nodes: [str]
    :param user: user name to use for the discovery
    :type user: str
    :param includePartitions: include partition mapping when getting disks.
    :type includePartitions: boolean
    :returns: :class:`DeviceMap`
    """
    devices = DeviceMap()
    for nodeName in nodes:
        response = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName), "COLUMNS=100 lsblk --ascii --bytes --noheadings -P --output name,type,size,rota,mountpoint,fstype,model"],
                            "Could not determine available devices on {node} as {user}".format(node=nodeName, user=user))
        node = Node(nodeName)
        node.disks = getAvailableDisks(response, includePartitions=includePartitions)

        # check if any devices have been abstracted as JBODs through a SCSI controller
        if any([disk.model.startswith("MR") for disk in node.disks.values()]):

            log.info("Adding MegaRAID SCSI information")
            try:
                logicalDevicesString = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName),
                                                                       c4.utils.scsi.lsi.LSIDevicesInfo.LOGICAL_DEVICES_INFO_COMMAND],
                                "Could not determine available logical devices on {node} as {user}".format(node=nodeName, user=user))
                physicalDevicesString = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName),
                                                                        c4.utils.scsi.lsi.LSIDevicesInfo.PHYSICAL_DEVICES_INFO_COMMAND],
                                    "Could not determine available physical devices on {node} as {user}".format(node=nodeName, user=user))
                devicesInfo = c4.utils.scsi.lsi.LSIDevicesInfo.fromString(logicalDevicesString, physicalDevicesString)

                blockDeviceMappingString = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName), BlockDeviceMapping.INFO_COMMAND],
                                "Could not determine block device mappings on {node} as {user}".format(node=nodeName, user=user))
                blockDeviceMapping = BlockDeviceMapping.fromString(blockDeviceMappingString)

                addLSIControllerInformation(node.disks, devicesInfo, blockDeviceMapping)
            except Exception as e:
                log.exception(e)

        elif any([disk.model.startswith("JBOD") for disk in node.disks.values()]):
            # note that this is for Adaptec controllers only

            log.info("Adding Adaptec SCSI information")
            try:
                logicalDevicesString = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName),
                                                                       c4.utils.scsi.adaptec.AdaptecDevicesInfo.LOGICAL_DEVICES_INFO_COMMAND],
                                "Could not determine available logical devices on {node} as {user}".format(node=nodeName, user=user))
                physicalDevicesString = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName),
                                                                        c4.utils.scsi.adaptec.AdaptecDevicesInfo.PHYSICAL_DEVICES_INFO_COMMAND],
                                    "Could not determine available physical devices on {node} as {user}".format(node=nodeName, user=user))
                devicesInfo = c4.utils.scsi.adaptec.AdaptecDevicesInfo.fromString(logicalDevicesString, physicalDevicesString)

                addAdaptecControllerInformation(node.disks, devicesInfo)
            except Exception as e:
                log.exception(e)

        devices.nodes[nodeName] = node

    log.debug("available devices: %s", devices.toJSON(includeClassInfo=True, pretty=True))
    return devices

def partitionDevices(devices, user="root"):
    """
    Partition specified devices accordingly

    :param devices: node to disk mapping
    :type devices: :class:`DeviceMap`
    :param user: user name to use for the partitioning
    :type user: str
    """
    #TODO: change to parallel
    for nodeName, node in sorted(devices.nodes.items()):

        for diskName, disk in sorted(node.disks.items()):

            # detect partitions with existing mountpoints
            mountPointsCommand = ["ssh", "{0}@{1}".format(user, nodeName), "lsblk --ascii --noheadings --output mountpoint /dev/{0}".format(diskName)]
            mountPoints = c4.utils.command.execute(mountPointsCommand, "Could not determine mountpoints for '{0}'".format(diskName))
            if mountPoints:
                for mountPoint in mountPoints.splitlines():
                    if mountPoint:
                        unmountCommand = ["ssh", "{0}@{1}".format(user, nodeName), "umount -f {0}".format(mountPoint)]
                        c4.utils.command.execute(unmountCommand, "Could not unmount '{0}'".format(mountPoint))
                        removefstabCommand = ["ssh", "{0}@{1}".format(user, nodeName), "sed --in-place 's|.*\s{0}\s.*||' /etc/fstab".format(mountPoint)]
                        c4.utils.command.execute(removefstabCommand, "Could not remove fstab entry for '{0}'".format(mountPoint))
                        removeMountPointCommand = ["ssh", "{0}@{1}".format(user, nodeName), "/bin/rmdir {0}".format(mountPoint)]
                        c4.utils.command.execute(removeMountPointCommand, "Could not remove mount point '{0}'".format(mountPoint))



            # create disk label
            createPartitionTableCommand = ["ssh", "{0}@{1}".format(user, nodeName), "parted -s /dev/{0} mklabel gpt".format(diskName)]
            c4.utils.command.execute(createPartitionTableCommand, "Could not partition '{0}'".format(diskName))


            # create partitions
            start = 0
            for partitionIndex, partition in sorted(disk.partitions.items()):
                end = start + partition.percent
                createPartitionCommand = ["ssh", "{0}@{1}".format(user, nodeName),
                                          "parted -s -a optimal /dev/{0} mkpart primary {1}% {2}%".format(diskName, start, end)]
                c4.utils.command.execute(createPartitionCommand, "Could not create partition {0}{1}".format(diskName, partitionIndex))
                start = end
