---
layout: post
title:  "The Branches That Don't Lift: Why Some Clades Left the CHM13 Tree (For Now)"
date:   2026-06-30 07:00:00 -0500
categories: ["genomics"]
tags: ["Y-DNA", "haplogroup", "CHM13", "T2T", "liftover", "FTDNA", "pangenome", "decodingus", "coordinate integrity", "coalescence age", "callable loci"]
excerpt: "Moving the Y-haplotree onto the T2T-CHM13 reference means giving every legacy SNP a new address. Most lift cleanly. But in the most repetitive stretch of the Y, some markers have no honest CHM13 coordinate at all, so the clades they define are removed and their children promoted. This is why, why it is the right call, and why a pangenome will eventually give those branches back."
---

# The Branches That Don't Lift: Why Some Clades Left the CHM13 Tree (For Now)

If you have been watching your corner of the Decoding Us Y-tree, you may have noticed that a branch you know by name has gone quiet. The node is there, or it used to be, but the SNP that defines it (your `ZZ11`, your `M252`, or some `Z`-number you have memorized) is not listed against it anymore. In a few cases the whole clade has folded up into its parent. Nothing was lost from your DNA and nothing was decided about your ancestry. What changed is the *coordinate system the tree lives in*, and a SNP that cannot be given an honest address in the new system cannot be allowed to define a branch in it. This post is the accounting of why.

It is a companion to the [tree-from-scratch](/genomics/2026/06/30/building-a-y-and-mt-tree-from-scratch.html) and [crowdsourcing](/genomics/2025/12/06/crowdsourcing-the-haplogroup-tree.html) posts. Those were about how branches get *born*. This one is about the much less glamorous business of moving the existing tree to a better reference without quietly corrupting it along the way.

## The move that started it

The legacy Y-haplotree, the one the community has built up over a decade, the FTDNA-style scaffold of named clades, is anchored in **GRCh38** coordinates. The Decoding Us tree is anchored in **T2T-CHM13v2.0**, the first genuinely complete human assembly, the one that finally has an opinion about the satellite-and-amplicon jungle of the Y where the older references just gave up. I have written before about [what a pangenome and a complete reference buy you](/genomics/2026/06/16/what-a-pangenome-misses-and-what-it-nails.html); the short version is that CHM13 is simply a better map of the Y, and the whole project runs on one rule: **one coordinate system, no exceptions.** Mixing GRCh38 and CHM13 positions in the same file is how you lose a day, or worse, ship a wrong answer that looks right.

So every defining SNP on the legacy tree has to be *lifted* from GRCh38 to CHM13: same physical mutation, new address. A clade defined by `A9005` at GRCh38 `chrY:21,045,063` has a perfectly good CHM13 home at `chrY:21,905,878`; the lift just moves the address and the tree carries on. Multiply by roughly 800,000 marker positions and you have the migration.

Most of them lift fine. The ones that matter for this post fail for a single stubborn reason, and it is not the SNP's fault: in the most repetitive stretch of the Y, there is simply no honest CHM13 address to move them to.

## When a SNP has no address

Some markers genuinely **have no CHM13 coordinate at all.** Not a wrong one, not a hard-to-find one: none.

`ZZ11_1`, the name the coordinate dictionaries give the marker most people know as `ZZ11`, is the poster child. Its GRCh38 position, `chrY:20,124,913`, falls inside a roughly 200 kb stretch (`chrY:20,060,815`–`20,257,799` in GRCh38 terms) that does not align to CHM13 anywhere. Not flipped, not moved, not renamed: *not present as a one-to-one correspondence.* This is the heart of the ampliconic Y, the palindromes, segmental duplications, and satellite repeats where "the position" is not even a well-posed question. Because the sequence exists in several near-identical copies, a single linear-to-linear alignment cannot honestly say which copy your SNP is on. `M252`, `DF83`, and roughly fifteen thousand other markers live in this same un-mappable country.

I went looking for a rescue. I checked whether the public coordinate browsers had a CHM13 position these markers were hiding; they did not. I checked the production Decoding Us data; it did not. What these markers reliably have is their legacy GRCh38 address, the one the source tree was built on. Some also carry an older GRCh37 coordinate and many do not, which is its own small tangle I have left to the aside below. What none of them has, as of today, is an honest T2T one. They are, for now, lost.

## Why "lost" means "removed," not "pretended"

Here is the decision that this whole post exists to explain, and it is a deliberate one.

When a clade's *only* defining SNP cannot be lifted, the node is **removed from the CHM13 tree, and its children are promoted to its parent.** It does not linger as a named branch with an empty definition. It does not get to keep its old GRCh38 coordinate as a kind of placeholder. It is contracted out of the tree entirely.

That can feel harsh, so let me defend it. The Decoding Us tree is a CHM13 object. Every assertion in it should be checkable against the CHM13 reference; that is the entire point of picking one coordinate system and holding the line. A node whose defining mutation has no CHM13 address is an assertion you *cannot* check. Keeping it around with a borrowed GRCh38 coordinate would be coordinate laundering: a number that looks like a position but means nothing in the system it is sitting in, waiting for some future tool to read it literally and place a variant 800 kb from where it belongs. I would rather show you an honest gap than a confident fiction. A branch exists on this tree if, and only if, it has a mutation the tree can actually point to.

There is a concrete consequence behind that principle, and it is the one that actually forces the decision: **branch ages.** Decoding Us dates each branch with a coalescence-age model following Iain McDonald's work on Y haplogroup ages (McDonald, I. "Improved Models of Coalescence Ages of Y-DNA Haplogroups." *Genes* 2021, 12, 862, [doi:10.3390/genes12060862](https://doi.org/10.3390/genes12060862)), and that kind of model does not run on SNP counts alone. To turn a count of mutations on a branch into a number of years, you have to divide by how many base pairs those mutations could have been observed over: the *callable* region, the part of the Y that was confidently sequenced and genotyped across the samples on that branch. SNPs are the numerator, callable base pairs are the denominator, and the age is essentially the ratio scaled by a mutation rate.

That denominator is measured on CHM13, against the same [callable-loci mask the rest of the pipeline uses](/genomics/2026/06/30/building-a-y-and-mt-tree-from-scratch.html). A SNP with no CHM13 position has no place in that measurement, because there is no CHM13 locus at which to ask "was this callable, and in how many samples?" Keep it on the branch with a borrowed GRCh38 coordinate and you have added to the numerator without any matching contribution to the denominator, at a position whose callability you never measured. The age estimate does not just get fuzzier; it gets *wrong*, in a direction you cannot even characterize. Dropping the un-anchored SNP is what keeps the dating honest, because it keeps the mutation count and the callable-region length in the same coordinate frame. We need callable-loci metrics around every site that feeds the calculation, and a site with no CHM13 address is a site we cannot measure.

And the children do not fall off the planet. They move up to the nearest surviving ancestor: the closest clade that *does* have a real CHM13 definition. If the cohort genuinely splits where the vanished node used to be, that split has not disappeared; it is simply waiting to be re-expressed by a mutation we *can* place. The [de-novo tree builder](/genomics/2026/06/30/building-a-y-and-mt-tree-from-scratch.html) discovers exactly those mutations from the sequencing data directly, in CHM13 coordinates, with no legacy name required. A real branch with a real CHM13 marker will come back named by its evidence rather than by its history.

## This is a liftover limitation, not a biological one

The most important thing to say is that **nothing is wrong with these SNPs or these lineages.** `ZZ11`, `M252`, and their neighbors are perfectly good mutations marking perfectly real branches of the human Y. The lineages are not in doubt. What is missing is a *coordinate*, and the reason it is missing is that a liftover is a fundamentally limited instrument: it is a pairwise alignment between two single, linear genomes. Where one assembly has a region the other represents as several near-identical copies (precisely the ampliconic, palindromic heart of the Y), a linear-to-linear chain has no honest answer to give, so it gives none.

That is exactly the limitation a **pangenome** is built to dissolve. A graph reference does not force the repetitive Y into one linear track and then try to align across it; it represents the copies *as copies*, as parallel paths through the graph, so a marker that is genuinely ambiguous on a linear map can be placed on the specific path it belongs to. The same instinct runs through everything I have written in this series, from [finding a haplogroup in a pangenome](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html) to [what the graph nails and what it misses](/genomics/2026/06/16/what-a-pangenome-misses-and-what-it-nails.html): the structure a single reference flattens is the structure a graph keeps.

So the removal is explicitly provisional. When the Decoding Us pipeline grows a pangenome-aware placement stage, one that resolves these ampliconic positions against the graph instead of against a single linear CHM13 track, the markers that have no honest address today can get one, and the branches that folded up can be restored, defined this time by a coordinate the tree can actually verify. The gap on the tree is not a tombstone. It is a `TODO` with a known fix and a clear owner.

## An aside: the source data is its own adventure

Not every branch that looks missing is a coordinate problem. The legacy haplotree is a decade of community contribution layered on top of FTDNA's source data, and like any living, human-curated dataset it carries a few scars that have nothing to do with CHM13. They are worth a short detour, because when a branch goes quiet it helps to know which kind of missing you are looking at.

The common one is name drift. The source tree calls a marker `ZZ43`; the coordinate dictionaries call the exact same physical site `ZZ43_1`. Match the two by name and the lookup fails and the SNP drops, even though its position lifts without complaint. The fix is to stop trusting the string and trust the GRCh38 position the source already records; lifting that directly, and validating it against the CHM13 base, quietly brings back branches that were never really un-liftable, just mislabeled.

The rarer one is plain bad data: a handful of markers carry a source position of `-7`, or some other value that is not a coordinate at all. There is nothing to lift; you cannot reverse-engineer a real genomic address out of a data-entry artifact. These are not a CHM13 problem either, just the ordinary noise of a dataset built by many hands over many years.

The GRCh37 story is a milder version of the same thing, and it is why I would not lean on "well, it still has a build-37 coordinate" as reassurance. The source tree is GRCh38-native, and an older GRCh37 position exists for only a minority of its markers. Of the lost ampliconic markers specifically, roughly two thirds do lift back to a GRCh37 position and the rest do not, because they sit in sequence GRCh37 never had either. And the same name drift reaches back into the older builds: the *site* behind `ZZ11` does carry a GRCh37 address, but only under its dictionary name `ZZ11_1`, so the `ZZ11` your tree shows resolves to nothing even there. The prior-build coordinates are real, but they are patchy and inconsistent, which is exactly why the move to one complete reference, even at the cost of these temporary gaps, is the right direction.

I separate these out because they are easy to confuse with the real story, and they are not the same animal. A name mismatch can be cleaned up this afternoon. A SNP with no CHM13 address has to wait for a better instrument.

## Where that leaves the tree

The outcome this post is really about is small to state and large in consequence: roughly fifteen thousand markers in the ampliconic Y have no one-to-one CHM13 coordinate today, and the clades defined *only* by those markers are removed from the tree, their children promoted to the nearest surviving ancestor. Every branch that remains has a mutation CHM13 can actually point to.

The tree got *more correct*, not just smaller. The part it genuinely cannot represent yet, it represents as an honest absence rather than a confident guess, held open for the pangenome work that is the natural next step for all of this.

If your branch is one of the ones that went quiet, that is the deal: I would rather tell you "not yet, and here is exactly why" than show you a number I cannot stand behind. The map is getting better, and some of the territory is just waiting for a better map.
