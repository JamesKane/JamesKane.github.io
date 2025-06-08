---
layout: post
title:  "Human Pangenome Reference Experiments"
date:   2025-06-08 06:12:45 -0500
categories: ["genomics"]
tags: ["human pangenome", "WGS", "alignment"]
---

# Human Pangenome Reference Experiments - Setup A Pipeline

[A draft human pangenome reference](https://www.nature.com/articles/s41586-023-05896-x) was made available in 2023.  The graph-based approach uses 94 fully phased genome assemblies from 47 individuals at present versus a single linear sequence used in previous references. This graph-based representation provides a more accurate and comprehensive view of human genomic diversity.
With a new release of over 200 assemblies for [release 2](https://humanpangenome.org/hprc-data-release-2/) in 2025, it's time to experiment with the graph-based genome.

The paper offers the graph-based reference provides these key improvements:
1) Enhanced Assembly Quality: Compared to previous efforts, these assemblies exhibit significantly higher accuracy, contiguity, and structural accuracy.
2) Improved Variant Calling: The pangenome enables more accurate and comprehensive variant calling, including the detection of a larger number of structural variants (SVs) compared to previous methods.
3) Improved Read Mapping: Aligning reads to the pangenome improves read mapping accuracy, leading to better variant calling and downstream analyses like transcript mapping and ChIP-seq peak detection.

This blog entry will look at the tools and necessary files from the draft reference to align my Illumina NovaSEQ 30x WGS test and a low-coverage PacBio Sequel II library and call the variants for each.

## Required Software
[vg](https://github.com/vgteam/vg) - Tools for working with variation graphs specifically ```vg giraffe``` and ```vg stats```.

## Required Reference Files
```vg giraffe``` requires three files to operate on the Illumina short-reads:
1) The core graph file in compressed binary format - [GRCh38 Graph](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.d9.gbz)
2) The distance index file - [GRCh38 Distance Index](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.d9.dist)
3) The minimizer index file - [GRCh38 Minimizer Index](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.d9.min)
4) The snarls file (needed for calling) - [GRCh38 Snarls](https://s3-us-west-2.amazonaws.com/human-pangenomics/pangenomes/freeze/freeze1/minigraph-cactus/hprc-v1.1-mc-grch38/hprc-v1.1-mc-grch38.d9.snarls)

The tool can also use a Haplotype Index file instead of the AF-Filtering used in the files referenced above.  That capability is outside the scope of what this set of experiments is intending to cover.

## Why GRCh38 when there's a CHM13 alternate?
Simply because the v1.1 CHM13 graph appears to have used the GRCh38 chrY instead of the newer gapless chrY in CHM13v2.0.
Rather than dealing with multiple coordinate systems, I just decided to stick the GRCh38 for this run.  Hopefully, when
the newer graph based on the v2 assemblies land the gapless version is included instead.

## Hardware used in this experimentation
The scripts that followed were refined on a Fedora Linux Workstation with the following components:
* AMD Ryzen 9 7900X (12 cores/24 threads)
* 96GB of DDR5 RAM
* 2TB NVMe Drive

Other than situations where the pangenome graph is being indexed, the system never used more than ~51GB of RAM.  Lowering
the number of threads may make the scripts more accessible on more mainstream hardware.

## Short-Read Alignment Script
After a bit of experimentation with vg tools, the following script will produce a GAM and alignment statistics for a short-read
WGS library from FASTQ files. The first run of the script should be performed with minor modifications to produce new min index
and zipcodes files for short-reads.  Uncomment the original MIN_INDEX line for the files downloaded from AWS and comment out the
following line along with the `-z "${ZIP_INDEX}"` line in Step 1.  The re-indexing process requires a large amount of memory, I had to reduce
the number of threads to only 4 on my system for the new index to successfully generate.  Fortunately, the alignment
process is more reasonable in requiring ~50GB with all 24 threads.

The preconditions for the script include having run the original FASTQ files from [YSEQ](https://www.yseq.net) through 
`fastp -i WGS229_1.fastq.gz -I WGS229_2.fastq.gz -o WGS229_qc_1.fastq.gz -O WGS229_qc_2.fastq.gz`.  The process removed
~40,000 reads of the original 615.5 million reads for being too short or low quality.  The step was likely not necessary.

In a later experiment I will try to recreate the process on an Apple MacBook Pro with an M3 Max processor and 36GB of unified RAM.

```bash
#!/bin/bash
# Pangenome Alignment and Post-processing Pipeline

# --- Configuration Variables ---

# Base directories
BASE_DIR="/home/jkane/Genomics"
REFERENCE_DIR="${BASE_DIR}/Reference"
PANGENOME_REF_DIR="${REFERENCE_DIR}/PanGenomeRelease1/GRCh38"

# Input BAM details
SAMPLE_ID="WGS229"
OUTPUT_GAM="${SAMPLE_ID}.gam"

READS_R1_FQ="WGS229_qc_1.fastq.gz"
READS_R2_FQ="WGS229_qc_2.fastq.gz"

# Pangenome graph files
GBZ_GRAPH="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.gbz"
DIST_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.dist"
#MIN_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.min"
MIN_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.shortread.withzip.min"
ZIP_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.shortread.zipcodes"

NUM_THREADS=$(nproc)

# Step 1: vg giraffe
# Aligns the FASTQ reads to the pangenome graph, outputting a GAM file.
echo "Step 1/10: Aligning to pangenome graph with vg giraffe (output: '${OUTPUT_GAM}')..."
echo "Using ${NUM_THREADS} threads"

vg giraffe -p -t "${NUM_THREADS}" \
  -Z "${GBZ_GRAPH}" \
  -d "${DIST_INDEX}" \
  -m "${MIN_INDEX}" \
  -z "${ZIP_INDEX}" \
  -f "${READS_R1_FQ}" \
  -f "${READS_R2_FQ}" \
  -o GAM > "${OUTPUT_GAM}" || { echo "Error: vg giraffe failed"; exit 1; }
```

## Alignment Statistics - Short Reads

```text
Total alignments: 615565718
Total primary: 615565718
Total secondary: 0
Total aligned: 592849425
Total perfect: 321271267
Total gapless (softclips allowed): 584501083
Total paired: 615565718
Total properly paired: 592321740
Alignment score: mean 150.182, median 161, stdev 21.4798, max 161 (319454701 reads)
Mapping quality: mean 53.1969, median 60, stdev 17.4544, max 60 (497567953 reads)
Insertions: 14665393 bp in 4709079 read events
Deletions: 15605476 bp in 6588544 read events
Substitutions: 933011281 bp in 933011281 read events
Matches: 87069216181 bp (141.446 bp/alignment)
Softclips: 1150135356 bp in 33165562 read events
Total time: 281026 seconds
Speed: 2190.42 reads/second
```

We can see that all the available reads have been mapped with a primary location assignment.  321 million alignments
have perfect matches on the graph.  592 million reads have their mate within the expected length of the insert fragments.
The file will need to be called later to interpret the variations found from the graph.  Overall, the mapping
quality is great with a 53-mean Phred-scaled probability.

You can also see that the alignment process would take over 78 hours on a single core CPU.

## Low-Coverage PacBio HiFi Reads
As one of the people who purchased the HiFi Reads test from [Dante Labs](https://www.dantelabs.com) in 2023, I also
prepped a GAM from that library.  The 4x coverage long reads help resolve for structural variations, span repetitive 
regions, and aid in phasing the short read calls.  `vg giraffe` also has a preset mode for these reads.

```bash
# Define input and output file names
PACBIO_UBAM="GFX0457637_SL_L001_001.reads.bam"
PACBIO_FASTQ="GFX0457637_SL_L001_001.reads.fastq"
PACBIO_GAM="GFX0457637_SL_L001_001.reads.gam"

# Pangenome graph files
GBZ_GRAPH="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.gbz"
DIST_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.dist"
MIN_INDEX="${PANGENOME_REF_DIR}/hprc-v1.1-mc-grch38.d9.min"

NUM_THREADS=$(nproc)

echo "Step 1/2: Converting PacBio HiFi uBAM to FASTQ..."
samtools fastq "${PACBIO_UBAM}" > "${PACBIO_FASTQ}" || \
  { echo "Error: samtools fastq failed"; exit 1; }
echo "PacBio HiFi reads extracted to ${PACBIO_FASTQ}"

echo "Step 2/2: Aligning PacBio HiFi reads to pangenome graph with vg giraffe (output: '${PACBIO_GAM}')..."
vg giraffe -t "${NUM_THREADS}" \
  -Z "${GBZ_INDEX}" \
  -d "${DIST_INDEX}" \
  -m "${MIN_INDEX}" \
  -f "${PACBIO_FASTQ}" \
  --output-format GAM \
  --parameter-preset hifi \
  > "${PACBIO_GAM}" || { echo "Error: vg giraffe failed for PacBio reads"; exit 1; }
echo "PacBio HiFi reads aligned to ${PACBIO_GAM}"
```

NOTE: The hifi preset generates the same shortread min and zipcodes file as the first script.  Therefore, an optimization
would be to simply reuse them.  I didn't do that as the HiFi library was relatively quick to align compared to the 10x
bigger NovaSeq library in the first example.

## Alignment Statistics - Long Reads
```text
Total alignments: 1059479
Total primary: 1059479
Total secondary: 0
Total aligned: 1008105
Total perfect: 92772
Total gapless (softclips allowed): 796896
Total paired: 0
Total properly paired: 0
Alignment score: mean 3889.5, median 3337, stdev 2793.22, max 23203 (1 reads)
Mapping quality: mean 59.0571, median 60, stdev 6.50758, max 60 (983225 reads)
Insertions: 442554 bp in 270471 read events
Deletions: 333430 bp in 183560 read events
Substitutions: 5297231 bp in 5297231 read events
Matches: 3941456234 bp (3720.18 bp/alignment)
Softclips: 7458707729 bp in 1292345 read events
Total time: 16954.2 seconds
Speed: 62.4906 reads/second
```
The early HiFi design from Dante was apparently targeting a ~4x.  983k of the one million reads max out the mapping quality
metric in `vg giraffe`, which is one of the great features of long reads.  A surprising feature is the number of soft clips
would indicate there are a fair number of novel sequences, unrepresented structural variants or regions not fully resolved
in the 1.1 pangenome graph.

It will be interesting to follow up on this more when someone decides to offer a high coverage long read test on the
direct-2-consumer option in the future, or when the 2.x version of the pangenome graph becomes available.

## Conclusions
This blog entry sets out a basic set of scripts for aligning a short-read or long-read WGS library using `vg giraffe` and
presents some discussion of the `vg stats` results.  The tools require a significant investment in computing hardware to
be able to use effectively.  The tested Ryzen 9 7900X system is outfitted with 96GB of DDR5 RAM, and struggled with
re-constructing the short-read indices needed for `vg giraffe`.  The workaround was to limit the number of cores and trade
wall-clock time to complete the task.  Later runs were able to reuse the zipcode file using all 24 CPU threads.

Future blog articles will:
1) Cover projecting the GAMs back to the GRCh38 linear reference to compare coverage statistics with `bwa-mem` and `minimap2`.
2) Compare variant calling for some selected chrY SNPs downstream of R1b-CTS4466 and interesting traits using the projected BAM files and `vg call` directly.