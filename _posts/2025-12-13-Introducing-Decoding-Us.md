---
layout: post
title: "Crowdsourcing the Haplogroup Tree: How Your DNA Helps Build Human History"
date: 2025-12-13
categories: genomics
tags: [haplogroups, y-dna, mtdna, genetic-genealogy, decodingus, federated]
---

# Introducing Decoding Us: A Platform for Community-Driven Haplogroup Discovery

When I wrote about the closure of YDNA-Warehouse earlier this year, I promised something new was coming. Today I'm ready to share what we've been building.

**Decoding Us** is now approaching its MVP milestone—a collaborative platform designed to let genetic genealogists work together on haplogroup tree development while maintaining control over their own data.

## The Problem We're Solving

If you've spent time in genetic genealogy, you know the frustration. The haplogroup trees—those branching diagrams showing how Y-DNA and mtDNA lineages split over millennia—are living documents. New discoveries happen constantly as more people test and as sequencing technology improves.

But contributing to that knowledge has always been difficult. Maybe you found mutations beyond your terminal haplogroup. Maybe you noticed your Big Y results contain SNPs that aren't on any tree yet. Where do those observations go? How do they become part of the shared understanding?

Traditional models lock your data behind proprietary walls. The company stores your raw DNA. The company controls access. The company decides what gets published and when. If the company changes direction—or closes its doors—your contribution to genetic genealogy goes with it.

We're building something different.

## What Decoding Us Does Today

The platform is already functional and preparing for wider testing. Here's what works now:

**Interactive Haplogroup Trees.** Browse the Y-DNA and mtDNA phylogenetic trees with an interface built for genealogists. Each node shows its defining variants, and the trees are structured to support the discovery workflow we're building.

**Academic Data Integration.** We've built a system to contextualize samples from peer-reviewed publications within our experimental trees. Every sample links back to its original source—ENA accession numbers, DOIs, the works. Full transparency about where data comes from.

**Publication Tracking.** Curators can submit relevant publications, and the platform enriches them with metadata from OpenAlex. Samples from peer-reviewed studies get associated with specific tree positions, building a bridge between academic research and community-driven discovery.

**Sample Registration via the Edge App.** This is where things get interesting. The Edge App processes your DNA files locally on your own hardware. It determines your haplogroup assignment, identifies your private variants, and publishes only the analysis results—never the raw genetic files—to your Personal Data Server.

**API Integration.** The backend exposes a complete REST API with Swagger documentation. Biosamples flow in from Edge Apps, get associated with specimen donors, and feed into the discovery pipeline.

## The Discovery System (Coming Next)

The core innovation we're working toward is automatic branch discovery. Here's how it will work:

When your DNA sample is analyzed, the system identifies mutations that extend beyond the known tree. These "private variants" are potential new discoveries. On their own, they might be noise—sequencing errors, parallel mutations, random drift.

But when multiple unrelated people share the same private variants? That's signal.

The system correlates evidence across all samples—both from individual users and academic publications. When enough independent samples share the same variants (configurable threshold, default three), it creates a proposed branch. Curators review the evidence, and accepted proposals become official additions to the tree.

Every sample that contributed evidence gets automatically reassigned to the new, more specific branch.

This is how haplogroup trees should evolve: organically, driven by community data, with expert oversight to maintain quality.

## Why the Federated Architecture Matters

I've been working on this problem for years, and I keep coming back to the same conclusion: the traditional model is broken. Not because the companies are bad actors—many do excellent work—but because centralization creates fragility.

With Decoding Us, your DNA data lives in your Personal Data Server. Think of it like your own personal cloud storage for genetic information. The Edge App runs on your device and handles the heavy computation. Your raw files never leave your machine.

What gets shared? Just the analysis results: your haplogroup assignment, your variant calls, your coverage metrics. Enough information to contribute to tree building. Not enough to reconstruct your genome.

This design means:

- **You own your data.** Not us. You.
- **Portability.** Take your data to any compatible service.
- **Resilience.** No single point of failure. If Decoding Us goes away, your data doesn't.  The entire stack is open source—anyone could pick up where we left off.

We're building on the [AT Protocol](https://atproto.com)—the decentralized infrastructure that also powers Bluesky. But our network is separate: dedicated Personal Data Servers for genomic data, our own relay infrastructure, our own Lexicon definitions. Your biosample records, your projects, your workspace—all defined in a portable format that any compatible application can understand.

## What's Next

The MVP is focused on getting the core workflow solid: samples flowing in, trees displaying correctly, publication data integrating cleanly. After that, the roadmap includes:

- **Haplogroup Discovery Engine** — The full proposal workflow with curator review
- **Multi-Test-Type Support** — Extending beyond WGS to handle Big Y-700, mtDNA Full Sequence, and chip data
- **IBD Matching** — Privacy-preserving relative discovery through encrypted edge-to-edge comparison
- **Sequencer Lab Inference** — Community-driven identification of which labs own which instruments

The discovery system is the heart of it. Everything else enables it.

## Getting Involved

Decoding Us is open source under the BSD 3-Clause license. The web platform is Scala 3 and Play Framework. The entire aggregation layer, decodingus-nexus, is written in asynchronous Rust, handling the Firehose ingestion, PDS synchronization, and real-time event processing. If you're technically inclined, there's interesting work on both ends. But you don't need to be a developer to contribute.

We need:
- **Testers** willing to run the Edge App and provide feedback
- **Curators** with haplogroup expertise to help validate the tree structure
- **Data** — every sample that flows through the system makes discovery more powerful

If you've been waiting for an alternative to the walled gardens, this is it. Not a finished product—we're building this together—but a foundation designed for community ownership from the start.

The trees are alive. Let's grow them together.

---

*For technical details, visit [decoding-us.com](https://decoding-us.com/) or check out the [source code](https://github.com/decodingus/decodingus).*
