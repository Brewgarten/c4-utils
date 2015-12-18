import logging
import os
import time

import pytest

from c4.utils.devices import addAdaptecControllerInformation, addLSIControllerInformation, getAvailableDisks, DiskTypes, BlockDeviceMapping
from c4.utils.scsi.base import PhysicalDeviceInfo
from c4.utils.scsi.adaptec import AdaptecDevicesInfo
from c4.utils.scsi.lsi import LSIDevicesInfo


logging.Formatter.converter = time.gmtime
log = logging.getLogger(__name__)

@pytest.fixture(params=["lsblk_baremetal.output", "lsblk_baremetal_haswell.output"])
def blockDeviceInfoFile(request):
    return request.param

@pytest.fixture(params=["block_device_mapping.output", "block_device_mapping_haswell.output"])
def blockDeviceMappingFile(request):
    return request.param

@pytest.fixture(params=[{"class": AdaptecDevicesInfo,
                         "ld_info_file" : "arcconf_ld_baremetal.output",
                         "pd_info_file" : "arcconf_pd_baremetal.output"},
                        {"class": LSIDevicesInfo,
                         "ld_info_file" : "storcli_ld_baremetal_haswell.json",
                         "pd_info_file" : "storcli_pd_baremetal_haswell.json"}
                        ])
def controller(request):
    return request.param

@pytest.fixture
def utilsTestDataDir():
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")

class TestControllers():

    def test_fromString(self, utilsTestDataDir, controller):

        with open(os.path.join(utilsTestDataDir, controller["ld_info_file"])) as f:
            logicalDevicesString = f.read()
        with open(os.path.join(utilsTestDataDir, controller["pd_info_file"])) as f:
            physicalDevicesString = f.read()

        info = controller["class"].fromString(logicalDevicesString, physicalDevicesString)
        assert len(info.controllers) == 1
        assert len(info.controllers[0].logicalDevices) == 12
        assert len(info.controllers[0].logicalDevicesbyNameMap) == 12
        for name, device in info.controllers[0].logicalDevicesbyNameMap.items():
            assert name.startswith("JBOD")
            assert len(device.physicalDevices) == 1
            for physicalDevice in device.physicalDevices.values():
                assert isinstance(physicalDevice, PhysicalDeviceInfo)
        assert len(info.controllers[0].physicalDevices) == 12

    def test_parseLogicalDevicesString(self, utilsTestDataDir, controller):

        with open(os.path.join(utilsTestDataDir, "arcconf_ld_baremetal.output")) as f:
            logicalDevicesMap = AdaptecDevicesInfo.parseLogicalDevicesString(f.read())
            assert len(logicalDevicesMap) == 12
            for deviceId, device in logicalDevicesMap.items():
                assert isinstance(deviceId, int)
                assert device.name.startswith("JBOD")
                assert len(device.physicalDevices) == 1

    def test_parsePhysicalDevicesString(self, utilsTestDataDir, controller):

        with open(os.path.join(utilsTestDataDir, "arcconf_pd_baremetal.output")) as f:
            physicalDevicesMap = AdaptecDevicesInfo.parsePhysicalDevicesString(f.read())
            assert len(physicalDevicesMap) == 12
            assert len([device for device in physicalDevicesMap.values() if device.isSSD]) == 6
            assert len([device for device in physicalDevicesMap.values() if not device.isSSD]) == 6

def test_addAdaptecControllerInformation(utilsTestDataDir):

    with open(os.path.join(utilsTestDataDir, "lsblk_baremetal.output")) as f:
        disks = getAvailableDisks(f.read())

    with open(os.path.join(utilsTestDataDir, "arcconf_ld_baremetal.output")) as f:
        logicalDevicesString = f.read()
    with open(os.path.join(utilsTestDataDir, "arcconf_pd_baremetal.output")) as f:
        physicalDevicesString = f.read()

    devicesInfo = AdaptecDevicesInfo.fromString(logicalDevicesString, physicalDevicesString)

    assert len(disks) == 11

    assert len([disk for disk in disks.values() if disk.type == DiskTypes.SSD]) == 0
    assert len([disk for disk in disks.values() if disk.type == DiskTypes.HDD]) == 11

    with pytest.raises(ValueError):
        addAdaptecControllerInformation(disks, {})

    addAdaptecControllerInformation(disks, devicesInfo)

    assert len([disk for disk in disks.values() if disk.type == DiskTypes.SSD]) == 6
    assert len([disk for disk in disks.values() if disk.type == DiskTypes.HDD]) == 5

def test_addLSIControllerInformation(utilsTestDataDir):

    with open(os.path.join(utilsTestDataDir, "lsblk_baremetal_haswell.output")) as f:
        disks = getAvailableDisks(f.read())
    with open(os.path.join(utilsTestDataDir, "storcli_ld_baremetal_haswell.json")) as f:
        logicalDevicesString = f.read()
    with open(os.path.join(utilsTestDataDir, "storcli_pd_baremetal_haswell.json")) as f:
        physicalDevicesString = f.read()
    devicesInfo = LSIDevicesInfo.fromString(logicalDevicesString, physicalDevicesString)
    with open(os.path.join(utilsTestDataDir, "block_device_mapping_haswell.output")) as f:
        mapping = BlockDeviceMapping.fromString(f.read())

    assert len(disks) == 11

    assert len([disk for disk in disks.values() if disk.type == DiskTypes.SSD]) == 0
    assert len([disk for disk in disks.values() if disk.type == DiskTypes.HDD]) == 11

    with pytest.raises(ValueError):
        addLSIControllerInformation(disks, {}, mapping)
    with pytest.raises(ValueError):
        addLSIControllerInformation(disks, devicesInfo, {})

    addLSIControllerInformation(disks, devicesInfo, mapping)

    assert len([disk for disk in disks.values() if disk.type == DiskTypes.SSD]) == 6
    assert len([disk for disk in disks.values() if disk.type == DiskTypes.HDD]) == 5

def test_blockDeviceMapping(utilsTestDataDir, blockDeviceMappingFile):

    with open(os.path.join(utilsTestDataDir, blockDeviceMappingFile)) as f:
        mapping = BlockDeviceMapping.fromString(f.read())
        assert len(mapping.devices) == 12
        for blockDeviceId, name in mapping.deviceNamebyIDMap.items():
            assert isinstance(blockDeviceId, int)
            assert name.startswith("sd")
        for name, blockDeviceId in mapping.IDbyDeviceNameMap.items():
            assert isinstance(blockDeviceId, int)
            assert name.startswith("sd")

def test_getAvailableDisks(utilsTestDataDir, blockDeviceInfoFile):

    with open(os.path.join(utilsTestDataDir, blockDeviceInfoFile)) as f:

        disks = getAvailableDisks(f.read())
        assert len(disks) == 11
        for disk in disks.values():
            assert disk.name.startswith("sd")
            # without additional information from controller all disks should be HDD
            assert disk.type == DiskTypes.HDD
