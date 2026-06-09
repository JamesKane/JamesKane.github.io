---
layout: post
title:  "Finding a Y Haplogroup in a Pangenome (and Why It Almost Didn't Work)"
date:   2026-06-09 07:00:00 -0500
categories: ["genomics"]
tags: ["human pangenome", "Y-DNA", "haplogroup", "vg", "surjection", "decodingus"]
excerpt: "I tried to read a Y-DNA haplogroup straight out of a personal pangenome alignment. It got me most of the way, then quietly lied to me. Here is what went wrong, why, and the three different ways I eventually got the right answer."
---

# Finding a Y Haplogroup in a Pangenome (and Why It Almost Didn't Work)

A while back I [built a pipeline against the draft human pangenome](/genomics/2025/06/08/Human-Pangenome-Reference-Experiments.html) and aligned my usual test library to it. That library is WGS229 from yseq.net, the same mixed-European R1b donor I have been using since the [Orange Pi experiments](/genomics/2025/04/19/Personal-Genomics-on-an-Orange-Pi-5-Plus.html). This time I built a small *personal* pangenome from eight phased assemblies plus the T2T-CHM13 reference, aligned the WGS229 short reads together with a HiFi library to that graph with `vg giraffe`, and called variants with `vg call`. The result was a clean VCF in CHM13 coordinates: 4.26 million variants, Ts/Tv of 1.94, nothing alarming.

Then I asked what felt like a simple question. The donor's terminal Y haplogroup is independently known to be R1b-FGC29071. Could I recover that from the pangenome callset alone, using the public [Decoding Us](https://decoding-us.com) Y tree as the phylogeny?

The short version: the graph got me confidently into R1b, then it stopped resolving, and a naive reading of the data actively pointed me at the wrong branch. Getting the real answer took a more careful algorithm and, ultimately, leaving the graph. The interesting part is *why*, because the reason is not specific to the Y chromosome.

## The reference has a twist

The personal pangenome uses T2T-CHM13 as its reference path, which matters more than I expected. CHM13 is a near-complete assembly, but it has no Y chromosome of its own. The chrY in CHM13v2.0 comes from HG002, the well known Genome in a Bottle sample. HG002 is Y haplogroup J, not R.

So the reference I called against sits on a completely different major branch of the Y tree than my donor. That single fact explains the shape of everything that follows. Where my R sample and the J reference share ancient ancestry, the sample matches the reference and produces no variant record. Where the R lineage carries mutations that J does not, the sample shows a variant. The boundary between those two regimes is exactly where the story gets interesting.

## The Decoding Us Y tree, and how to read it against a VCF

The Decoding Us API exposes the Y phylogeny at `/api/v1/y-tree`. It returns 2,695 nodes, each with a parent, a list of defining variants, and per-variant coordinates in three assemblies: GRCh37, GRCh38, and hs1. That last one, hs1, is T2T-CHM13v2.0, which is exactly the coordinate system of my VCF. Each variant also carries its ancestral and derived alleles. As a spot check, the marker FGC29071 lands at hs1 chrY:15,570,629, an A to C change, and the reference base there really is A. The coordinates line up.

The method writes itself. For every node in the tree, look at each defining SNP, find the donor's allele at that position, and classify it:

* the VCF has a variant whose alternate allele equals the derived base: positive evidence (call it a derived call)
* the VCF has a variant whose alternate allele equals the ancestral base: a contradiction
* the VCF has no record, and the reference base equals the derived base: consistent, via reference match (this is the ancient backbone shared with the J reference)
* the VCF has no record, and the reference base equals the ancestral base: ambiguous

That last case is the trap, and I want to flag it early. A sites-only VCF cannot tell the difference between "the sample matches the reference here" and "there was no coverage here." Both look like an absent record. I treat an absent record as no data, never as ancestral, which turns out to be the only safe choice.

## First run: confident, then quietly wrong

Walking the tree from the root, the donor places cleanly and correctly down through the R1b backbone. The path runs through CT, F, K, P, R, R1, R1b, and on toward R1b-P312, accumulating hundreds of derived calls with essentially no contradictions. So far so good. This is a confident R1b assignment, and it is right.

Then it falls apart. My first, naive scoring picked the deepest node with the most accumulated derived evidence, and that node was **R1b-BY66412**. The true answer, R1b-FGC29071, sits on a different sub-branch. The two share a common ancestor at R1b-FGC11134 and diverge right below it.

When I looked at why BY66412 won, the "evidence" was garbage. Of that node's roughly sixty-five defining SNPs, almost all were uncalled. The handful of calls that existed were four "SNPs" packed into a 96 base pair window around chrY:11.95 Mb, all genotyped 1/1, plus one outright contradiction nearby. That is the textbook signature of paralogous reads collapsing onto one location in a repetitive region. The caller had been seduced by a mapping artifact.

Meanwhile the true path below FGC11134, the sixteen nodes leading down through CTS4466 to FGC29071, had essentially no called markers at all. The terminal markers live in the repeat-rich distal part of the Y, and in the graph callset that region is a desert dotted with the occasional mirage.

## Why the graph goes blind

Two things are happening at once, and they compound.

The first is representation. `vg call`, run as a genotyper, can only report variation that already exists in the graph as nodes and edges, which means variation carried by one of the panel assemblies. My donor's terminal lineage simply is not in the panel. I confirmed this directly: of the eight assemblies, the only R1b Y belongs to HG01243, which is R1b-DF27. DF27 and my donor's L21 lineage are siblings that split at P312, which is precisely where the clean resolution stopped. There is no panel haplotype anywhere on the donor's L21 to DF13 to FGC11134 to FGC29071 path, so those alleles are not edges in the graph, so the genotyper cannot emit them. Not "did not." Cannot.

The second is the loops. The palindromes and ampliconic repeats of the distal Y become cycles in the graph. Reads multi-map, alignments become ambiguous, and `vg call` produces a mix of missing calls and tightly clustered false positives. The terminal Y markers happen to live right in that mess.

I want to be precise about the failure mode, because it is worse than it first appears. The omission is silent. An absent record in the VCF could mean the sample matches the reference, or that the allele is not in the graph, or that there was no coverage. Three very different situations, collapsed into one indistinguishable blank. A linear reference with a normal caller at least gives you an explicit reference call with a depth, or an honest no-call. The graph genotyper, used this way, hands you a callset that looks complete and is not, and gives you no signal about what it left out.

## A more resilient caller

The naive "deepest node with the most derived evidence" rule was never going to survive contact with that 96 base pair artifact. The Y phylogenetics literature solved this years ago, in tools like [yhaplo](https://github.com/23andMe/yhaplo), [pathPhynder](https://github.com/ruidlpm/pathPhynder), and [Yleaf](https://github.com/genid/Yleaf). The common idea is to follow a *supported path* down the tree rather than chase the single deepest derived marker.

I rewrote my placement to do three things:

* **Gate.** Only step into a child branch that carries net positive derived support at the branch itself. This forbids tunneling through unsupported branches, so an isolated deep artifact, which you can only reach by passing through the unsupported branches above it, is never reached.
* **Route.** Among the branches that do pass the gate, descend toward the one whose subtree holds the most positive evidence. This keeps the ancient backbone on track even where an intermediate node is only weakly supported but clearly leads to the signal-rich part of the tree.
* **Report.** Take the deepest node with genuine variant evidence and trim any reference-match-only tail, so a single coincidental reference match cannot stretch a terminal call.

There was one more wrinkle worth mentioning, because it cost me an hour and turned out to be a clean idea. Some tree nodes, including R1b-A353 on my donor's path, are defined entirely by insertions and deletions rather than SNPs. A SNP-based caller sees them as empty and the strict gate refuses to traverse them. The fix is structural: collapse any node with no usable SNP markers and re-parent its children to the nearest informative ancestor, recursively. It is sample independent, so it stays safe on sparse data.

With that, the graph VCF resolves honestly to R1b-P312 and refuses to guess deeper. That is the correct answer for what the graph actually contains. It is not the terminal, but it is not a lie either.

## Leaving the graph: surjection

If the graph cannot represent the donor's terminal alleles, the obvious move is to stop asking the graph. `vg surject` projects the graph alignments back onto the linear CHM13 reference, giving an ordinary BAM. A pileup on that BAM can call any allele the reads carry, regardless of whether it was ever in the graph.

This is the payoff. At FGC29071, chrY:15,570,629, the graph VCF had no record. The surjected pileup shows eleven reads, all eleven carrying C, the derived allele. The marker was never missing from the data. It was missing from the graph.

I ran the same path-supported placement over the pileup genotypes, with quality and allele-balance filters, and added a small allowance for a lone contradicting call when the surrounding evidence overwhelms it (one such artifact sits at chrY:21.9 Mb, again in a repeat). The donor resolves to **R1b-FGC29071**. Fully. The exact known terminal.

## Were there better snarls hiding in the panel?

Before declaring surjection necessary, I checked whether any panel male sat closer to the donor's branch, in which case the graph would already carry usable snarls. All eight samples are male, so I placed each one two ways: from the graph directly, and independently from their linear CHM13 short-read CRAMs.

| Sample | from the graph | from the CRAM |
|--------|----------------|---------------|
| HG00126 | R1b-S227 | R1b-BY65673 |
| NA20752 | R1b-S227 | R1b-P312 |
| HG01243 | R1b-DF27 | R1b-FT51793 |
| HG00140 | I1 | I1b-S249 |
| NA20762 | I1 | I1a-BY383 |
| HG00290 | K-M526 | N-Z19831 |
| HG01530 | K | T-FT327096 |
| HG002 | J1a-ZS2712 | (it is the reference) |

The three R1b males all branch off at P312. None is on the donor's L21 lineage, none is at or below FGC11134. So the graph genuinely holds nothing to substitute for the donor's terminal path, and surjection was both necessary and sufficient.

The cross-check also handed me a nice illustration of the original problem. The two samples that the graph could only resolve to a basal "K" turned out, from their reads, to be haplogroup N (a Finnish sample) and T. The graph under-resolved them by entire major branches, for the same reason it under-resolved my donor: their deep lineages are sparsely represented. The linear reads were consistently deeper and more correct than the graph deconstruction.

## Staying in the graph: augmentation

There is a second way to recover the terminal that does not abandon the graph. `vg augment` folds the reads' novel variation into the graph as new nodes and edges, after which `vg call` can genotype it. I confined this to chrY for tractability: pull the chrY component out of the graph, filter the alignments down to the chrY reads, augment, then pack, snarl, and call.

Augmentation grew the chrY subgraph from about 176,000 nodes to about 395,000, and the resulting callset jumped from roughly 14,000 chrY variants to 46,000. Running the placement on that augmented VCF, in strict mode this time, gives **R1b-FGC29071**. The donor's lineage, once added to the graph, is genotyped natively.

It is not free. Augmentation also injects spurious edges in the repeat regions, and the caller flagged ambiguous branching at a couple of nodes. The subtree routing picked the correct branch each time, but the noise is real, and I would not trust raw augmented calls in the distal Y without the path logic guarding them.

## Three answers, one donor

Here is the whole experiment in one table.

| Approach | Result |
|----------|--------|
| `vg call`, genotype only | R1b-P312, then blind (a naive reader is lured to R1b-BY66412) |
| surject to linear, then pileup | R1b-FGC29071 |
| `vg augment`, then `vg call` | R1b-FGC29071 |

Both ways of *discovering* variation, leaving the graph or extending it, land on the right terminal. The genotype-only path does not, and cannot, because the lineage was never in the panel.

## The part that is not about the Y chromosome

It would be easy to file this under "the Y is hard," which is true but misses the point. The real lesson is general.

A genotype-only pangenome callset is a panel-conditioned genotyping result wearing the costume of a variant catalog. Anything private to your sample, anything not carried by one of the assemblies that built the graph, is invisible, and invisible silently. My donor's FGC29071 is a trivial, well-covered SNP that any linear caller would have emitted without a second thought. The graph could not, and said nothing about the omission. That is genome-wide, not a Y quirk. It bites rare and private variants everywhere.

So is the pangenome worse than a plain linear reference? For this specific job, novel-variant discovery with a genotype-only caller, honestly yes, and the silent failure makes it worse still. But that is the wrong conclusion to draw, because it is a tool-usage error, not a property of pangenomes. Genotype-only `vg call` is a genotyper, not a discovery caller. The standard pangenome discovery pipeline maps to the graph and then surjects to linear for calling with something like DeepVariant, precisely to avoid this. That surjection step is the same fallback I reached for here. For everything the graph does represent, it beats the linear reference, with less reference-allele bias and better behavior around indels and structural variation.

The honest framing is a trade, not a verdict. You swap the linear reference's allele bias for the pangenome's panel-representation bias. The pangenome wins for genotyping known and common variation across diverse ancestries. It loses, quietly, for discovering what is rare or private, unless you surject or augment. The mistake is treating a genotype-only graph VCF as the complete truth.

My donor is R1b-FGC29071. The reads always knew it. I just had to stop expecting the graph to tell me on its own.
