---
layout: post
title:  "One Path Ends, Another Begins"
date:   2025-04-19 00:00:00 -0500
categories: ["genomics"]
tags: ["Orange Pi 5 Plus", "personal genomics"]
---

# Personal Genomics on an Orange Pi 5 Plus

With the pending shutdown of ydna-warehouse.org, it is time to start sketching out a possible path to a federated system to democratize the compute and storage costs across users.  One possible solution is for users to build a low-cost home server using a single-board computer or mini computer.  The Orange Pi 5 Plus featuring a Rockchip RK3588 ARM processor is a power efficient, lower cost option which could conceivably fill the role with a 16GB of RAM model.
## The Build
For this post we will be looking at the performance of this specific configuration, which matches the 16GB Pi 5 Plus with a 1TB NVME, cooling, case, and a 20W power supply.

| Qty | Item | Price | Subtotal |
|-----|------|-------|----------|
| 1| Orange Pi 5 Plus 16G | $151.99 | $151.99 |
| 1 | Kingston NV2 1TB M.2 2280 NVME | $60.99 | $60.99 |
| 1 | DVOZO Orange Pi 5 Plus Case & 5V 4A Power Supply Kit | $21.99 | $21.99 |
| | | Subtotal: | $234.97 |

The Orange Pi 5 Plus features the Rockchip RK35588.  The system on a chip provides quad Arm Cortex-A76 running up to 2.4GHz, quad Cortex-A55 cores, and NEON co-processors.  The Arm Mail-610 GPU provides for accelerated 3D graphics when used with a display.  An embedded NPU provides up to 6Tops, which may be beneficial for edge-computing operations, but will not be explored at this time.  A wide assortment of connections can be explored on Orange Pi’s [product information page](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5-plus.html).  For the purposes of this article, we are using the bottom PCIe M.2 Socket for a 1TB Kingston NV2 NVME drive and one 2.5G LAN port to control the board remotely via SSH.

Assembling the parts into the DVOZO case was quick, since the process boils down to inserting the NVME drive and installing the cooler.  Unfortunately the provided fan is obnoxiously loud by modern standards, but certainly quieter than a 1990s cooler used my [college days](https://jameskane.blog/retro-computing/2024/05/23/Amiga-500-Restoration-Project.html).

## The Software
All common bioinformatics software is built with POSIX platforms as a target, so we will be using Orange Pi’s [Official Debian Image](https://drive.google.com/drive/folders/1I_asEsyjMf_nixpymLdco7SCxr9AveYH).  The image was written to the Kingston NVME using an external dock from my laptop using balenaEtcher and resized the main root partition to use all available space after booting the board.

The actual applications we need for the early experiments are part of the Debian Package library: bwa-mem, minimap2 and samtools.

The packages are installed via this command:
```bash 
sudo apt install bwa minimap2 samtools
``` 

### BWA-MEM
BWA-MEM is part of the [BWA (Burrow-Wheeler Aligner)](https://github.com/lh3/bwa).  The software is the most popular short-read alignment tool due to speed and accuracy.  It’s purpose is to take raw 100 to 150bp reads common in Illumina platform sequencing and find the best placement on a reference genome for further study.  This is a lengthy compute process which thankfully can be make use of the RK3588’s NEON co-processors thanks to the neon_sse.h compiled into the application.

### minimap2
[Minimap2](https://github.com/lh3/minimap2) is another alignment tool primarily used for PacBio or Oxford Nanopore long-reads.  The tool also offers modes to work with short-read data.  Some labs will use minimap2 for this purpose as the algorithms are [up to 3x faster but can be unpredictable](https://lh3.github.io/2018/04/02/minimap2-and-the-future-of-bwa).  This software requires our boards NEON co-processors as well.

### samtools
Samtools are a collection of tools (written in C) for working with next-generation sequencing data.  It will be used in BASH pipelines with the aligners to prepare our raw data and inspect the results.

## The Data
For a reference, we will use [hs1 (chm13v2.0)](https://s3-us-west-2.amazonaws.com/human-pangenomics/T2T/CHM13/assemblies/analysis_set/chm13v2.0.fa.gz) from the [Telomere-to-Telomere consortium](https://sites.google.com/ucsc.edu/t2tworkinggroup).  Hs1 gives us a complete assembly of a human genome without the gaps in the more common hg38 reference.

For a read library, we will use WGS229 from yseq.net.  The sample donor is of mixed European descent with Y haplogroup R1b and mtDNA haplogroup U5a.  Since hs1 is also a European sample, we won’t expect a large number of reads not mapping due to structural differences in other populations.  The read library is composed of 615,605,482 150bp PE reads sequenced on via the Illumina NovaSeq platform in 2018.

## The Tests
The goal of a federated matching system is to have a common analysis pipeline between users to minimize disparate analysis artifacts during comparison.  So we will look at the performance of alignment and post processing times using two popular aligners on the Pi 5 Plus and compare them with enthusiast level x86-64 hardware and an M3 MacBook Pro for reference.

For bwa the following pipeline is used:
```bash
time bwa mem -t $MAX_CORES -M -R $READ_GROUP ${reference} - \
  | samtools fixmate -u -m - - \
  | samtools sort -@ $SORT_CORES -T /tmp - \
  | samtools markdup -@ $MAX_CORES - ${target}
```

For minimap2 the following pipeline is modified as follows:
```bash
time minimap2 -ax sr -t $MAX_CORES -R $READ_GROUP ${reference} - \
  | samtools fixmate -u -m - - \
  | samtools sort -@ $SORT_CORES -m4g -T /tmp - \
  | samtools markdup -@ $MAX_CORES - ${target}
```

The Pi 5 Plus was run with MAX_CORES set to the number of Arm Cortex-A76 cores (4) due to the physical 16GB of RAM being exceeded in minimap2.

## Results

The Alignment Results table shows the results of the scripts for the Pi 5 Plus vs machines that are a full order of magnitude more expensive, but are fairly typical of mid-tier gaming or prosumer grade computers.

| System          | Cores        | RAM   | Aligner  | Wall Time            | Reads / Second / Core |
|-----------------|--------------|-------|----------|----------------------|-----------------------|
| Pi 5 Plus       | 4            | 16GB  | minimap2 | 11h 42m 5s 223ms     | 3,653.4               |
| Pi 5 Plus       | 8 (4P/4E)    | 16GB  | bwa mem  | 1d 21h 26m 59s 156ms | 470.3                 |
| Core i7-12700KF | 12 (8P/4E)   | 128GB | minimap2 | 2h 46m 56s 400ms     | 5,121.6               |
| Core i7-12700KF | 12 (8P/4E)   | 128GB | bwa mem  | 8h 26m 9s 600ms      | 1,689.2               |
| Ryzen 7900X     | 12           | 96GB  | minimap2 | 1h 28m 4s 145ms      | 9,708.4               |
| Ryzen 7900X     | 12           | 96GB  | bwa mem  | 5h 9m 16s 825ms      | 2,764.5               |
| M3 Max          | 14 (10P/4E)  | 36GB  | minimap2 | 2h 19m 57s 460ms     | 5,236.3               |
| M3 Max          | 14 (10P/4E)  | 36GB  | bwa mem  | 7h 31m 58s 420ms     | 1,621.5               |


The important takeaway is that the RK3588 with 16GB of DDR4 RAM is able to complete the task of aligning the raw reads to a BAM file.  The Pi 5 Plus accomplishes this while staying under 20 watts versus the 170 watts of the Ryzen 7900X.  This results in a very similar energy cost to perform the tasks.  A user is simply trading time by choosing the Pi 5 Plus.

The Pi 5 Plus does fall off a performance cliff when attempting to use all 8 cores in bwa mem.  Additional testing will be required to validate a hypothesis that this is due to the Cortex A55-cores not being suitable for the algorithms.

## Conclusions
Looking at low-cost 20watt solution like the Orange Pi 5 Plus, we can see an approximately $250 investment looks viable as an alternative for the most intensive operation to standardize the workflow.  While four to eight times slower than x86-64 examples the overall energy costs are very close.  Therefore such a machine could be assembled and used in a compute/personal data storage capacity for individuals who no longer have an always on desktop that could participate in a distributed system.

Other options that could also be considered are a base level [M4 Mac mini](https://www.apple.com/mac-mini/) with external SSD storage or an [AMD NUC](https://www.amazon.com/s?k=amd+nuc) device.  These devices should be more in-line with the Core i7 and Apple M3 in performance for double the investment.  Perhaps I can look at these in the future if review units can be acquired.