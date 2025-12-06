---
layout: post
title: "Crowdsourcing the Haplogroup Tree: How Your DNA Helps Build Human History"
date: 2025-12-06
categories: genomics
tags: [haplogroups, y-dna, mtdna, genetic-genealogy, decodingus, federated]
---

The Y-DNA and mtDNA haplogroup trees are among the most fascinating maps in human genetics. They trace our paternal and maternal lineages back tens of thousands of years, connecting us to migrations, populations, and ancestors we'll never know by name. But these trees aren't static museum pieces—they're living documents that grow with every new discovery.

The problem? Until now, expanding the tree has been a manual, academic exercise. Researchers publish papers, nomenclature committees meet, and eventually new branches get official names. Meanwhile, thousands of people are getting whole genome sequencing done, and their DNA contains discoveries that could extend the tree—if only there were a way to find them.

That's what we're building next.

## The Discovery Problem

When you get your haplogroup assignment—say, R-M269—the analysis compares your DNA against known mutations that define each branch of the tree. The software walks down from the root, testing each defining variant until it reaches your terminal haplogroup: the most specific branch you belong to.

But here's the interesting part: you almost certainly have mutations *beyond* your terminal branch. These "private variants" are mutations that haven't been documented in the official tree yet. Maybe they're unique to your family line. Or maybe—and this is where it gets exciting—other unrelated people have the exact same mutations.

When multiple independent samples share the same private variants, that's evidence of a real genetic lineage. A new branch hiding in plain sight.

## How It Works

The system we're building tracks these private variants across all samples in the network. When your DNA is analyzed on your local Edge device, the results include not just your haplogroup assignment, but also a list of variants that extend beyond the known tree.

These discoveries flow into a central registry where the system looks for patterns:

1. **Correlation** - When Joe and Bob (completely unrelated, different countries) both have the same two mutations beyond R-M269, that's interesting
2. **Consensus** - When Frank and David also show up with matching mutations, we have a pattern
3. **Proposal** - The system creates a "proposed branch"—a candidate for addition to the official tree
4. **Review** - Expert curators examine the evidence and either accept, reject, or refine the proposal
5. **Evolution** - Accepted proposals become official branches, and everyone's assignments update automatically

The magic is in the aggregation. No single sample is conclusive, but patterns across dozens of independent samples provide strong evidence for new branches.

## Federated by Design

Here's where the architecture matters.

Your raw DNA data never leaves your control. The Edge application runs on your hardware—whether that's a beefy desktop, a modest laptop, or [an Orange Pi 5 Plus](/genomics/2025/04/19/Personal-Genomics-on-an-Orange-Pi-5-Plus.html)—and handles all the heavy computation locally. Only the analysis results (haplogroup assignments, private variant summaries) get published to your Personal Data Server.

```
Your Device          Your PDS             DecodingUs
┌────────────┐      ┌────────────┐       ┌────────────┐
│ Edge App   │─────►│ Your Data  │──────►│ Discovery  │
│ (local)    │      │ (you own)  │       │ Engine     │
└────────────┘      └────────────┘       └────────────┘
                                                │
                                                ▼
                                         Tree expands
```

This isn't just a privacy nicety—it's foundational. The genetic genealogy space has been plagued by companies that lock your data behind proprietary walls, change their terms of service on a whim, or get acquired and leave you wondering what happened to your genome. The federated model flips this: you maintain custody of your data, and services compete to provide value rather than lock-in.

## The Curator Layer

Automated consensus detection is powerful, but genetics is messy. Sequencing errors happen. Some variants look private because coverage was poor in that region. Parallel mutations can occur in unrelated lineages.

That's why the system includes a curator workflow. When a proposed branch accumulates enough supporting evidence (configurable, but typically 3+ independent samples), it gets flagged for expert review. Curators can:

- **Accept** the proposal with an official name (e.g., R-FT12345)
- **Reject** it with documented reasoning
- **Split** it if the evidence suggests multiple distinct sub-branches
- **Modify** which variants define the branch

Every action is logged permanently. Who changed what, when, and why. The tree's evolution becomes auditable history.

## What This Means for You

If you've done whole genome sequencing—or plan to—your data can contribute to expanding human genetic history. Not by uploading your raw files to yet another company, but by running analysis locally and sharing only the results you choose to share.

When a new branch gets discovered and you're one of the supporting samples, you'll see your assignment update automatically. That generic "R-M269" might become "R-M269 > R-XYZ123"—a more specific placement that connects you to a subset of that lineage.

And for the genetic genealogy community, this creates something that hasn't existed before: a mechanism for the tree to grow organically based on real-world data, with quality control, without requiring academic publication cycles.

## What's Next

This discovery system is our next major milestone after completing the MVP. The foundation is already in place: the Edge application handles local analysis, the PDS integration provides federated data ownership, and the haplogroup assignment pipeline identifies terminal branches and private variants.

What we're adding is the consensus engine—the piece that correlates discoveries across samples, proposes new branches, and enables curator oversight. It's a significant undertaking, touching the data model, the API layer, and eventually a curator dashboard for managing proposals.

If you're interested in contributing—whether as an early tester, a domain expert, or a developer—I'd love to hear from you. The code is [open source](https://github.com/JamesKane/decodingus), and the [roadmap](https://github.com/JamesKane/decodingus/blob/main/documents/planning/post-mvp-roadmap.md) is public.

More to come as we build it.

---

*This is part of an ongoing series about the DecodingUs project. Previous posts: [Personal Genomics on an Orange Pi 5 Plus](/genomics/2025/04/19/Personal-Genomics-on-an-Orange-Pi-5-Plus.html)*
