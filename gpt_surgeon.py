#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import struct
import binascii
import uuid


def readStruct(stream, fmt):
    length = struct.calcsize(fmt)
    data = stream.read(length)
    if len(data) == length:
        return struct.unpack(fmt, data)
    else:
        return None


def readStruct1(stream, fmt):
    fields = readStruct(stream, fmt)
    if fields and len(fields) == 1:
        return fields[0]
    else:
        return None


def writeStruct(stream, fmt, *fields):
    stream.write(struct.pack(fmt, *fields))


blockSize = 512  # bytes

efiHeaderExpectedSize = 92  # bytes
efiHeaderFmt = '<8s4sII4xQQQQ16sQIII'
efiSignature = "EFI PART"
efiExpectedVersion = "\x00\x00\x01\x00"

efiEntryExpectedSize = 128  # bytes
efiEntryFmt = '<16s16sQQQ72s'


def crc32(b):
    return binascii.crc32(b) & 0xffffffff


class EFIPartitionTable(object):
    def __init__(self, disk):
        rawHeader = disk.read(efiHeaderExpectedSize)
        sig, version, \
            headerSize, headerCRC, \
            self.currentLBA, self.backupLBA, \
            self.firstUsableLBA, self.lastUsableLBA, \
            diskUUID, \
            self.partitionTableStartLBA, \
            self.partitionTableEntryCount, self.partitionTableEntrySize, \
            self.partitionTableCRC = struct.unpack(efiHeaderFmt, rawHeader)
        self.diskUUID = uuid.UUID(bytes_le=diskUUID)
        # sanity checks
        assert sig.decode('utf-8') == efiSignature
        assert version.decode('utf-8') == efiExpectedVersion
        assert len(rawHeader) == efiHeaderExpectedSize
        assert headerSize == efiHeaderExpectedSize
        assert self.lastUsableLBA >= self.firstUsableLBA
        assert self.currentLBA != self.backupLBA
        assert self.partitionTableStartLBA >= 2
        # corruption check
        headerForCRC = rawHeader[:16] + struct.pack('<I', 0) + rawHeader[20:]
        assert crc32(headerForCRC) == headerCRC

        disk.seek(blockSize * self.partitionTableStartLBA)
        rawTable = disk.read(self.partitionTableEntryCount *
                             self.partitionTableEntrySize)
        # corruption check
        assert crc32(rawTable) == self.partitionTableCRC

        self.partitionTable = []
        for idx in range(self.partitionTableEntryCount):
            self.partitionTable.append(EFIPartitionEntry(
                rawTable[idx * self.partitionTableEntrySize:(idx + 1) * self.partitionTableEntrySize]))

    def pack(self, tableCRC):
        rawHeader = struct.pack(efiHeaderFmt,
                                efiSignature, efiExpectedVersion,
                                efiHeaderExpectedSize, 0,
                                self.currentLBA, self.backupLBA,
                                self.firstUsableLBA, self.lastUsableLBA,
                                self.diskUUID.bytes_le,
                                self.partitionTableStartLBA,
                                self.partitionTableEntryCount, self.partitionTableEntrySize,
                                tableCRC)
        headerCRC = crc32(rawHeader)
        rawHeader = rawHeader[:16] + \
            struct.pack('<I', headerCRC) + rawHeader[20:]
        return rawHeader


unusedUUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
hfsPlusUUID = uuid.UUID("48465300-0000-11AA-AA11-00306543ECAC")

knownUUIDs = {
    uuid.UUID("00000000-0000-0000-0000-000000000000"): "Unused",
    uuid.UUID("024DEE41-33E7-11D3-9D69-0008C781F39F"): "MBR Scheme",
    uuid.UUID("C12A7328-F81F-11D2-BA4B-00A0C93EC93B"): "EFI System",
    uuid.UUID("21686148-6449-6E6F-744E-656564454649"): "BIOS Boot",

    uuid.UUID("E3C9E316-0B5C-4DB8-817D-F92DF00215AE"): "Microsoft Reserved",
    uuid.UUID("EBD0A0A2-B9E5-4433-87C0-68B6B72699C7"): "Microsoft Basic Data",
    uuid.UUID("5808C8AA-7E8F-42E0-85D2-E1E90434CFB3"): "Microsoft Logical Disk Manager metadata",
    uuid.UUID("AF9B60A0-1431-4F62-BC68-3311714A69AD"): "Microsoft Logical Disk Manager data",

    uuid.UUID("48465300-0000-11AA-AA11-00306543ECAC"): "Apple HFS+",
    uuid.UUID("55465300-0000-11AA-AA11-00306543ECAC"): "Apple UFS",
    uuid.UUID("52414944-0000-11AA-AA11-00306543ECAC"): "Apple RAID",
    uuid.UUID("52414944-5F4F-11AA-AA11-00306543ECAC"): "Apple RAID (offline)",
    uuid.UUID("426F6F74-0000-11AA-AA11-00306543ECAC"): "Apple Boot",
    uuid.UUID("4C616265-6C00-11AA-AA11-00306543ECAC"): "Apple Label",
    uuid.UUID("5265636F-7665-11AA-AA11-00306543ECAC"): "Apple TV Recovery",
    uuid.UUID("6A898CC3-1DD2-11B2-99A6-080020736631"): "Apple ZFS",
}


class EFIPartitionEntry(object):
    def __init__(self, bytes):
        partitionType, partitionUUID, \
            self.firstLBA, self.lastLBA, \
            self.flags, \
            name = struct.unpack(efiEntryFmt, bytes)
        self.partitionType = uuid.UUID(bytes_le=partitionType)
        self.partitionUUID = uuid.UUID(bytes_le=partitionUUID)
        name = name.decode('utf-16le')
        term = name.find('\x00')
        if term >= 0:
            name = name[:term]
        self.name = name

    def pack(self):
        rawEntry = struct.pack(efiEntryFmt,
                               self.partitionType.bytes_le, self.partitionUUID.bytes_le,
                               self.firstLBA, self.lastLBA,
                               self.flags,
                               self.name.encode('utf-16le'))
        return rawEntry


def readMBRAndGPT(diskDevice):
    disk = open(diskDevice, 'rb')
    mbr = disk.read(blockSize)
    gpt = EFIPartitionTable(disk)
    disk.close()
    print("Read MBR and GPT from %s." % diskDevice)
    return (mbr, gpt)


def listGPT(diskDevice):
    _, gpt = readMBRAndGPT(diskDevice)
    for i in range(gpt.partitionTableEntryCount):
        entry = gpt.partitionTable[i]
        if entry.partitionType == unusedUUID:
            continue
        print("partition %d:" % i)
        print("     type: %s" % knownUUIDs.get(
            entry.partitionType, "<unknown partition type>"))
        print("     name: %r" % entry.name)
        print("    flags: 0x%08x" % entry.flags)


def fixGPTPartitionType(diskDevice, selectedPartition):
    mbr, gpt = readMBRAndGPT(diskDevice)
    gpt.partitionTable[selectedPartition].partitionType = hfsPlusUUID
    print("Changing type of partition #%d on %s to HFS+..." %
          (selectedPartition, diskDevice))
    disk = open(diskDevice, 'wb')
    print("    Opened %s for writing." % diskDevice)
    disk.write(mbr)
    print("    Wrote MBR.")
    table = b""
    for i in range(gpt.partitionTableEntryCount):
        entry = gpt.partitionTable[i]
        table = table + entry.pack()
    header = gpt.pack(crc32(table))
    disk.write(header)
    print("    Wrote GPT header.")
    disk.write("\x00" * (blockSize - len(header)))
    disk.write(table)
    print("    Wrote GPT entries.")
    disk.close()
    print("    Closed %s." % diskDevice)
    print("Done.")


usage = """
usage:

%(progName)s list </dev/diskN>
    Show GPT entries for a disk.

%(progName)s repair </dev/diskN> <partition number>
    Change the type of the selected partition on the selected disk to HFS+.
    The partition numbers start at 0, as in the list command.
"""[1:]


def exitToUsage(msg):
    progName = sys.argv[0]
    print
    print(msg)
    print
    print(usage % {'progName': progName})
    exit(1)


def main():
    argc = len(sys.argv)
    if argc < 2:
        exitToUsage("No command given!")
    cmd = sys.argv[1]
    if cmd == 'list':
        if argc < 3:
            exitToUsage("Too few arguments for list command!")
        if argc > 3:
            exitToUsage("Too many arguments for list command!")
        diskDevice = sys.argv[2]
        print
        listGPT(diskDevice)
    elif cmd == 'repair':
        if argc < 4:
            exitToUsage("Too few arguments for repair command!")
        if argc > 4:
            exitToUsage("Too many arguments for repair command!")
        diskDevice = sys.argv[2]
        selectedPartition = int(sys.argv[3])
        print
        fixGPTPartitionType(diskDevice, selectedPartition)
    else:
        exitToUsage("Unsupported command!")


if __name__ == '__main__':
    main()
