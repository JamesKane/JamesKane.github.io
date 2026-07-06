---
layout: post
title: "Folding@Home for the Family Tree: A Community Compute Grid for Public DNA"
date: 2026-07-06
categories: genomics
tags: [decodingus, distributed-computing, ena, crowdsourcing, t2t, chm13, minimap2, haplogroups, ancestry, genetic-genealogy, edge-computing, reputation]
excerpt: "There are tens of thousands of public DNA samples sitting in scientific archives, most of them aligned to a decade-old reference and never placed on our haplogroup tree. Reprocessing all of them onto the modern T2T reference is a mountain of compute. So here is a proposal: borrow the SETI@home idea. Let volunteers lend spare cycles on their own computers to reprocess public genomes, one work unit at a time, and turn the results into a shared community resource. This is the design, in plain terms, and where it stands."
---

# Folding@Home for the Family Tree

If you were online in the early 2000s, you might remember a screensaver that searched radio noise for aliens. SETI@home turned a few million idle home computers into one enormous telescope-processing cluster. Folding@Home did the same for protein simulations and, for a while during the pandemic, was one of the most powerful computing systems on the planet. The trick was simple and a little bit magical: your computer, doing nothing while you slept, quietly worked on one small piece of a very large problem, sent the answer home, and asked for another.

I want to try the same trick for genetic genealogy. This post is a proposal, not a finished feature, so I will be honest about that throughout. But the shape of it is clear enough to write down, and I think it is worth getting right.

The short version: there is an enormous amount of public DNA data that nobody has processed the way *we* want it processed. Let volunteers lend their spare computer time to fix that, and give them a scoreboard for doing it.

## The pile of data we are not using

When a lab publishes a study, the sequencing data usually goes into a public archive. The big one in Europe is the [European Nucleotide Archive](https://www.ebi.ac.uk/ena/browser/home), the ENA. It holds hundreds of thousands of human samples: the 1000 Genomes Project, the Human Genome Diversity Project, ancient DNA from archaeological digs, population studies from every corner of the world. This is the raw material that anchors the haplogroup tree in real, citable science. It is free to download and free to use.

Here is the catch. Almost all of it was aligned to an older reference genome, usually GRCh37 or GRCh38, and processed with whatever pipeline the original lab happened to run. For a genetic genealogist, that leaves two problems.

First, the reference is out of date. I have written before about moving our work onto the [T2T-CHM13 assembly](/genomics/2026/06/30/the-branches-that-dont-lift.html), the first truly complete human genome. The old references have gaps and collapsed duplications, and the Y chromosome in particular is far better resolved on T2T. A sample aligned to GRCh38 is looking at the family tree through a smudged lens.

Second, even where the data is fine, nobody has placed most of these samples on our tree. A 1000 Genomes sample has a Y chromosome that belongs on a specific branch, with a specific ancestry profile, but unless someone actually runs that analysis, it is just a file sitting in an archive. Multiply that by tens of thousands of samples and you have a genuinely useful map of human genetic history that simply has not been drawn yet.

Drawing it is not hard, exactly. It is just *a lot*. Re-aligning one whole genome to T2T is hours of computer time and tens of gigabytes of scratch disk. Running the full analysis stack on top of that (coverage, biological sex, structural variants, Y and mitochondrial haplogroups, ancestry) is more. Doing it for a whole archive is not something one laptop, or one person's electricity bill, is going to finish.

But it is *exactly* the kind of problem you split into small pieces and hand out to a crowd.

## The idea in one paragraph

The Decoding Us AppView, the shared server I have described in earlier posts, publishes a list of **work units**. Each work unit is one public sample from the ENA. A Navigator instance running on your computer can raise its hand and reserve a work unit for a few days. While it holds that reservation, it downloads the sample straight from the ENA, re-aligns the reads to the T2T reference using a real aligner, runs the complete analysis stack, submits the conclusions back to the shared index, and releases the reservation for the next one. Do enough of them and your name climbs a public leaderboard, and your contribution earns a bump to your standing in the community.

That is the whole thing. Now let me walk the parts that make it actually work, because the details are where these systems live or die.

## Reserving a work unit, honestly

The coordination is the part I find most interesting, because it has to be fair. If one over-eager machine grabbed a thousand samples and then crashed, those samples would be locked forever. So reservations work like a library loan with a due date.

When your Navigator asks for work, the AppView hands it a small batch and stamps each one with an expiry, say three days. Your machine sends a quiet heartbeat as it makes progress, which can extend the loan while real work is happening. If your computer finishes, great, it submits and releases. If your computer is turned off, closes the lid for a week, or simply gives up, the loan expires on its own and the sample quietly returns to the pool for someone else. No sample can be hoarded, and no crash can strand one.

Under the hood this is a classic job-queue pattern, and pleasantly, a lot of the plumbing for it already exists in the AppView database from an earlier design pass and just needs to be switched on. The reservation, the node registry, the heartbeat log, and the results queue were sketched out long ago. What is new is the logic that hands out loans without ever giving the same sample to two machines at once, and the logic that decides when a result is trustworthy. Which brings me to the hard problem.

## How do you trust a stranger's computer?

This is the question that every volunteer-computing system has to answer, and it is not a small one. When a random computer on the internet sends back "this sample is Y-haplogroup R-M269," how do you know it is telling the truth? Maybe the machine has a subtle hardware fault. Maybe someone modified their copy to submit garbage and farm the leaderboard. Maybe they are just running an old version with a real bug.

SETI@home and Folding@Home solved this with **redundancy**. Send the same work unit to more than one independent computer and only believe the answer when they agree. A single machine cannot lie its way to a false result, because it does not control the others.

We use the same principle, with a genealogy-specific twist. Two things make it work.

First, **we compare conclusions, not files**. Re-aligning a genome is not perfectly repeatable down to the byte: run it with a different number of processor threads and the output file differs in trivial ways, even though the biology is identical. So it would be pointless to check whether two machines produced the exact same file. Instead each machine submits a small, signed **summary of its conclusions**: the biological sex, the Y-haplogroup terminal branch, the mitochondrial haplogroup, the top-level ancestry, the coverage rounded to a sensible bucket. Two results *agree* when those conclusions match. That is the genealogically meaningful thing anyway. I do not care whether two copies of a BAM are identical; I care whether they both say R-FGC29071.

Second, **trust is earned and adaptive**. A brand-new node is treated with healthy suspicion: its work units are also sent to a second independent machine, and the sample is only marked canonical when they agree. As a contributor builds a track record of results that keep matching everyone else's, the system starts trusting them to run a unit solo, while still spot-checking a small random fraction of their work. If a node ever submits a result that contradicts an established one, its reputation takes a hit and it drops back to being double-checked. This is how you get the safety of redundancy without paying to run *everything* twice forever. New and unproven work gets the belt-and-suspenders treatment; proven contributors get trusted with the occasional audit.

The signature matters too. Each result is signed by a cryptographic key tied to the contributor, using the same device-key mechanism that already secures the private matching features. A result is not an anonymous vote. It is a signed statement: *this machine, belonging to this person, computed this conclusion.* That is what lets the AppView give credit to the right person and, if needed, hold a bad actor accountable.

## Where the results live, and who gets the credit

When a work unit is validated, its conclusions become part of the shared index, tagged with the ENA accession they describe so anyone can look them up. They also carry a provenance stamp: which reference, which aligner and version, which analysis stack produced them. Reproducibility is not optional for something that wants to be citable.

There is a subtle new wrinkle here compared to everything I have built before. Until now, a published record was always *about* the same person who published it: your PDS, your haplogroup. A grid result is *about* a public sample but *computed by* you. So the records grow a small distinction between the **subject** (the ENA sample) and the **contributor** (the volunteer who did the work). That sounds like a technicality, but it is the thing that lets the system credit you for processing a sample that is not yours.

And credit is the fun part. Borrowing the vocabulary of the old distributed-computing projects, each validated work unit earns **cobblestones**, a score weighted by how much work it actually took. Re-aligning a deep whole genome is worth more than running the stack on a small sample. Those scores feed a public leaderboard on the AppView: all-time and rolling, so both the marathoners and the newcomers who went hard this month get their moment. Validated contributions also give a bump to your community reputation, the same reputation that gates the social features, though deliberately capped so that nobody can grind the grid to buy their way past the trust thresholds. Compute standing and social standing are related but not the same currency.

I will admit the gamification is partly just because it is delightful. There is something genuinely satisfying about watching a counter tick up while your computer chews through human history in the background. SETI@home understood that. The leaderboard is not a gimmick bolted on; it is the engine that turns a chore into a hobby.

## Why start small

The instinct with a system like this is to build the whole vision at once: fetch reads, re-align to T2T, run everything, from day one. I am deliberately not doing that.

The first version skips the aligner entirely. A meaningful slice of ENA samples already ship with a modern alignment file attached. For those, there is no need to re-align anything: download it, run the analysis stack, submit the conclusions. This proves out the entire distributed machine (the reservations, the heartbeats, the trust-by-agreement, the leaderboard, the credit) without the single riskiest and heaviest piece attached. It is the difference between testing a new engine on a bench and dropping it straight into a car doing highway speed.

Only once that loop is turning smoothly does the second version add the marquee capability: pulling raw reads and re-aligning them to T2T with [minimap2](https://github.com/lh3/minimap2), compiled directly into Navigator so there is still no separate tool to install. That re-alignment engine is already specified in its own design, and pleasantly, the hardest part of it (reconstructing raw reads from an existing alignment) is unnecessary here, because ENA raw reads arrive already unaligned. The grid gets the easy half of a hard feature.

## What this actually gives a genealogist

Step back from the machinery and here is the payoff.

Imagine every public sample that matters to our field placed on the *same* modern tree, with the *same* pipeline, all comparable to each other and to your own results. Every 1000 Genomes participant, every published ancient genome, every population-study sample, given an honest Y and mitochondrial placement on T2T coordinates and an ancestry profile computed the same way yours was. That is a reference map of human paternal and maternal lineages, drawn to a consistent standard, that mostly does not exist today because nobody has had the compute to draw it.

More placed samples means a denser tree, which means more of those satisfying moments where an unnamed branch suddenly has a published sample sitting on it, or where a private variant you carry turns out to be shared with an ancient individual from a specific time and place. It means better context for your own results: not just "you are R-FGC29071" but "here is where that sits among every public sample the community has processed." It is the [crowdsourced haplogroup tree](/genomics/2025/12/06/crowdsourcing-the-haplogroup-tree.html) idea, extended from crowdsourcing the *variants* to crowdsourcing the *compute* that places them.

And it scales with enthusiasm rather than budget. There is no server farm to rent. The more people who leave Navigator running overnight, the faster the map fills in.

## If you're not a programmer

Here is the whole thing without the jargon:

- **There is a huge amount of free, public DNA data** from research studies that nobody has fully processed onto the modern, complete human reference genome.
- **Processing it all is too much for any one computer,** but it splits neatly into small independent jobs.
- **You can volunteer your computer** to do some of those jobs while you are not using it, a bit like the old SETI@home screensaver, and the results get added to a shared community map of human lineages.
- **Your own private DNA is never involved.** The grid only works on public samples that are already free for anyone to download. Your personal genome stays on your machine exactly as before.
- **Answers get double-checked.** A result is only trusted when independent computers agree on it, so a broken or dishonest machine cannot poison the map.
- **You get a scoreboard.** Validated work earns points on a public leaderboard and a boost to your reputation, because doing a real chore should feel a little like a game.

## Where things stand

Now the honesty section, because this is a proposal and I would rather name that than dress it up.

This is a **design, not a shipping feature**. The document exists, the decisions are made, and much of the foundation it depends on is already built and running: the shared server and its database, the signed-request security, the reputation ledger, the full analysis stack in Navigator, and the firehose ingestion that would carry the results into the shared index. The re-alignment engine is specified in detail. What has not been written yet is the connective tissue: the code that fetches from the ENA, the reservation and trust logic on the server, the leaderboard, and the worker loop that ties it all together.

So there is no screensaver to download today. There is a plan I am fairly confident in, a first version scoped small enough to actually finish, and a foundation solid enough that the plan is not wishful. If it works the way I expect, the first sign of it will be quiet: a leaderboard with a handful of names on it, and a tree that is filling in a little faster than one person could manage alone.

That was always the appeal of the @home projects. Not any single computer doing something heroic, but a lot of ordinary machines, each doing a small honest piece, adding up to something none of them could do apart. The family tree is exactly that kind of problem.

---

*For technical details, visit [decoding-us.com](https://decoding-us.com/) or check out the [source code](https://github.com/decodingus/decodingus).*
