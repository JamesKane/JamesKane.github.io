---
layout: post
title:  "StarFive VisionFive 2 - Updating to Boot from NVMe"
date:   2024-05-03 06:12:45 -0500
categories: ["single-board-computers"]
tags: ["visionfive-2", "setup"]
---
## Introduction:
I bought my StarFive VisionFive 2 early last year to tinker with some actual hardware and build a basic OS. However, 
like many projects, it got shelved for other priorities. Now, a year later, there have been several firmware updates, 
including the exciting ability to boot from an NVMe drive into StarFive's Debian image.

## The Update Process:
My first step was to download the latest Debian image from the [official StarFive website](https://debian.starfivetech.com/). 
After flashing the image to the NVMe drive using BalenaEtcher and installing it in the VisionFive 2, I encountered an 
immediate hurdle: the board remained stuck at the splash screen and wouldn't boot.
Thankfully, a quick web search led me to a helpful blog post by [James Chambers](https://jamesachambers.com/starfive-visionfive-2-firmware-update-guide/). 
This guide provided a clear outline for installing the necessary files:
* u-boot-spl.bin.normal.out
* visionfive2_fw_payload.img

Following the "Easy Way" instructions in the guide, I ran into another obstacle. Apparently, the image sizes had changed
over time, and they no longer fit within the /dev/mtd1 partition. After browsing through some threads on the StarFive 
forums, I discovered that /dev/mtd2 was now the appropriate target for flashing.
Here are the corrected commands for flashing the firmware:

{% highlight bash %}
sudo flashcp -v u-boot-spl.bin.normal.out /dev/mtd0
sudo flashcp -v visionfive2_fw_payload.img /dev/mtd2
{% endhighlight %}

## Success and Next Steps:
With a successful flash operation, I removed the micro-SD card and restarted the system. This time, the board booted 
flawlessly from the NVMe drive. For convenience, I simply installed gparted to resize the root partition and utilize the
remaining free space on the drive.    

```
user@starfive:~$ df -h
Filesystem      Size  Used Avail Use% Mounted on
udev            3.2G     0  3.2G   0% /dev
tmpfs           791M  3.4M  788M   1% /run
/dev/nvme0n1p4  917G   11G  907G   2% /
tmpfs           3.9G   36M  3.9G   1% /dev/shm
tmpfs           5.0M   12K  5.0M   1% /run/lock
tmpfs           791M  180K  791M   1% /run/user/1000
```

Now the board is prepped to start installing the development tool chains, which I will be using to re-introduce myself
to systems level programming.