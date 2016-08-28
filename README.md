# GPT Surgeon

Command-line tool for repairing corruption of HFS+ partition labels on GPT-partitioned drives.

I originally noticed this corruption on an external HD in a Mac OS X/Windows Vista dual-boot setup
using [MacDrive](http://www.mediafour.com/software/macdrive/) 7 for HFS+ access,
but some GPT Surgeon users have reported the same issue with Apple's Boot Camp drivers.

Generally this manifests as the Apple Disk Utility error "invalid BS_jmpBoot in boot block: 000000"
after you've booted Windows, accessed the drive, and then booted Mac OS X. The data hasn't been lost,
but the partition type GUID is wrong, and so Mac OS X can't recognize the filesystem.

See the below blog posts and their comments for more info:

* [invalid BS_jmpBoot in boot block: 000000](https://steelpangolin.wordpress.com/2009/03/15/invalid-bs_jmpboot-in-boot-block-000000/)
* [more on: invalid BS_jmpBoot in boot block: 000000](https://steelpangolin.wordpress.com/2009/11/12/more-on-invalid-bs_jmpboot-in-boot-block-000000/)

## Requirements

Requires Python 2.5 or higher. Not tested with Python 3.

GPT Surgeon relies on direct access to device files, so you'll need to run it as `root`
on Mac OS X, Linux, FreeBSD, etc. My instructions assume Mac OS X. It won't work as is on Windows.

## Using GPT Surgeon

You'll need to know the path to the affected disk.
You can use the info button in Apple's Disk Utility, or `diskutil list` in the Terminal.
For an external disk, this will usually be `/dev/disk1` or higher;
if your boot disk is encrypted with FileVault, it may be `/dev/disk2` or higher.

Show GPT entries for a disk:

```bash
sudo ./gpt_surgeon.py list </dev/diskN>
```

Change the type of the selected partition on the selected disk to HFS+:

```bash
sudo ./gpt_surgeon.py repair </dev/diskN> <partition number>
```

The partition numbers start at 0, as in the output of the list command.

I've also made a walkthrough video:

[![walkthrough video](https://img.youtube.com/vi/Xumbf5rOp6c/0.jpg)](https://www.youtube.com/watch?v=Xumbf5rOp6c "Walkthrough for repairing a Mac GPT disk damaged by MacDrive")

## Submitting bug reports

If you run into problems with GPT Surgeon and your disk, please install
[`disktype`](http://disktype.sourceforge.net/) (which you can get from
[Homebrew](http://brew.sh/) or [MacPorts](https://www.macports.org/)),
and include a `disktype` report for the affected disk with your Github issue:

```bash
sudo disktype </dev/diskN> > disktype_report.txt
```
