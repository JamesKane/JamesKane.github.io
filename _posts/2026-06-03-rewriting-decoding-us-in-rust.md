---
layout: post
title: "Rewriting Decoding Us in Rust: Simpler, Safer, No Cold Start"
date: 2026-06-03
categories: genomics
tags: [decodingus, rust, atproto, oauth, bioinformatics, federated, genetic-genealogy]
excerpt: "A follow-up on Decoding Us: why we tore the whole stack down to the studs and rebuilt it in Rust, dropping the JVM and GATK, locking in the new AT Protocol permission model, and simplifying the architecture along the way."
---

# Rewriting It All in Rust

When I [introduced Decoding Us](/genomics/2025/12/13/Introducing-Decoding-Us.html) back in December, I described a platform approaching its MVP: interactive haplogroup trees, academic data integration, and an Edge App that processes your DNA locally and publishes only the results. The foundation worked. People started kicking the tires.

And then we decided to rebuild most of it.

That probably sounds like a step backward, so let me explain why it's the opposite, and why the version that comes out the other side is going to be simpler, faster, and more trustworthy than what we had.

## The Honest Reason

The original platform was three things wearing different hats. The web application was Scala 3 on the Play Framework. The Edge App, the desktop software that does the genomic heavy lifting, was a ScalaFX application that leaned on GATK, the standard bioinformatics toolkit, which runs on the Java Virtual Machine. Only the aggregation layer was already Rust.

Each of those choices was defensible on its own. Together they added up to a lot of friction:

- **The JVM is a heavy houseguest.** GATK doesn't just need Java; it needs a particular kind of Java, generous memory settings, and a few seconds of cold-start warm-up before it does anything useful. For a desktop app that a genealogist installs on a laptop, "first download a multi-gigabyte toolkit and a Java runtime" is a rough first impression.
- **Garbage collection pauses at the worst time.** When you're streaming through billions of bases in a CRAM file, the periodic stop-the-world pauses of a managed runtime are exactly the tax you don't want.
- **Two languages, two mental models.** Every shared concept had to be expressed twice and kept in sync by hand: what a biosample is, how a haplogroup node is defined, how we talk to a Personal Data Server.

So the decision: rewrite the whole stack, top to bottom, in **Rust**. A memory-safe language with no garbage collector, no runtime to warm up, and self-contained binaries at the end. The aggregation layer was already proving the point. We're extending it to everything.

## One Language, Top to Bottom

The new architecture is a single Rust codebase split into small, layered crates, with the pieces that both halves of the system need extracted into a shared library:

- **`du-domain`** holds the pure types and algorithms: what a variant *is*, how trees merge, how identifiers work. Defined once, used everywhere.
- **`du-atproto`** is our AT Protocol client, covering DID resolution, the OAuth flow, and the cryptographic plumbing.
- **`du-bio`** handles coordinate math and file parsing, including liftover chains, BED regions, and VCF reading.

The web platform (now Axum and HTMX instead of Play) and the Edge App both build on top of these. The desktop app uses [egui](https://github.com/emilk/egui), a pure-Rust user interface, which means the whole Edge App ships as one binary with no separate runtime to install. Define a concept once, and both sides of the federation agree on it by construction.

## Replacing GATK With Something Purpose-Built

This is the part I was most nervous about, and the part I'm most proud of.

GATK is excellent, general-purpose software. But Decoding Us only ever used a thin slice of it: calling variants, computing coverage, a handful of metrics. We were carrying an entire JVM toolkit to use a fraction of its surface.

So we built a purpose-built variant caller in pure Rust, reading BAM and CRAM files through the [noodles](https://github.com/zaeleus/noodles) library. No JVM, and no external binaries to shell out to. Because Y-DNA and mitochondrial DNA are *haploid*, one copy rather than two, the calling problem is far more tractable than general diploid variant calling, and we could write something focused and fast.

The obvious question is whether it actually agrees with GATK. You don't want a haplogroup assignment that depends on which tool you ran. So we built a parity harness that pits our caller against GATK on the same data. On the mitochondrial genome, our de-novo caller now matches GATK's HaplotypeCaller at **precision 1.000 and recall 1.000**: every SNP GATK found, we found, with no spurious extras. Getting that last false positive to disappear meant teaching the caller a light local realignment step around homopolymer runs, the same trick GATK uses. The harness stays in the test suite as a gate, so parity can't silently regress.

The result: the Edge App does its genomics natively, starts instantly, and streams whole-genome coverage in about 2 GB of memory where the naive approach would have needed dozens.

## Locking In the New AT Protocol Permissions

The bigger architectural simplification came from outside our codebase.

When I first wrote about the federated design, the AT Protocol (the same decentralized infrastructure behind Bluesky) already had OAuth, but it didn't yet have a fine-grained permission model to go with it. Without scoped permissions, the practical fallback was the older app-password mechanism, and an app password grants *full* account access. That forced an awkward design: we needed a trusted, credential-holding backend in the middle to relay writes safely. An entire subsystem existed only to compensate for a missing feature.

In early 2026 the AT Protocol shipped its [granular permission model](https://atproto.com/specs/permission). OAuth was already there; what landed was the ability to scope it, governing writes per record collection. That one addition let us delete a whole tier of the architecture:

- **The credential-holding relay is gone.** Clients now write **directly to your Personal Data Server** under a narrow, per-collection scope. Nothing in the middle needs to hold your keys.
- **The Edge App is a proper public client.** It uses the OAuth flow built for native desktop software: PKCE, a loopback redirect, and tokens stored in your operating system's keychain. No secret to leak, because there isn't one.
- **The web platform and the Edge App ask for different powers.** The desktop app requests *write* access to publish your results. The web side never asks for the keys to your data at all.

We validated the core flow against a live Personal Data Server: discovery, authorization, the cryptographic token binding, and publishing a real coverage summary and reading it back. It works.

## The AppView Is Still the Hub

I want to be careful not to oversell "simpler" here, because one piece stays deliberately substantial: the central service, which in AT Protocol terms is called the AppView.

The AppView is the lynchpin for everything that happens *between* people rather than on one person's laptop. IBD match suggestions, messaging, cross-user reporting, the shared haplogroup tree: all of it depends on a service that can hold de-identified results from across the community and answer real questions about them quickly. "Quickly" is the operative word. Match-finding and reporting need data you can query, index, and join, not summaries reassembled on the fly each time someone asks. That calls for a proper PostgreSQL database, so the AppView keeps one. (An earlier sketch of the Rust design imagined doing all of this on demand, reading straight from Personal Data Servers per request. It didn't survive contact with what reporting actually requires.)

What *did* get simpler is how data reaches the AppView. The credential-holding relay is gone, the same one the new permission model let us delete. Edge Apps now publish their de-identified call signatures and coverage summaries directly to their own Personal Data Servers, and the AppView ingests that public, de-identified layer into its store. Your raw DNA never enters the picture. What the central service holds is what it always worked with: the derived signatures, not your genome, now in a database built for the reporting and matching still to come.

## What This Means If You're Not a Programmer

All of that is plumbing. Here's what you'll actually notice:

- **One thing to install.** The Edge App becomes a single download with no Java runtime, no toolkit, and no setup ritual.
- **It starts now, not in a few seconds.** No cold start, and no GC hitches mid-analysis.
- **Your data ownership is unchanged, and the path to it is shorter.** Your raw DNA still never leaves your machine. Your results still publish to *your* server. There's just no longer a middleman holding credentials to make that happen.

The promises from the first post all still hold. You own your data. It's portable. The stack is open source, so if Decoding Us disappeared tomorrow, someone could pick it up. The rewrite doesn't change any of that. It makes the foundation under it sturdier.

## Where Things Stand

I want to be straight about status, the same way I was in December. This is a rewrite in progress, not a finished product.

The genomics core is done. Coverage, the haploid caller, sex inference, structural-variant evidence, diploid genotyping, and the IBD matching engine are all ported and running natively, with the haploid caller held to the GATK parity bar described above. The desktop shell drives them end to end. On the web side, the spine is complete: schema, data layer, the public site, curator tools, the JSON API, and tree versioning. The OAuth flow is validated against a real server.

What's left is real work: wiring the login experience through the desktop UI, the variant-proposal submission path, token refresh, the federation endpoints, and a careful cutover from the old system. The AppView features that connect people, IBD match suggestions and messaging chief among them, are still ahead of us, and they're a big part of why the AppView stays substantial. The discovery engine I described last time, the part that proposes new branches when unrelated people share the same private variants, is still the destination. Everything we're building is in service of getting there on a foundation that won't buckle.

There's also a nice tailwind I didn't have in December. The [T2T Consortium](https://github.com/marbl/CHM13) has published a full set of reference resources for the complete, telomere-to-telomere human genome: liftover chains, variant panels, accessibility masks, all of which simply didn't exist when the original code was written. The Rust version gets to build on the better map from the start.

Rewriting working software is a gamble. You spend effort getting back to where you already were, and you bet that the new ground is worth the climb. I'm confident in this bet. A memory-safe language, a single binary, a permission model that finally fits the federated design, and an architecture with fewer moving parts: that's the platform I wanted to build the first time.

The trees are still alive. We're just giving them better roots.

---

*For technical details, visit [decoding-us.com](https://decoding-us.com/) or check out the [source code](https://github.com/decodingus/decodingus).*
