---
layout: post
title:  "Try It Yourself: A Pangenome Variant-Calling Bench"
date:   2026-06-23 07:00:00 -0500
categories: ["genomics"]
tags: ["human pangenome", "vg", "GATK", "delly", "sniffles", "bcftools", "tutorial", "reproducible"]
excerpt: "The two previous posts made some claims about pangenomes. This one is the bench notes: every tool, every command, and every gotcha, so you can run the same experiments on your own data. It all runs locally on one workstation."
---

# Try It Yourself: A Pangenome Variant-Calling Bench

The [last](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html) [two](/genomics/2026/06/16/what-a-pangenome-misses-and-what-it-nails.html) posts made some claims about what a pangenome graph can and cannot do. This post is the part I find most useful in other people's writing and most often missing: the bench notes. Every tool, the actual commands, and the mistakes that cost me an afternoon, so you can put your own data on the bench and check my work.

Everything here runs locally on a single workstation. Mine is a Mac Studio, but the same tools build and run on Linux, and in the spirit of the [Orange Pi experiments](/genomics/2025/04/19/Personal-Genomics-on-an-Orange-Pi-5-Plus.html), none of it requires sending your genome to anyone.

## The toolbox

| Tool | Used for | Where |
|------|----------|-------|
| [`vg`](https://github.com/vgteam/vg) | pangenome mapping, calling, surject, deconstruct, augment | GitHub, or `brew install vg` on Linux |
| [`samtools` / `bcftools`](https://www.htslib.org/) | BAM/CRAM/VCF wrangling | htslib.org |
| [`GATK`](https://github.com/broadinstitute/gatk) HaplotypeCaller | standard linear small-variant calling | Broad Institute |
| [`Delly`](https://github.com/dellytools/delly) | short-read structural variant calling | GitHub (build from source) |
| [`sniffles`](https://github.com/fritzsedlazeck/Sniffles) | long-read (HiFi) SV calling | `pip install sniffles` |
| [`bwa-mem2`](https://github.com/bwa-mem2/bwa-mem2) | linear short-read alignment | GitHub |
| [Decoding-Us API](https://decoding-us.com/api/docs/) | the Y phylogeny and its markers | `/api/v1/y-tree` |
| Python + matplotlib | overlap analysis and the charts | `pip` |

You also need a reference, a pangenome, and your reads. For the reference, use a T2T-CHM13v2.0 analysis set, and read the gotchas section before you pick which one. For a pangenome you can build your own with [minigraph-cactus](https://github.com/ComparativeGenomicsToolkit/cactus), or start from the public [Human Pangenome Reference](https://humanpangenome.org/) GBZ. Your reads can be ordinary 30x Illumina; HiFi is optional but it is the referee that settles the hard cases.

A note on coordinates: I work entirely in CHM13 (hs1) coordinates because that is what my graph uses. If your graph is GRCh38-based, substitute accordingly, but keep one coordinate system for the whole bench or you will spend a day chasing contig-name mismatches.

## Recipe 1: map and genotype against the graph

If you are starting from FASTQ, map with giraffe. You need the GBZ plus its companion indexes (`.min`, `.dist`).

```bash
vg giraffe -Z graph.gbz -m graph.min -d graph.dist \
  -f reads_1.fq.gz -f reads_2.fq.gz -t 16 > aln.gam
```

Then compute read support and genotype the variation that is in the graph:

```bash
vg pack -x graph.gbz -g aln.gam -Q 5 -o aln.pack -t 16
vg snarls graph.gbz > graph.snarls          # or use a precomputed one
vg call graph.gbz -k aln.pack -r graph.snarls -z -s MYSAMPLE -t 16 > calls.vcf
```

That `-z` restricts the search to the GBZ haplotypes, which is faster and usually more accurate for a personal pangenome. The output is in your reference's coordinates with one sample column.

Keep this number in mind for later: this callset is a **genotyping** of the variation already represented in the graph. It is not a discovery callset. That distinction is the whole point of the second post.

## Recipe 2: a Y haplogroup from the graph

The phylogeny and its markers come from the Decoding-Us API. The tree is one request:

```bash
curl -s "https://decoding-us.com/api/v1/y-tree" > ytree.json
```

Each node carries defining variants with coordinates in GRCh37, GRCh38, and hs1, plus the ancestral and derived alleles. Pull the `hs1` coordinates if your VCF is CHM13-based. You also need the reference base at each marker, which you can extract straight from the graph:

```bash
echo "CHM13#0#chrY" > ypath.txt
vg paths -x graph.gbz -F -p ypath.txt > chrY.fa
samtools faidx chrY.fa
```

The placement itself is where a naive approach goes wrong. Do not just pick the deepest node with a derived call, because one paralog artifact in the repetitive Y will drag you onto the wrong branch. Borrow the logic the published callers use ([yhaplo](https://github.com/23andMe/yhaplo), [pathPhynder](https://github.com/ruidlpm/pathPhynder)): walk the tree, only step into a child branch that has net positive derived support, route by which subtree holds the most evidence, and report the deepest node with genuine variant support. Two details earned their keep: collapse tree nodes that have no usable SNP markers (some are defined only by indels) and re-parent their children, and for the haploid Y drop any site whose pileup is not near-monoallelic, since a mixed allele balance means a paralog. I wrapped all of this in a [small Python script](/assets/code/y_haplogroup.py) you can grab and adapt; the algorithm matters more than my code. It runs on a graph VCF, a CHM13-surjected BAM, or a linear CHM13 CRAM.

The honest result for my sample: the graph VCF resolves confidently to R1b-P312 and then stops, because the rest of the lineage is not in the panel. To get the terminal, you surject.

## Recipe 3: surject for discovery, and measure the gap

Surjection projects the graph alignments back onto the linear reference, so an ordinary caller can find anything the reads support, not just what the graph represents.

```bash
vg surject -x graph.gbz -b -t 14 -n CHM13 aln.gam \
  | samtools sort -@ 4 -m 2G -o surjected.bam -
samtools index surjected.bam
```

Now call it with a standard linear caller. GATK wants a sequence dictionary, an indexed reference, and a read group:

```bash
gatk CreateSequenceDictionary -R ref.fa
samtools addreplacerg -r 'ID:x' -r 'SM:MYSAMPLE' -r 'PL:ILLUMINA' -o rg.bam surjected.bam
samtools index rg.bam
gatk HaplotypeCaller -R ref.fa -I rg.bam -L chr20 -O linear.vcf.gz \
  --native-pair-hmm-threads 8
```

To measure the discovery gap, normalize both callsets identically and intersect:

```bash
for v in graph linear; do
  bcftools norm -f ref.fa -m- $v.vcf.gz | bcftools norm -d exact -Oz -o $v.norm.vcf.gz
  bcftools index -t $v.norm.vcf.gz
done
bcftools isec -p isec graph.norm.vcf.gz linear.norm.vcf.gz
# isec/0000 = graph-only, 0001 = linear-only, 0002 = shared
```

The linear-only pile is the discovery gap. To prove the graph could never have emitted those, enumerate the panel's own variation and subtract it:

```bash
vg deconstruct -p CHM13#0#chr20 -r graph.snarls graph.gbz > panel.vcf
# then bcftools isec the linear-only set against panel.vcf;
# the part absent from the panel is the true representation gap
```

For me that was 98.9 percent. The graph was not failing to genotype those variants. It had no way to represent them.

## Recipe 4: structural variants, done with the right tool

This is the part I got wrong first, so learn from it. **GATK HaplotypeCaller is not a structural variant caller.** It does local assembly in small windows and emits nothing past a few hundred base pairs. If you compare a graph's structural alleles against HaplotypeCaller, you are comparing against a tool that physically cannot make the calls. Use a real SV caller.

For short reads that is Delly, and you want it on a properly paired alignment, not the surjected BAM, because surjection without read pairing strips the paired-end signal Delly depends on. Align your reads with bwa-mem2 and run Delly against that:

```bash
# Delly is not packaged for macOS arm64, so build it:
git clone --recursive https://github.com/dellytools/delly.git && cd delly
make all          # needs boost + htslib; on Homebrew add -I/opt/homebrew/include

delly call -g ref.fa -o sv.bcf properly_aligned.bam
bcftools view -f PASS sv.bcf | grep SVTYPE | ...   # DEL, DUP, INS, INV, BND
```

If you have HiFi, sniffles is trivial to set up and is the truth set worth having:

```bash
pip install sniffles
sniffles --input hifi.bam --vcf hifi_sv.vcf.gz --reference ref.fa \
  --minsupport 2 --minsvlen 50 --threads 8
```

Then a few lines of Python with interval overlap tells you how much each method recovers of the long-read truth. In my data the graph recovered around 80 percent of HiFi-validated SVs and short-read Delly around a quarter, and the gap got wider in segmental duplications. One caveat worth stating in your own writeup: low-coverage HiFi confirms that a variant is present but cannot prove one is absent, so it measures sensitivity, not precision.

## Recipe 5: discovery without leaving the graph

If you would rather not surject, you can fold the reads' novel variation into the graph and then genotype it. Confine it to one chromosome or it is enormous.

```bash
vg chunk -x graph.gbz -C -p CHM13#0#chr20 > sub.vg     # the chr20 component
vg filter aln.gam -N read_names.txt -t 16 > sub.gam    # just the chr20 reads
vg augment -s sub.vg sub.gam -m 3 -A aug.gam > aug.vg  # add novel edits
vg pack -x aug.vg -g aug.gam -o aug.pack
vg snarls aug.vg > aug.snarls
vg call aug.vg -k aug.pack -r aug.snarls -s MYSAMPLE > aug.vcf
```

After augmentation the variation the reads carry is now in the graph, so `vg call` can genotype it. For my sample this recovered the Y terminal that genotype-only calling missed. It also adds some spurious edges in repeats, so do not trust it blindly there.

## Gotchas, the expensive kind

These each cost me time. They are worth a paragraph.

- **A genotype-only graph VCF is not a complete catalog.** `vg call` reports only what is in the graph. An absent record could mean reference match, no coverage, or allele-not-in-graph, and you cannot tell which. Never treat it as discovery.
- **CHM13v2.0's chrY is HG002's Y, which is haplogroup J.** So the reference allele on the Y is not universally ancestral. Get ancestral versus derived from the tree, never from "is this the reference base."
- **mtDNA is special.** CHM13's mitochondrion is not the rCRS that every mtDNA haplogroup tool expects. Use the analysis-set reference that carries rCRS, and go through PhyloTree / HaploGrep, not the graph.
- **CRAM is strict.** A CRAM only decodes against the exact reference it was aligned to (MD5 is checked) and needs a `.crai`. A reference extracted from a GBZ can differ from the published FASTA in masking or case, which is enough to break CRAM decode. Keep references consistent within a comparison.
- **Surjection drops pairing.** `vg surject` without `-i` gives you single-end-looking reads. Fine for a pileup, useless for paired-end SV calling. For SVs, use a real paired alignment.
- **Normalize before you compare.** `bcftools norm -m- -f ref` (split multiallelics, left-align) on both callsets, or your intersection counts are fiction.
- **Pick the right Y reference for short reads.** A pseudoautosomal-masked Y avoids a class of X/Y multi-mapping artifacts.

## The runtime reality

The expensive steps are the ones that read the whole alignment file: pack, surject, and filtering reads out of a multi-hundred-gigabyte GAM. Each is roughly an hour on sixteen cores for a 30x genome, and you want a few hundred gigabytes of scratch or a fast NAS. The per-chromosome work after that (GATK on one chromosome, Delly, sniffles, the comparisons) is minutes to under an hour. None of it needs a cluster, which is the whole appeal.

If you run this on your own data and get a different answer than I did, I want to hear about it. That is the point of writing the commands down.
