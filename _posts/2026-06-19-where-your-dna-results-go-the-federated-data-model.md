---
layout: post
title: "Where Your DNA Results Go: The Federated Data Model Behind Decoding Us"
date: 2026-06-19
categories: genomics
tags: [decodingus, atproto, pds, firehose, appview, federated, edge-computing, genetic-genealogy, privacy]
excerpt: "I've written a lot about what the Navigator Workbench computes on your laptop. This post follows the other thread: what happens to a result after it's computed. How a haplogroup assignment travels from your machine to a server you own, gets picked up by the firehose, and lands in the shared index — and, just as important, what never makes the trip."
---

# Where Your DNA Results Go

Most of what I've written about Decoding Us lives on one machine. Placing a [Y haplogroup in a pangenome](/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html), [what a pangenome catches and misses](/genomics/2026/06/16/what-a-pangenome-misses-and-what-it-nails.html), [rewriting the variant caller in Rust](/genomics/2026/06/03/rewriting-decoding-us-in-rust.html) — all of that is the Navigator Workbench chewing through a BAM file on your laptop and producing answers.

This post is about the part that comes after. A result is sitting in the Workbench. Now what? Where does it go, who gets to see it, and how does it end up contributing to the shared tree and the match suggestions that make the whole thing more than a single-player tool?

The short version is a four-hop path: **Navigator → your PDS → the firehose → the AppView.** Each hop earns its place, and the boundaries between them are exactly where the privacy guarantees live. Let me walk it.

## The one rule everything else hangs on

Before the data flow, the principle that constrains it: **your raw genome never leaves your machine.**

Not "we encrypt it in transit." Not "we delete it after processing." It simply never moves. The BAM, the CRAM, the VCF, the FASTQ, the chip genotype file — all of it stays on the device where the Navigator Workbench runs. This is edge computing in the literal sense: the analysis goes to the data, not the other way around.

What *does* travel is the stuff computed *from* your genome — and even then, only a thin, derived layer:

| Flows out | Stays home |
|:---|:---|
| Haplogroup assignment (`R-FGC29071`, `U5a1b1g`) and its lineage path | The BAM/CRAM with your aligned reads |
| Private Y-DNA / mtDNA SNPs — the novel variants that grow the tree | The full VCF |
| Coverage and quality summaries | The FASTQ raw reads |
| Ancestry percentages and PCA coordinates | The chip genotype file |
| File *metadata* — name, checksum, size | The file *contents* |

Notice the shape of the second column. It's not "less detailed versions of the first." It's a different category entirely. A haplogroup name is a conclusion. A coverage summary is a statistic. Neither one lets anybody reconstruct your sequence, because the sequence stayed on your disk the whole time. The Workbench is, by design, a one-way valve: genomes in, conclusions out.

## Hop one: Navigator → your PDS

When you publish a result, the Workbench writes it to your **Personal Data Server** — your PDS, the same kind of account that backs a Bluesky identity under the [AT Protocol](https://atproto.com/). It's a server you control, addressed by a decentralized identifier (a DID) that's yours regardless of which provider hosts it.

I covered the *permission* side of this in the [Rust rewrite post](/genomics/2026/06/03/rewriting-decoding-us-in-rust.html): the Workbench is a public OAuth client that writes directly to your PDS under a narrow, per-collection scope, with no credential-holding middleman. What I want to draw out here is the *shape* of what gets written, because that shape is doing real work.

The records are **granular**. Each logical thing — a biosample, a sequencing run, an alignment, a haplogroup result, an ancestry breakdown — is its own first-class record with its own address (an AT URI). They're not bundled into one big document. A biosample record points at its sequencing runs by reference; a run points at its alignments; an alignment carries just its metrics.

```
workspace
└── biosample            haplogroups: { yDna, mtDna }
    ├── sequencerun       platform, instrument
    │   └── alignment     referenceBuild, coverage metrics
    ├── genotype          chip data metadata
    └── populationBreakdown   ancestry components
```

Why split it up like this? Because results get *revised*. You re-run an alignment against a better reference. A new tree version moves your terminal branch. If everything were one monolithic blob, every small update would rewrite the whole thing and ripple through everyone indexing it. With granular records, you update the one alignment that changed and nothing else moves. The parent biosample doesn't even notice.

A few other properties baked into the records:

- **Soft deletes.** Removing a record doesn't destroy it; it marks it withdrawn. Scientific lineage is worth preserving even when a particular result is retracted.
- **Version tracking.** Each record carries a content identifier and a version number, so a downstream reader can tell a genuine update from a replay and resolve conflicts deterministically (higher version wins; ties break on timestamp).
- **Metadata, not content, in the file fields.** A `fileInfo` block records a name, a checksum, and a size — and a *location* that's purely for your own reference. Decoding Us never reads that location. It exists so you can keep track of where your own BAM lives; it's a note to self, not a pointer the network follows.

At the end of hop one, your conclusions live on a server you own, in records addressed by your DID. If Decoding Us vanished tomorrow, those records would still be sitting in your PDS, yours, in an open format.

## Hop two: the firehose

Here's the elegant part, and it's not something Decoding Us invented — it's how the whole AT Protocol ecosystem works.

Every PDS in the network emits a stream of its public record changes: creates, updates, deletes. That stream is the **firehose**. Bluesky uses it to build timelines; we use it to build a genomic index. When your Workbench writes a haplogroup record to your PDS, that write shows up on the firehose as an event, tagged with the collection it belongs to (`com.decodingus.atmosphere.biosample` and friends).

The thing I find genuinely nice about this: **we don't have to ask your PDS for anything.** There's no API where Decoding Us reaches into your account and pulls. You publish; the network broadcasts; anyone subscribed listens. The data flows because you pushed it out, not because a central service came and took it. That inversion is the whole point of building on a federated protocol instead of a private API. Your server is the source of truth, and the index downstream is just a cache of what you chose to make public.

## Hop three: the firehose → the AppView

The **AppView** is the central service — Decoding Us itself, in AT Protocol terms. It subscribes to the firehose — in practice the lightweight [Jetstream](https://github.com/bluesky-social/jetstream) variant, a filtered JSON feed rather than the full binary repo stream — keeps only the `com.decodingus.atmosphere.*` summary records it cares about, and folds each event into a PostgreSQL database (the de-identified `fed.*` store you'll see me refer to later). Create a biosample, a row appears. Update an alignment's metrics, the row updates in place, parents untouched. Delete a record, it's marked orphaned or withdrawn, never truly gone — and its children are orphaned, not cascaded into oblivion, so a re-create can re-attach them.

I was careful in the last post not to undersell the AppView, and I'll repeat it here: this piece stays **deliberately substantial.** It would be tidier to claim the whole system is just laptops talking to PDSs with nothing in the middle. But the interesting questions in genealogy are the ones *between* people:

- **IBD match suggestions** — finding the other people in the network who share a stretch of DNA with you.
- **The shared haplogroup tree** — the consensus phylogeny that grows when unrelated people independently report the same private variant.
- **Multi-run reconciliation** — when one person has a chip test, a Big Y, and a whole genome, deciding what the *consensus* haplogroup across all of them actually is.
- **Reporting** across the community — the de-identified summaries indexed and queryable, so the network can answer real questions about itself.

None of those can be answered from a single PDS, and none of them can be reassembled cheaply on demand. Match-finding needs data you can index and join across thousands of people, fast. That's a database's job. So the AppView keeps a real PostgreSQL store of the de-identified layer — the conclusions and signatures, never the genomes — built for exactly the kind of querying these features require. (An early sketch of the design imagined doing all of this on the fly, reading from PDSs per request. It did not survive contact with what reporting actually needs.)

The mental model that keeps it straight: **your PDS is the source of truth; the AppView is a queryable index built from the public slice you opted to publish.** If the AppView's database were wiped, it could rebuild itself by replaying the firehose. Your records are the originals; its tables are derived.

## What about the things that connect people?

This is where the privacy boundary gets its most careful treatment, because matching is inherently about comparing your data to someone else's.

The rule holds even here: the comparison happens at the edges, not in the middle. IBD segment detection runs **locally**, in your Workbench, against candidates the network helps you find. What flows to the AppView is consent and confirmed-match metadata — never your raw segments, never the underlying genotypes. A `matchConsent` record is you opting in; a match list is the conclusion of a comparison, not its raw material. The AppView can suggest *who* might be worth comparing against, but the actual DNA-to-DNA comparison stays on hardware you control, gated behind explicit consent.

There's also a second ownership model worth naming, because it's not all citizen-owned PDSs. Academic and published samples — the ones from research papers that anchor the tree in known science — don't have a citizen behind them with a PDS. For those, the AppView itself is the source of truth, curator-administered. The `specimen_donor` concept stitches the two worlds together: it unifies samples from the same underlying individual whether they arrived from a citizen's PDS or from a publication, so a person with both a personal test and a presence in the literature isn't split into two strangers.

## If you're not a programmer

Strip away the protocol names and here's what the model actually promises:

- **Your genome stays on your computer.** Always. The thing that does the heavy analysis runs locally and only ever emits conclusions — your haplogroup, your ancestry percentages, your coverage stats. The raw sequence has no exit.
- **Your results live on a server you own.** Not in a Decoding Us account you'd lose access to if you left. They're in your PDS, addressed by an identity that's portable across providers, in an open format. Leaving doesn't mean losing them.
- **The shared features are opt-in and edge-computed.** Matching, the community tree, reporting — they run on the conclusions you chose to publish, and the sensitive comparisons happen on your own machine behind explicit consent.
- **The central service is honest about what it is.** It's a fast index over the public, de-identified layer — the part that makes match suggestions and a shared tree possible — not a vault holding everyone's genomes. There are no genomes to hold.

The federation isn't decoration. It's the mechanism that lets the second and third promises both be true at once: you keep your data, *and* the network can still be more than the sum of isolated laptops.

## Where things stand

More is done than I sometimes give it credit for. The spine is built and cutover-verified: the schema, the query layer, the public site and JSON API, the curator tools, the haplogroup tree's build/merge/versioning machinery, the variant-naming authority. The Workbench publishes core records to a PDS, and the AppView ingests them — biosample, sequence run, alignment, project, workspace, plus genotype, ancestry, and haplogroup reconciliation. And the **reporting layer is live**: the de-identified summaries land in the `fed.*` store and the endpoints that query and join across the community already answer.

**IBD matching is built on both ends** — the edge-side segment detection in the Workbench and the AppView-side suggestion and introduction flow that pairs people up, riding the same encrypted edge-to-edge channel the design calls for. It's code that runs, not a sketch. What it hasn't had yet is a real production cohort: the proving ground where you point it at thousands of live records and find out how the suggestions hold up at scale. So "done" here means done-and-untested-in-production, which is a real distinction and one I'd rather name than paper over.

Branch discovery is real too, in its **curator-driven form**: private variants that extend past the known tree surface as proposed branches, and curators review, accept, modify, or split them. What's still forward there is the *automation* — the engine that correlates shared private variants across unrelated people and drafts the proposal on its own, rather than a curator spotting the pattern.

So the genuinely-ahead list is narrower than "everything social." It's the **collaboration and genealogy-platform layer**: group projects, a privacy-preserving research-subject registry that links a person's samples across testing companies without the AppView ever holding their name, attributed assertions over that registry, and the messaging and reputation features that sit on top. That's a real chunk of work, and it's deliberately the last thing built — because it's the layer where people make claims *about* each other's results, and the no-PII, consent-gated foundation under it had to come first.

You publish a conclusion. The network indexes it. Your sequence never moves. That's the whole shape of it.

---

*For technical details, visit [decoding-us.com](https://decoding-us.com/) or check out the [source code](https://github.com/decodingus/decodingus).*
