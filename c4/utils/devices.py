
'''
*******************************************************
(C) Copyright IBM Corp. 2015-2016. All rights reserved.
*******************************************************
'''

"""
Functionality
-------------
"""

import logging
import re
import os
import stat
import time

import c4.utils.command
import c4.utils.enum
import c4.utils.jsonutil
import c4.utils.scsi.adaptec
import c4.utils.scsi.lsi

log = logging.getLogger(__name__)

class DiskFailureException (Exception):
    def __init__(self, message ):
        super(DiskFailureException, self).__init__(message)

class DiskTypes(c4.utils.enum.Enum):
    """
    Enumeration of disk types
    """
    HDD = "hdd"
    SSD = "ssd"

class PartitionTypes(c4.utils.enum.Enum):
    """
    Enumeration of disk types
    """
    Primary = "primary"
    Extended = "extended"

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
    def __init__(self, name, diskType, model, location=0, sn=None, nsdList=None, size=None):
        self.name = name
        self.partitions = {}
        if diskType and not isinstance(diskType, DiskTypes):
            raise ValueError("'%s' is not an enum of DiskType")
        self.type = diskType
        self.model = model
        self.location = location
        self.sn = sn
        self.size = size if size else 0
        self.nsdList = nsdList if nsdList else []

    def getLocation(self):
        return self.location

    def getSerialNum(self):
        return self.sn

    def getSize(self):
        return self.size

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
    def __init__(self, name, rackLocation=0, nodeLocation=0):
        self.name = name
        self.disks = {}
        self.rackLocation = rackLocation
        self.nodeLocation = nodeLocation
        self.osDisks = []

    def setRackLocation(self, rackLocation):
        self.rackLocation = rackLocation

    def getRackLocation(self):
        return self.rackLocation

    def getNodeLocation(self):
        return self.nodeLocation

    def setNodeLocation(self, nodeLocation):
        self.nodeLocation = nodeLocation

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
    def __init__(self, filesystem, percent=100, partitionNum=0):
        self.percent = percent
        self.filesystem = filesystem
        self.partitionNum = partitionNum

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
            disks[name].location = blockDeviceId

def getAvailableDisks(lsblkOutput, ignoreOSDisks=True, includePartitions=False):
    """
    Get available disk information

    :param lsblkOutput: output of ``lsblk --ascii --bytes --noheadings --output name,type,size,rota,mountpoint,fstype,model``
    :type lsblkOutput: str
    :param ignoreOSDisks: ignore disks that are part of the os.
    :type ignoreOSDisks: boolean
    :param includePartitions: include the partitions as part of getting the disks.
    :type includePartitions: boolean
    :returns: Dictionary of disks.
    :retype: { :class:`Disk` }
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
            log.warn("Unable to parse %s", line)
            continue

        if deviceType == "disk":

            # make sure device is at least ~10MB
            if int(size) > 10000000:
                # detect virtual disks
                if name.startswith("xvd") or name.startswith("vd"):
                    disks[name] = Disk(name, DiskTypes.HDD, "virtual", size)
                else:
                    rotational = int(diskInfo[3])
                    model = diskInfo[4]
                    if rotational == 0:
                        disks[name] = Disk(name, DiskTypes.SSD, model, size)
                    else:
                        disks[name] = Disk(name, DiskTypes.HDD, model, size)

                currentDevice = name

        elif deviceType == "part":
            if includePartitions:
                try:
                    deviceName = re.match(r'([a-z]+)', name).group(1)
                except Exceptions as exception:
                    deviceName = "unknown"
                    log.error(exception)

                if deviceName in disks:
                    if name not in disks[deviceName].partitions:
                        disks[deviceName].partitions[name] = size

            if currentDevice is not None:

                # check if a mount point and file system exists
                if "MOUNTPOINT" in diskInfo and diskInfo["MOUNTPOINT"]:
                    mountpoint = diskInfo["MOUNTPOINT"]
                    if mountpoint in ("/", "/boot", "[SWAP]") and ignoreOSDisks:
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

def getOSDisks(lsBlkOutput):

    """
    Figure out OS disks from lBlkOutput

    :param lsBlkOutput: output of ``lsblk --ascii --bytes --noheadings --output name,type,size,rota,mountpoint,fstype,model``
    :type lsBlkOutput: str
    :returns: : osDisks[]
    """

    osDisks = []
    lines = lsBlkOutput.splitlines()
    for line in lines:
        deviceInfo = line.split()
        name, type = deviceInfo[:2]
        if type == "part":
            if (len(deviceInfo) > 4 and deviceInfo[4] in ("/", "/boot", "[SWAP]")):
                found=re.search('(.*)([0-9])',name[2:])
                if found:
                    diskname = found.group(1)
                    osDisks.append(diskname)

    log.debug("OS disks found %s", osDisks)
    return osDisks

def getAvailableDevices(nodes, user="root", ignoreOSDisks=True, includePartitions=False):
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
    :param ignoreOSDisks: ignore disks that are part of the OS.
    :type ignoreOSDisks: boolean
    :param includePartitions: include partition mapping when getting disks.
    :type includePartitions: boolean
    :returns: :class:`DeviceMap`
    """
    devices = DeviceMap()
    for nodeName in nodes:
        response = c4.utils.command.execute(["ssh", "{0}@{1}".format(user, nodeName), "COLUMNS=100 lsblk --ascii --bytes --noheadings -P --output name,type,size,rota,mountpoint,fstype,model"],
                            "Could not determine available devices on {node} as {user}".format(node=nodeName, user=user))
        node = Node(nodeName)
        node.disks = getAvailableDisks(response, ignoreOSDisks=ignoreOSDisks, includePartitions=includePartitions)
        node.osDisks = getOSDisks(response)

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

def getDiskPartitions(device, getFreeSpace=False, logErrors=True, i=1, maxi=3, unit='%', checkType=True, newSystem= True):
    """
    $ sudo parted -s -m  /dev/sdi print
    BYT;
    /dev/sdi:1200GB:scsi:512:512:gpt:IBM ST1200MM0007;
    1:24.6kB:1200GB:1200GB::GPFS::hidden;

    :param: checkType: Check partition type. Used to avoid error in case of RAID or LVM array.
    :type: checkType: bool
    :param: newSystem: Just to see if it is apinit (newsystem)
    :type: newSystem: bool
    :returns: {'number': '1', 'start': '2324', 'end' : '243465', 'size': '2334462'}]
    :rtype: list
     """
    if i > maxi:
        raise DiskFailureException('Disk [ {0} ] Failure:Cannot retrieve partition information after {1} times.'.format(device, maxi))

    volumeGroupMatch = re.match(r"/dev/VolGroup-(?P<group>.*)", device)
    if volumeGroupMatch:
        device = os.path.join("/dev", "VolGroup", volumeGroupMatch.group("group"))
    if not re.match(r"/dev/VolGroup.*", device) and not isBlockDevice(device):
        raise ValueError(device)

    command = ['/sbin/parted', '-sm', device, 'unit', unit]
    command.append('print')
    if getFreeSpace:
        command.append('free')

    output = c4.utils.command.execute(command, user='root', raiseOnExitStatus=False)
    if output.rc:
        # This error means the partition table is not present on the disk.
        # As the disk is not a system disk we should create it.
        unrecognizedLabelErr = 'unrecognised disk label'
        if unrecognizedLabelErr in output or unrecognizedLabelErr in output.error:
            if newSystem:
                createPartitionTable(device)
            return getDiskPartitions(device, getFreeSpace, logErrors, i+1, newSystem= newSystem)
        else:
            logFunc = log.error if logErrors else log.debug
            logFunc("Could not retrieve partition information: %s " % output.error)
            return None

    lines = output.splitlines()
    partitions = []
    start_marker_found = False
    for index, line in enumerate(lines):
        if not start_marker_found:
            if line == 'BYT;':
                start_marker_found = True
            continue
        if line.startswith(device + ':'):
            (phy_sec_size, loc_sec_size, ptt) = line.split(':')[3:6]
        if re.match(r'^\d+:.*;$', line):
            names = ['number', 'start', 'end', 'size', 'file system', 'name', 'Flags']
            values = line[:-1].split(':')
            # in case we have : inside name of filesystem e.g. GPFS:
            if len(values) > 7:
                    values[5:7] = [':'.join(values[5:7])]
            partition = dict(zip(names, values))
            # Remove the unit from start, end and size
            partition['start'] = float(re.sub(r'[^0-9.]','',partition['start']))
            partition['end'] = float(re.sub(r'[^0-9.]','',partition['end']))
            partition['size'] = float(re.sub(r'[^0-9.]','',partition['size']))

            # Parted is setting the number to 1 for free space which is misleading
            if partition['file system'] == 'free':
                partition['number'] = None

            partition['device'] = device + partition['number'] if partition['number'] is not None else None
            partition['index'] = index

            if checkType and partition['number']:
                '''
                As parted is calling partprobe eventhough we just read the partition table,
                /proc/partitions might not be refresh and the partition cannot found despite the
                fact it is there. Waiting a short amount of time should solve the problem.
                '''
                for i in xrange(maxi):
                    type = getPartitionType(device, partition['number'], True if i == maxi-1 else False)
                    if type is None:
                        import time
                        time.sleep(0.5)
                if type is not None:
                    partition['Type'] = type

            partitions.append(partition)

    return partitions

def getPartitionType(device, number, logErrors=True):
    """
    The type (primary / extended) is not available in the machine-readable mode of
    parted. It is faster and easier to read from /proc/partitions than to parse
    the normal parted output.

    Remark: by convention the blocks for extended is set to 1 in /proc/partitions

    :returns: type of the partition
    :rtype: PartitionTypes
     """
    logFunc = log.error if logErrors else log.debug
    try:
        deviceName = device.split('/')[2]
        # major     minor    #blocks  name
        #    8        2          1    sda2
        command = ['/bin/cat', '/proc/partitions']
        def getOutput():
            output = c4.utils.command.execute(command, "Could not execute cat command")
            lines = output.splitlines()
            output = None
            for line in lines:
                if deviceName+str(number) in line:
                    output = line
                    break
            if output is None:
                logFunc("Partition %s not found on %s device." % (number,deviceName))
            return output
        output = None
        for i in xrange(0, 10):
            output = getOutput()
            if output:
                break
            logFunc("Retrying.")
            time.sleep(1)
        output = ' '.join(output.split()).split()
        if int(output[2]) == 1:
            return PartitionTypes.Extended
        else:
            return PartitionTypes.Primary
    except (c4.utils.command.CommandException, Exception) as e:
        logFunc("Cannot access the partition: %s " % e)
        return None

def getDiskSize(device):
    """
    Remark: Lengths and sizes are expressed in sectors.

    :returns: size of the disk
    :rtype: integer
     """
    if not isBlockDevice("/dev/{0}".format(device)):
        raise ValueError(device)

    filePath = "/sys/block/{0}/size".format(device)

    size = None
    try:
        size = open(filePath).read().rstrip('\n').strip()
    except Exception as e:
        log.error("Error while getting number of sectors: %s ", e)
    return size

def isBlockDevice(file):
    """
    Test if a given file is a block device.

    :param file: file to test
    :type file: str
    :returns: True if file is a block device
    """
    try:
        mode = os.lstat(file).st_mode
    except OSError:
        return False
    else:
        return stat.S_ISBLK(mode)

def diskType(deviceFile):
    """
    Determine the type of a given disk device file.

    :param deviceFile
    :type file: str
    :return Disk type (SDD or HDD)
    :type DiskTypes
    """
    command = ["/bin/lsblk", "-dnr", "-o", "ROTA", deviceFile]
    rotational = c4.utils.command.execute(command, "Could not determine the type of the disk: {0}".format(deviceFile),  user='root')
    if rotational == "0":
        return DiskTypes.SSD
    else:
        return DiskTypes.HDD

def deletePartitions(deviceFile, numbers):
    """
    Delete a partition

    :param deviceFile: valid block device
    :type file: str
    :param number: number of the partition to be deleted
    :type file: str or number
    """
    command = ["/sbin/parted", "-s", deviceFile]
    for number in numbers:
        command.append["rm",  str(number)]
    c4.utils.command.execute(command, "Could not delete partition %s" % deviceFile+str(number),  user='root')
# TODO: Create an unified Parted API
def deletePartition(deviceFile, number):
    """
    Delete a partition

    :param deviceFile: valid block device
    :type file: str
    :param number: number of the partition to be deleted
    :type file: str or number
    """
    command = ["/sbin/parted", "-s", deviceFile, "rm",  str(number)]
    c4.utils.command.execute(command, "Could not delete partition %s" % deviceFile+str(number),  user='root')

def createPartitionTable(deviceFile, type='gpt'):
    """
    Create a new partition table

    :param deviceFile: valid block device
    :type file: str
    :param number: number of the partition to be deleted
    :type file: str or number
    """

    command = ['/sbin/parted', '-s', deviceFile, 'mklabel', type]
    try:
        c4.utils.command.execute(command, "Could not partition %s" % deviceFile, user='root')
    except Exception as e:
        log.warning(e)
        '''
            Temporary workaround because creating a partition table always return an error:
            Error: Partition(s) 1 on /dev/sda have been written, but we have been unable
            to inform the kernel of the change, probably because it/they are in use.
            As a result, the old partition(s) will remain in use.  You should reboot now before making further changes.
        '''
def createPartition(deviceFile, start, end, unit='%', geometry='optimal', partType='primary'):
    """
    Create a new partition

    :param deviceFile: valid block device
    :type file: str
    :param number: number of the partition to be deleted
    :type file: str or number
    """
    command = ["/sbin/parted", "-s", "-a", geometry, deviceFile, "unit", unit, "mkpart", partType, "%s %s" %
                               (str(start), str(end))]
    c4.utils.command.execute(command, "Could not create partition on %s" % deviceFile,  user='root')

def createPartitions(deviceFile, start_end, unit='%', geometry='optimal', partName='DEFAULT'):
    """
    Create a new partition

    :param deviceFile: valid block device
    :type file: str
    :param number: number of the partition to be deleted
    :type file: str or number
    """
    command = ["/sbin/parted", "-s", "-a", geometry, deviceFile, "unit", unit]

    default = False
    if partName == 'DEFAULT':
        default = True
        basePartName = 'primary-'+os.path.basename(deviceFile)

    for idx, (start,end) in enumerate(start_end):
        if default:
            partName = ''.join([basePartName,str(idx+1)])
        command += ["mkpart", partName, "%s %s" %(str(start), str(end))]

    # note that we should ignore any warnings like
    # Warning: WARNING: the kernel failed to re-read the partition table on /dev/vdb (Device or resource busy).  As a result, it may not reflect all of your changes until after reboot.
    # because they cause the exit code to be non-zero
    result = c4.utils.command.execute(command, "Could not create partition on %s" % deviceFile,  user='root', raiseOnExitStatus=False)
    if result.rc:
        log.warn("Could not create partition on '%s' because '%s'", deviceFile, result)

def refreshPartitionTable(devices):
    """
    Inform the kernel that the partition table has changed.

    :param devices: List of devices to inform the kernel
    :type devices: list
    """
    command = ["/sbin/partprobe"] + devices
    c4.utils.command.execute(command, "Could not refresh partition table for devices: {0}".format(devices),  user='root')

def GPFSMountPointsInUse():
    """
    Return the list of GPFS mount points still in use:
        /dev/head on /head type gpfs (rw,atime=1,dev=head,mtime)
    """
    output = c4.utils.command.execute(["/bin/mount"], user="root", raiseOnExitStatus=False)
    output = output.splitlines()
    output = [line for line in output if 'type gpfs' in line]
    mpoints = {}
    for line in output:
        l = line.split()
        mpoints[l[0]] = l[2]

    return mpoints

def isVirtualMachine():
    '''
    Define if the machine is virtual by reading the disk models and comparing to a predefined list of VM disk names
    '''
    VMDiskModels = ["HARDDISK", "VMware Virtual", "QEMU HARDDISK", "Virtual disk", "VBOX HARDDISK"]
    try:
        output = c4.utils.command.execute(["lsblk", "--ascii", "--bytes", "--noheadings", "--output", "name,type,size,rota,mountpoint,fstype,model", "-P"])
        disks = getAvailableDisks(output)
        models = [disk.model.strip() for disk in disks.values()]
        for vmModel in VMDiskModels:
            if len([model for model in models if vmModel in model]): #vmModel in model because for VMware, a suffix can be added
                return True
    except Exception as e:
        log.warning('Could not determine if the machine is virtual. It will be considered as PHYSICAL. Details: %s', e)
    return False

def getRaidArrayDevices(device):
    """
    Return the list of block devices involved in a given raid array
        example:
            input: /dev/md0
            output: [/dev/sda3, /dev/sdb3]
    """
    command = ['/sbin/mdadm', '--detail', device]
    try:
        output = c4.utils.command.execute(command, "Could not execute mdadm command", user="root")
    except c4.utils.command.CommandException, e:
        log.error("mdadm command thrown exception: %s ", e)
        return []
    lines = output.splitlines()
    devices = []
    for line in reversed(lines):
        line = [item.strip() for item in line.split()]
        if line[0] == 'Number':
            break
        else:
            dev = line[-1]
            if dev.startswith('/dev'):
                devices.append(dev)
            else:
                log.warning('One device in the array %s is not active.', device)
    return devices

def calculateSwapUsage():
    """
    Calculates swap usage

    :returns: total (k), used (k), used_percent
    """
    total = 0
    used = 0
    with open("/proc/swaps") as f:
        # Example contents from /proc/swaps
        # Filename                Type        Size    Used    Priority
        # /dev/dm-1              partition    24780792    0    -1
        f.next()
        for line in f:
            print line
            swap_tokens = line.split()
            if len(swap_tokens) >= 4:
                # could be multiple swap files, so keep a running total
                total = total + int(swap_tokens[2])
                used = used + int(swap_tokens[3])
    # handle case when file is empty, like on a VM
    if total == 0:
        usage = 0
    else:
        usage = used / float(total) * 100
    return (total, used, usage)

def isStaleFile(file):
    import os
    try:
        os.lstat(file)
    except OSError as e:
        if e.errno == os.errno.ESTALE:
            return True
    return False

def getStaleFiles(path='/'):
    command = ['/bin/ls', '-la', path]
    res = []
    try:
        c4.utils.command.execute(command, "Could not execute ls", user="root")
    except c4.utils.command.CommandException as e:
        if 'Stale file handle' in e.error:
            lines = e.error.splitlines()
            for line in lines:
                #['/bin/ls:', 'cannot', 'access', '/head:', 'Stale', 'file', 'handle']
                res.append(line.split()[3][:-1])
    return res


def calculateMemoryInfo():
    """
    Calculates memory info

    Extracts total memory, free memory, buffer memory, and cached memory
    from /proc/meminfo.  Values are in kB.

    Also calculates used memory by subtracting free, buffer, and cached
    memory from total.

    Also calculates used memory as a percent

    :returns: memory status
    :rtype: :class:`~MemoryStatus`
    """

    # Example lines from /proc/meminfo
    # MemTotal:       198335704 kB
    # MemFree:        49995828 kB
    # Buffers:          902040 kB
    # Cached:         92300176 kB
    mem_info = {}

    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal"):
                tokens = line.split()
                mem_info["total_memory"] = int(tokens[1])

            elif line.startswith("MemFree"):
                tokens = line.split()
                mem_info["free_memory"] = int(tokens[1])

            elif line.startswith("Buffers"):
                tokens = line.split()
                mem_info["buffer_memory"] = int(tokens[1])

            elif line.startswith("Cached"):
                tokens = line.split()
                mem_info["cached_memory"] = int(tokens[1])

    mem_info["used_memory"] = mem_info["total_memory"] - \
                                mem_info["free_memory"] - \
                                mem_info["buffer_memory"] - \
                                mem_info["cached_memory"]

    mem_info["usage"] = mem_info["used_memory"] / float(mem_info["total_memory"]) * 100
    return mem_info
