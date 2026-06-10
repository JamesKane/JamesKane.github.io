---
layout: post
title:  "Building a Y and mtDNA Tree From Scratch (Work in Progress)"
date:   2026-06-30 07:00:00 -0500
categories: ["genomics"]
tags: ["Y-DNA", "mtDNA", "haplogroup", "phylogenetics", "GATK", "iqtree", "CHM13", "WIP"]
excerpt: "The last few posts placed a single sample onto a tree that already existed. This one goes the other direction: a local pipeline that calls chrY and mtDNA across many genomes, builds the phylogeny itself, roots it on a chimp outgroup, and reads the branch-defining mutations straight off the tree. It runs end to end on a pilot cohort; these are the working notes before the full-scale run."
---

# Building a Y and mtDNA Tree From Scratch (Work in Progress)

Everything I have written about haplogroups so far has been about *placement*: take one genome, walk an existing tree, find the branch it belongs on. The [pangenome posts](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html) did it against the Decoding Us tree, and the [crowdsourcing post](/genomics/2025/12/06/crowdsourcing-the-haplogroup-tree.html) was about how that tree grows when many people contribute. But the tree has to come from somewhere. At some point you stop reading the map and start drawing it.

This post is the other direction. It is a local pipeline that calls the Y chromosome and the mitochondrion across a set of genomes, builds a phylogeny *de novo* without leaning on any pre-existing tree, roots it against a chimp outgroup, and then reads the mutations that define each branch back off the reconstructed tree. It is honestly labeled work in progress: the whole chain runs end to end on a small pilot cohort, but I have not turned it loose on the full sample set yet, and the last two stages (the tree inference and the ancestral reconstruction) are freshly written and still earning my trust. So these are the bench notes for a thing that is mostly built but not yet proven at scale. Consider it the upstream counterpart to the crowdsourcing idea, the part that produces the raw branches a curator would later name.

As always, it runs on one workstation. Mine is a Mac Studio with the CRAMs sitting on a NAS, same as the [pangenome bench](/genomics/2026/06/23/try-it-yourself-a-pangenome-variant-calling-bench.html). Nothing leaves the house.

## The shape of the problem

A Y or mtDNA phylogeny is a particularly friendly tree to build, for one reason: both are haploid and neither recombines. You inherit your father's Y essentially verbatim and your mother's mitochondrion essentially verbatim, mutation by mutation, generation after generation. That means the variants line up into a clean nested hierarchy, and a standard phylogenetics tool can recover it without any of the phasing gymnastics autosomes demand.

The catch is everything around the calling. You have to call haploid, you have to be honest about which positions you could actually see, and you have to keep the diploid pseudoautosomal regions of the Y out of it. Get those wrong and the tree is built on sand.

I split the work into a chain of idempotent stages, each a small shell script sourcing a shared `lib.sh`: set up the references and manifest, call per sample, joint-genotype, build the callability mask, build the alignments, add a chimp outgroup, then infer the tree and reconstruct ancestral states. A `run_all.sh` chains them, and any stage can be re-run on its own. The plumbing is deliberately boring; the interesting decisions are in the parameters and in the last two stages.

## Where the samples come from

The input is whole-genome CRAMs I already have, aligned to T2T-CHM13v2.0. The pilot pulls from two public reference collections on the NAS, the [1000 Genomes Project](https://www.internationalgenome.org/) 30x high-coverage set and the [HGDP](https://www.internationalgenome.org/data-portal/data-collection/hgdp), plus my own genome. More collections will get added later; this is just enough to shake the pipeline out:

```bash
PROJECTS=(
  /Volumes/nas/Genomics/PRJEB9586
  /Volumes/nas/Genomics/PRJEB31736
  /Volumes/nas/Genomics/PRJEB36890
  /Volumes/nas/Genomics/mine/WGS229
)
```

Stage 0 walks those roots, finds the CHM13-aligned CRAMs (and only those; it explicitly skips anything tagged `b38`, `hg38`, `grch38`, and friends, because mixing coordinate systems is how you lose a day), reads the sample name out of the `@RG SM` tag, and writes a manifest. The same CHM13 coordinate discipline from the pangenome work applies here: one reference, no exceptions. A scan across thousands of public CRAMs hits a few that are truncated, missing an index, or downloaded as empty placeholders, so each one is quickcheck'd before it goes in the manifest and the casualties get parked in a `problem_samples.tsv` rather than aborting the whole scan. That bookkeeping is unglamorous and absolutely necessary the first time one bad file forty samples deep kills an hour-long run.

It also decides each sample's sex, because that determines whether the Y gets called at all. There is no need for a separate karyotype file when the coverage tells you directly. The ratio of chrY mean depth to autosomal mean depth is bimodal and obvious:

```bash
sex_of() {
  # "male" if chrY meandepth / mean(chr1..22 meandepth) >= threshold (0.15)
  ...
}
```

A real male sits near 0.5; a female sits near zero from the handful of mismapped reads. A threshold of 0.15 splits them with room to spare. Coverage gets generated on demand and cached next to each CRAM, so the second run is instant.

## Calling haploid, and only where it counts

Two reference details drive the calling intervals. First, CHM13's mitochondrion is not the rCRS that downstream mtDNA tools expect, which I will come back to. Second, and more immediately, the Y chromosome has pseudoautosomal regions that recombine with the X and are genuinely diploid. Calling those at ploidy 1 would be nonsense, so they are excluded up front:

```bash
# chrY non-PAR (PAR1/PAR2 from chm13v2.0_PAR.bed removed)
printf 'chrY\t2458320\t62122809\n' > "$CHRY_NONPAR_BED"
```

Per sample, stage 1 slices just the chrY and chrM reads into a small local BAM (decode the CRAM once, then stop touching it), and runs GATK HaplotypeCaller at `--sample-ploidy 1` in GVCF mode. Every sample gets chrM; only males get chrY non-PAR. Alongside that it runs `CallableLoci` to record, explicitly, which positions had enough depth and mapping quality to call at all:

```bash
gatk HaplotypeCaller -R "$REF" -I "$bam" -L "$CHRY_NONPAR_BED" \
  --sample-ploidy 1 -ERC GVCF --native-pair-hmm-threads 4 \
  --minimum-mapping-quality 20 -O "$s.chrY.g.vcf.gz"

gatk CallableLoci -R "$REF" -I "$bam" -L "$CHRY_NONPAR_BED" \
  --min-depth 4 --min-mapping-quality 20 --format BED \
  -O "$s.chrY.callable.bed" --summary "$s.chrY.callable.sum"
```

That callable BED is not an afterthought. It is the thing that lets the pipeline tell "this sample matches the reference here" apart from "I never saw this position," which was exactly the distinction the graph genotyper [could not give me](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html) in the last experiment. Building a tree without it would quietly turn missing data into false agreement. The GVCFs and the callable BED get archived next to the source CRAM so the expensive per-sample step never has to repeat, and stage 1 fans the whole manifest out across cores with GNU `parallel`.

## Joint genotyping, then a callability mask

Stage 2 is the GATK joint-calling pattern, adapted for haploids. It builds a GenomicsDB workspace from the per-sample GVCFs (every sample for chrM, males only for chrY), runs `GenotypeGVCFs` at ploidy 1, and applies the usual hard filters (QD, FS, MQ, SOR). Nothing exotic; the ploidy is the only thing that makes it unusual.

Stage 3 is the part I care most about getting right. The method borrows from how the 1000 Genomes Y chromosome work (Poznik and colleagues) defined a trustworthy region, but the output is a new mask, built fresh for CHM13v2. The widely used Poznik mask is in hg19 coordinates, and CHM13 being a far more complete assembly has a lot of Y sequence that mask never had an opinion about. Lifting an hg19 mask over and hoping is exactly the kind of coordinate laundering that bites you, so the cleaner move is to recompute callability directly on the cohort I am actually calling. A site is only allowed into the tree if it was *callable in at least 90 percent of the relevant samples*. For chrY that means 90 percent of males; for chrM, 90 percent of everyone. The trick is a per-base count of how many samples were callable at each position, done with `bedtools genomecov` over the concatenated callable intervals:

```bash
# keep positions CALLABLE in >= ceil(0.90 * N) samples
bedtools genomecov -bga -i callable.sorted.bed -g "$GENOME_FILE" \
  | awk -v t="$thr" '$4>=t {print $1,$2,$3}' \
  | bedtools merge -i - > mask.bed
```

The point of the mask is that a phylogeny is only as honest as its weakest column. A site that one sample could call and forty could not contributes mostly noise and missing data. Restricting to broadly callable positions trades a little sensitivity for branches you can actually trust, which is the right trade when the output is a tree other people might build on.

## Two chromosomes, two representations

Stage 4 turns the joint callset plus the mask into alignment files, and here the Y and the mitochondrion want different shapes. This is the stage I got most wrong on the first pass, so it is worth being precise.

The Y becomes a SNP matrix: a relaxed-PHYLIP alignment where each sample is a row and each variable site is one column. My first instinct was to keep only biallelic SNPs and encode them the obvious way, genotype `0` as the reference base and `1` as the alternate. That is wrong in two ways. First, throwing away multiallelic sites discards real signal. A Y position where three different lineages carry three different bases is one of the most phylogenetically informative columns you can have, and a maximum-likelihood model under GTR handles it natively. So the matrix keeps multiallelic SNP sites and decodes each sample's allele *index* to its actual base rather than to a 0/1:

```python
# each sample's haploid genotype is an allele index into [REF, ALT1, ALT2, ...]
tok = cell.split(":", 1)[0].replace("|", "/").split("/")[0]
a = alleles[int(tok)] if tok.isdigit() else ""
col.append(a.upper() if is_base(a) else "N")   # indel / spanning-del / missing -> N
```

Second, I have to be careful at sites that mix a SNP and an indel. GATK can emit those as one `MIXED` record, and if I select only `SNP` type I lose the SNP allele entirely. So selection keeps `SNP` and `MIXED`, and the decoder turns any allele that is not a single base (an indel, a spanning-deletion `*`, a missing call) into `N`, because a multi-base allele cannot occupy a single fixed-width alignment column. Finally, every column that comes out monomorphic after that decoding gets dropped. That last step is not cosmetic: the tree is inferred under an ascertainment-bias-corrected model (`GTR+ASC`), and ASC *requires* that the alignment contain only variable sites. Leave an invariant column in and IQ-TREE refuses to run.

The mitochondrion takes the other shape, a full-length consensus FASTA, one 16,569-base sequence per sample, because at that size you can afford to carry every position. But it is also SNP-only, and for a different reason than the Y: indels would change each sample's length and break the alignment, and by long-standing convention the mt poly-C tracts and other length-variable sites are excluded from phylogenetic analysis anyway. Each sample's consensus is then N-masked exactly where *that sample* was not callable, using `bcftools consensus` with a per-sample non-callable mask, so a low-coverage stretch in one sample does not masquerade as agreement with the reference.

## Rooting it: a chimp outgroup

An unrooted tree tells you who is related to whom but not which direction time runs. For a Y or mtDNA tree that matters enormously, because the whole point is to recover the *order* of mutations from the root of humanity down to the tips. And here the reference bites back: CHM13's chrY is HG002, a haplogroup-J Y, so "matches the reference" emphatically does not mean "ancestral." I cannot root on the reference.

The clean answer is an outgroup. Stage 4.5 takes a high-quality chimpanzee Y assembly, aligns it to CHM13 with `minimap2 -ax asm20` so it lands on its best human homolog, and projects it into CHM13 chrY coordinates with `samtools consensus -a`, giving one chimp base per chrY position. Then it reads the chimp allele at every SNP site the alignment stage emitted. That gives two things, and the pipeline supports using either:

- a per-site polariser: for each SNP, the chimp allele is the ancestral state, so I know which direction is derived independent of the tree's shape; and
- an outgroup taxon: a `CHIMP` row appended to the PHYLIP, so IQ-TREE can place the root on the branch leading to it.

The two are not equally safe. Adding chimp as a taxon is simplest, but the chimp Y is distant enough that its very long branch can drag the rooting around through long-branch attraction. So the recommended mode builds the tree from the human samples only, keeping the ingroup topology clean, and uses the chimp track purely to polarise. The chimp alignment only covers a fraction of the SNP sites, which is expected across that much evolutionary distance, and the stage reports exactly what fraction landed so I am not guessing about coverage.

## The tree, and reading the mutations off it

This is the stage that did not exist when I first sketched this pipeline, and it is the one that turns a pile of variant calls into something a person would recognize as a haplogroup tree.

Stage 5 hands the SNP PHYLIP to [IQ-TREE](http://www.iqtree.org/) under `GTR+ASC`, with ultrafast bootstrap if asked, and infers the maximum-likelihood tree. That alone gives the topology. But a topology with anonymous internal nodes is not yet a haplogroup tree. What makes the Y tree useful is that every branch is *labeled by the mutations that define it*, the way ISOGG and the Decoding Us tree name a branch by markers like P312 or FGC29071. To get there I run IQ-TREE's marginal ancestral state reconstruction (`--ancestral`), which estimates the most likely base at every internal node, and then walk the rooted tree comparing each parent to each child:

```
for each rooted parent -> child branch:
  for each site:
    if parent_base and child_base are both ACGT and differ:
      record  chrY:pos  ancestral_base > derived_base  on this branch
```

The result is an ISOGG-style map: one table of branches, each carrying the list of SNPs that mutate along it, and a companion table with one row per (branch, mutation) in chrY coordinates. Cross-referenced against the chimp polariser, each mutation is tagged as a clean forward mutation, a subsequent mutation, or a reversion back toward the ancestral allele, and reversions get counted per branch because a branch thick with them usually means a mapping artifact rather than real history. That branch-to-SNP table is the actual deliverable. It is exactly the form the [crowdsourcing pipeline](/genomics/2025/12/06/crowdsourcing-the-haplogroup-tree.html) consumes: candidate branches, each defined by a concrete set of positions and ancestral-to-derived calls.

One nice property of doing it this way: the defining markers are *derived*, not assumed. I am not handing the tree a list of known SNPs and asking where they fit. The mutations fall out of the reconstruction, so the method can name a branch nobody has named before, which is the entire reason for building a tree from scratch instead of placing onto an existing one.

## What I expect to go wrong

I would rather flag the landmines now than discover them in the tree.

- **Long-branch attraction from the outgroup.** Rooting on the chimp Y is the right idea but the wrong knob if I treat chimp as a taxon, because its branch is long enough to distort the ingroup. The polarise-only mode sidesteps this, and it is why that is the recommended path, but I want to confirm the auto-chosen root agrees with what I know about the deepest human Y splits before I trust it.
- **The distal Y is a swamp.** Palindromes and ampliconic repeats produce paralogous mapping, which is precisely the artifact that put four fake SNPs in a 96 bp window last time. The 90 percent callability mask should evict most of that region automatically, since paralogous positions tend not to be cleanly callable across the whole cohort, and the per-branch reversion count gives a second line of defense, since a branch full of back-mutations is usually paralogy rather than history. I still want to confirm the mask does the evicting rather than just assume it.
- **Ascertainment bias is easy to get half-right.** Feeding a SNP-only matrix to a model that expects whole-genome composition inflates branch lengths, which is why the tree uses `GTR+ASC`. But ASC corrects for the *count* of invariant sites it cannot see, and on a masked Y that count is itself an estimate. The branch *topology* is robust; the branch *lengths* deserve a skeptical eye.
- **CHM13's mitochondrion is not rCRS.** Anything I hand to a conventional mtDNA haplogroup tool will need translating to rCRS coordinates first. For an internal de novo tree it does not matter, since every sample shares the same CHM13 frame, but the moment I want to compare against PhyloTree it does.
- **Sample provenance and duplicates.** The two public collections plus my own genome may overlap, and a duplicated sample shows up as a zero-length branch that looks like a discovery and is not. The manifest is `sort -u`'d on every field, but identity is by name, not by content, so true duplicates under different names would slip through.

## Where this is going

The endgame is not a single tree of my few dozen pilot samples. It is the upstream half of the [crowdsourcing pipeline](/genomics/2025/12/06/crowdsourcing-the-haplogroup-tree.html): a repeatable, local, privacy-preserving way to go from raw CRAMs to honest haploid variant calls, a defensible callability mask, a rooted tree, and a branch-to-SNP table, which is exactly the substrate a consensus engine needs to propose new branches. Place a sample on the existing tree, yes, but also be able to extend the tree when the existing one runs out, the way it [ran out below R1b-P312](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html) for my own donor.

The machinery now runs all the way through on the pilot. What is left is the part that actually matters: turning it loose on the full sample set, checking the rooted topology against the deep splits we already know, and seeing whether the branch-defining SNPs it derives line up with the published markers where they should and propose something genuinely new where they can. Next post should have a real tree in it, plus whatever the five landmines above turn into at scale. If you build something similar and your callability mask or your rooting behaves differently than mine, I want to hear about it.
