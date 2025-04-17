---
layout: post
title:  "One Path Ends, Another Begins"
date:   2025-04-17 00:00:00 -0500
categories: ["genomics"]
tags: ["YDNA-Warehouse.org", "citizen science", "genetic genealogy"]
---

# One Path Ends

Over the last decade, there has been a tremendous boom in direct-2-consumer DNA sequencing options available to genealogists.
A challenge has been to collect and compare these results as the regulatory environments have shifted.  To that end I
established the [YDNA-Warehouse.org](https://ydna-warehouse.org/subject) for the purpose allowing individuals to contribute
their Y sequencing results along with some basic genealogical information to build out a human-scale family tree.  To support
other citizen scientists, the site has long provided the data for other sites such as Alex Williamson's [Big Tree](https://www.ytree.net).

In light of current world uncertainties, I made the decision that combined risks out-weigh the ability to keep funding a
very large hobby project with multiple terabytes of various storage classes in the cloud.  Therefore, the YDNA Warehouse
will cease operations on 9-May-2025.  Once the current server goes dark, there will be no record of the user accounts anywhere.
All data and backup images in Amazon Web Services, where the site is hosted, will be deleted.  The user contributed D2C
BAM files will also be removed from my private cloud where the analysis pipelines are run.  Due to the nature of anonymized 
data sharing Alex's site will still have copies of the files used in Big Tree.

# Another Begins

Early citizen science opportunities on the web included [SETI@Home](https://archive.org/details/0x-0_20221225), 
[Folding@Home](https://foldingathome.org), and other distributed computing projects.  Users participated by running a 
client-application on their home computers.  Multiple users received the same units of work and the results were checked
for consensus to ensure quality.  A large percentage of cost in time and money in the YDNA Warehouse is standardizing the
inputs and computing matching.  Using secure computing enclaves that run on end-user PCs would allow their devices to
exchange encrypted DNA attributes to build the matching graphs.  The enclaves could also be hosted on traditional
cloud-service providers when the user's computing device is a tablet or laptop.

Recently [Bluesky](https://bsky.app) published a specification for [@ATProtocol](https://atproto.com).  The federated 
network specified in the protocol allows the users to truly own their data in their own Personal Data Store (PDS).  The
PDS can be self-hosted along with the compute client or even managed for them by the vendor where they tested originally.
Matching becomes a function of joining the network and broadcasting an interest to match by sex determined haplogroup or
populations inferred from their autosomal DNA.

Orchestrating all of this is an App View designed for the needs of the citizen scientist interested in genealogy or anthropology
applications.  The central application routes messages between the users to accept a matching request, gather the consensus,
and update the results.  It should also be possible to build out refinements to public resources such as a Y DNA and mtDNA
tree using consent from the users.

And so this gives a high-level sketch of what my thoughts on the direction citizen science needs to head to truly leverage
direct-2-consumer testing.  Any future system must democratize the compute, hosting and time costs especially
with PacBio HiFi where sequencing libraries measure around 0.5TB for a single individual.  Over the next few months I plan to
detail more specific design here.  Then when it comes time to start coding set up a new public code repository on GitHub for
any who might be interested in collaborating.