#!/usr/bin/env python3
"""
Y-DNA haplogroup placement from a CHM13/hs1-coordinate VCF, using the
Decoding-Us Y-tree API (https://decoding-us.com/api/docs/).

Companion script for the pangenome variant-calling blog series:
  jameskane.blog/genomics/2026/06/09/finding-a-y-haplogroup-in-a-pangenome.html
  jameskane.blog/genomics/2026/06/23/try-it-yourself-a-pangenome-variant-calling-bench.html
Provided as-is for readers to experiment with. Needs samtools + bcftools on PATH,
and `vg` (to extract the CHM13 chrY reference) unless you pass --ref-fasta. Works
on a graph VCF, a CHM13-surjected BAM, or a linear CHM13 CRAM; see --help.

Approach
--------
The /api/v1/y-tree endpoint returns the full Y phylogeny as SubcladeDTO nodes
(name, parentName, isBackbone, defining variants). Each variant carries
coordinates per assembly; we use the `chrY [hs1]` key (= T2T-CHM13v2.0), which
matches a VCF called against CHM13. Each coordinate gives {start, anc, der}:
the phylogenetically ancestral and derived alleles.

Important: hs1/CHM13v2.0's chrY is HG002's Y (haplogroup J), so the *reference*
base is ancestral for R-lineage SNPs but DERIVED for the ancient backbone
shared between J and R. We therefore need the CHM13 chrY reference base to
interpret sites with no VCF record. Per-SNP state:

  * VCF record, ALT == der            -> DER_CALL     (positive evidence)
  * VCF record, ALT == anc            -> ANC_CALL     (contradiction)
  * VCF record is multi-base (MNP/indel rep) -> COMPLEX (skip)
  * no record, ref == der             -> DER_refmatch (backbone, consistent)
  * no record, ref == anc             -> ANC_nodata   (AMBIGUOUS: ref-match or
                                                        no-coverage; not counted
                                                        as contradiction)

Placement uses a parsimony path-supported descent (cf. yhaplo, Poznik 2016;
pathPhynder, Martiniano et al. 2022), which is resilient to the two things that
defeat a naive "deepest derived node" search -- missing terminal markers and
isolated artifactual derived calls in the repetitive Y:

  GATE   a child branch is traversable only if it has net positive derived
         support at the branch itself (support = DER_CALL + DER_refmatch >
         ANC_CALL). This forbids tunnelling through unsupported branches, so an
         isolated deep artifact -- reachable only via its unsupported ancestors
         -- is never reached; the descent halts at the deepest supported node.
  ROUTE  among traversable children, step into the one whose SUBTREE holds the
         most positive variant calls (look-ahead), so the ancient backbone
         routes correctly even where an intermediate branch (e.g. HIJK) is only
         weakly ref-matched but leads to the signal-rich R subtree.
  REPORT the deepest node with positive VARIANT evidence (DER_CALL), trimming any
         ref-match-only tail so a single coincidental ref-match cannot extend a
         terminal call.

Markers with no record are treated as no-data, never as ancestral, because a
sites-only VCF cannot distinguish ref-match from missing coverage. Validated:
HG01243's graph-deconstruct genotypes resolve to its known terminal R1b-DF27,
while the donor's reads resolve honestly to R1b-P312 (its true sub-P312 lineage
is absent from the panel) with no artifact misplacement.

Usage
-----
  python3 y_haplogroup.py --vcf sample.vcf.gz \
      --gbz pangenome.gbz                        # extracts CHM13 chrY ref via vg
  # or supply a CHM13 chrY FASTA directly with --ref-fasta chrY_chm13.fa
  # BAM/CRAM pileup mode:
  python3 y_haplogroup.py --bam sample.chm13.cram --contig chrY \
      --ref-fasta chm13v2.0.fa
"""
import argparse, json, os, re, subprocess, sys, urllib.request

API = "https://decoding-us.com/api/v1"
HS1 = "chrY [hs1]"
REF_PATH = "CHM13#0#chrY"

# When genotyping from a BAM pileup, this holds {pos: called_base} (filtered).
# It takes precedence over the VCF/ref logic in state(): every covered marker is
# a real call (derived OR ancestral), so it removes the sites-only-VCF ambiguity
# between ref-match and missing coverage.
BAM_CALLS = None


def sh(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout


def load_ytree(cache, root=None):
    if os.path.exists(cache):
        return json.load(open(cache))
    url = f"{API}/y-tree" + (f"?rootHaplogroup={root}" if root else "")
    sys.stderr.write(f"[ytree] downloading {url}\n")
    data = json.load(urllib.request.urlopen(url, timeout=180))
    json.dump(data, open(cache, "w"))
    return data


def load_ref(ref_fasta, gbz, vg, cache):
    """Return the CHM13 chrY sequence as a 1-based-indexable string."""
    fa = ref_fasta
    if not fa:
        fa = cache
        if not os.path.exists(fa):
            sys.stderr.write(f"[ref] extracting {REF_PATH} from {gbz}\n")
            with open("/tmp/_ypath.txt", "w") as fh:
                fh.write(REF_PATH + "\n")
            sh(f"{vg} paths -x {gbz} -F -p /tmp/_ypath.txt > {fa}")
    seq = []
    for line in open(fa):
        if not line.startswith(">"):
            seq.append(line.strip())
    return "".join(seq)


def load_vcf_chrY(vcf, sample=None):
    """Load chrY records as {pos: (REF, [ALT...], GT)} for one sample.

    Works for both a graph-VCF whose contig is 'CHM13#0#chrY' and a read-VCF
    whose contig is 'chrY' -- we query %CHROM and keep rows ending in 'chrY',
    which sidesteps region-index issues with '#' in contig names. `sample`
    selects a column from a multi-sample VCF (e.g. vg deconstruct output).
    """
    s = f"-s {sample} " if sample else ""
    out = sh(f"bcftools query {s}-f '%CHROM\\t%POS\\t%REF\\t%ALT\\t[%GT]\\n' {vcf}")
    d = {}
    for line in out.splitlines():
        chrom, p, r, a, gt = line.split("\t")
        if not chrom.endswith("chrY"):
            continue
        d[int(p)] = (r.upper(), [x.upper() for x in a.split(",")], gt)
    return d


def hs1_snps(node):
    out = []
    for v in node.get("variants") or []:
        c = (v.get("coordinates") or {}).get(HS1)
        if c and v.get("variantType") == "SNP":
            out.append((v["name"], c["start"], c["anc"].upper(), c["der"].upper()))
    return out


_PILEUP_RE = re.compile(r"\^.|\$")


def load_bam_calls(bam, ref_fasta, positions, mapq, baseq, min_depth, min_ab, contig=REF_PATH):
    """Genotype `positions` (chrY 1-based) from a BAM/CRAM via samtools mpileup.

    Counts high-quality bases per site (MAPQ>=mapq, baseQ>=baseq), calls the
    majority base if depth>=min_depth and its fraction>=min_ab (the haploid-Y
    allele-balance filter that rejects paralog/mismapping). Returns {pos: base}.
    `contig` is the chrY name in the BAM/CRAM header (e.g. 'chrY' for a linear
    CHM13 CRAM, 'CHM13#0#chrY' for a surjected-from-graph BAM).
    """
    bed = "/tmp/_yhap_targets.bed"
    with open(bed, "w") as fh:
        for p in positions:
            fh.write(f"{contig}\t{p - 1}\t{p}\n")
    # -r restricts decoding to the chrY contig (so a CRAM with other contigs is
    # not scanned sequentially, which would demand a whole-genome reference); -l
    # filters output to the target marker positions.
    out = sh(f"samtools mpileup -r {contig} -q {mapq} -Q {baseq} -l {bed} "
             f"-f {ref_fasta} {bam} 2>/dev/null")
    calls = {}
    for line in out.splitlines():
        f = line.split("\t")
        if len(f) < 5:
            continue
        pos, refb, bases = int(f[1]), f[2].upper(), f[4]
        bases = _PILEUP_RE.sub("", bases)        # strip read-start(^q)/read-end($)
        bases = re.sub(r"[+-](\d+)", lambda m: "#" * (len(m.group(0)) + int(m.group(1))), bases)
        cnt = {}
        i = 0
        while i < len(bases):
            ch = bases[i]
            if ch == "#":                         # indel run marker (skip its bases)
                i += 1
                continue
            if ch in ".,":
                cnt[refb] = cnt.get(refb, 0) + 1
            elif ch in "ACGTacgt":
                b = ch.upper(); cnt[b] = cnt.get(b, 0) + 1
            i += 1
        dp = sum(cnt.values())
        if dp < min_depth:
            continue
        top = max(cnt, key=cnt.get)
        if cnt[top] / dp >= min_ab:
            calls[pos] = top
    return calls


def state(pos, anc, der, SEQ, vcf):
    if BAM_CALLS is not None:
        b = BAM_CALLS.get(pos)
        if b is None:
            return "NODATA"
        if b == der:
            return "DER_CALL"
        if b == anc:
            return "ANC_CALL"
        return "OTHER"
    rec = vcf.get(pos)
    if rec:
        ref, alts, gt = rec
        idx = {int(t) for t in gt.replace("|", "/").split("/") if t.isdigit()}
        if idx and not (len(ref) > 1 or any(len(a) > 1 for a in alts)):
            called = {ref if i == 0 else (alts[i - 1] if i - 1 < len(alts) else "?") for i in idx}
            if der in called:
                return "DER_CALL"
            if anc in called:
                return "ANC_CALL"
            return "OTHER"
        if len(ref) > 1 or any(len(a) > 1 for a in alts):
            return "COMPLEX"
        # all-missing GT (e.g. '.|.' from a path that didn't span the snarl):
        # fall through to reference logic, same as an absent record.
    r = SEQ[pos - 1].upper()
    if r == der:
        return "DER_refmatch"
    if r == anc:
        return "ANC_nodata"
    return "NODATA"


def score(node, SEQ, vcf):
    """Return (der_call, der_refmatch, anc_call) for a node's hs1 SNPs.

    der_call    = positive variant evidence (ALT == derived)
    der_refmatch= consistent with derived via reference match (ancient backbone
                  shared with the HG002/J reference)
    anc_call    = hard contradiction (sample explicitly called ancestral)
    """
    dc = dr = ac = 0
    for _, pos, a, d in hs1_snps(node):
        s = state(pos, a, d, SEQ, vcf)
        dc += s == "DER_CALL"
        dr += s == "DER_refmatch"
        ac += s == "ANC_CALL"
    return dc, dr, ac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vcf", help="genotype source: a VCF in CHM13 coords")
    ap.add_argument("--bam", help="genotype source: a CHM13-surjected BAM (pileup mode)")
    ap.add_argument("--sample", default=None, help="sample column to use (multi-sample VCF)")
    ap.add_argument("--min-mapq", type=int, default=20, help="BAM: min read MAPQ [20]")
    ap.add_argument("--min-baseq", type=int, default=20, help="BAM: min base quality [20]")
    ap.add_argument("--min-depth", type=int, default=3, help="BAM: min HQ depth to call [3]")
    ap.add_argument("--min-ab", type=float, default=0.85,
                    help="BAM: min majority-allele fraction (haploid-Y allele balance) [0.85]")
    ap.add_argument("--contig", default=REF_PATH,
                    help="BAM/CRAM: chrY contig name ('chrY' for a linear CHM13 CRAM; "
                         f"'{REF_PATH}' for a graph-surjected BAM) [{REF_PATH}]")
    ap.add_argument("--gbz", help="GBZ to extract CHM13 chrY ref from (if no --ref-fasta)")
    ap.add_argument("--ref-fasta", help="CHM13 chrY FASTA (overrides --gbz extraction)")
    ap.add_argument("--vg", default="vg", help="path to the vg binary [vg]")
    ap.add_argument("--root", default=None, help="optional rootHaplogroup to limit the tree")
    ap.add_argument("--ytree-cache", default="/tmp/ytree_full.json")
    ap.add_argument("--ref-cache", default="/tmp/chrY_chm13.fa")
    ap.add_argument("--min-support", type=int, default=1,
                    help="min net derived support (DER_CALL+DER_refmatch) to traverse a branch [1]")
    ap.add_argument("--no-collapse", action="store_true",
                    help="disable collapsing marker-less nodes. By default, nodes with no "
                         "usable SNP markers (e.g. indel-only branches like A353) are spliced "
                         "out and their children re-parented to the nearest informative "
                         "ancestor (recursively), so the strict gate is not blocked by a "
                         "branch we simply cannot genotype. Sample-independent / structural.")
    ap.add_argument("--conflict-tol", type=float, default=0.0,
                    help="traverse past a branch with a lone conflict if downstream subtree "
                         "DER support >= this factor x ANC_CALL; 0 disables. Use with dense "
                         "(BAM) data only [0]")
    ap.add_argument("--expect", default=None, help="expected terminal haplogroup, for reporting")
    args = ap.parse_args()

    tree = load_ytree(args.ytree_cache, args.root)
    byname = {n["name"]: n for n in tree}
    children = {}
    for n in tree:
        children.setdefault(n.get("parentName"), []).append(n["name"])
    roots = [n["name"] for n in tree if n.get("parentName") not in byname]

    # Collapse marker-less nodes: a node with no usable SNP markers (e.g. an
    # indel-only branch like R1b-A353) cannot be genotyped here, so it must not
    # block a strict descent. We splice such nodes out, re-parenting their
    # children to the nearest SNP-bearing ancestor (recursively). This is purely
    # structural / sample-independent, so it is safe for both sparse VCF and
    # dense BAM input -- unlike a data-driven "pass-through", which would tunnel
    # through genuinely no-data branches in a sparse VCF.
    def has_markers(name):
        return len(hs1_snps(byname[name])) > 0
    collapsed = 0
    if not args.no_collapse:
        eff_children = {}
        for parent in list(children):
            if parent is not None and parent in byname and not has_markers(parent):
                continue  # this node is spliced out; its parent will absorb its kids
            stack = list(children.get(parent, []))
            kept = []
            while stack:
                c = stack.pop()
                if has_markers(c) or c in roots:
                    kept.append(c)
                else:
                    stack.extend(children.get(c, []))  # splice: promote c's children
            eff_children[parent] = kept
        collapsed = sum(1 for n in byname
                        if n not in roots and not has_markers(n))
        children = eff_children

    if not (args.vcf or args.bam):
        ap.error("supply --vcf or --bam")
    vcf = {}
    SEQ = None
    if args.bam:
        # BAM/CRAM mode classifies from pileup calls, not the reference sequence,
        # so we do NOT load the (possibly whole-genome) reference into memory --
        # it is only passed to samtools for decoding. The reference MUST be the
        # exact one the BAM/CRAM was aligned to (e.g. CHM13v2.0 for a linear CRAM).
        global BAM_CALLS
        positions = sorted({pos for n in tree for _, pos, _a, _d in hs1_snps(n)})
        ref_fa = args.ref_fasta or args.ref_cache
        BAM_CALLS = load_bam_calls(args.bam, ref_fa, positions, args.min_mapq,
                                   args.min_baseq, args.min_depth, args.min_ab, args.contig)
        sys.stderr.write(f"[bam] {len(BAM_CALLS)}/{len(positions)} marker sites called "
                         f"(MAPQ>={args.min_mapq} baseQ>={args.min_baseq} dp>={args.min_depth} "
                         f"AB>={args.min_ab}); [tree] {len(tree)} nodes, "
                         f"{collapsed} marker-less collapsed\n")
    else:
        SEQ = load_ref(args.ref_fasta, args.gbz, args.vg, args.ref_cache)
        vcf = load_vcf_chrY(args.vcf, args.sample)
        sys.stderr.write(f"[vcf] {len(vcf)} chrY sites (sample={args.sample}); "
                         f"[tree] {len(tree)} nodes; roots={roots}\n")

    # ---- Parsimony path-supported descent (pathPhynder/yhaplo-style) ----------
    # Descend from the root one branch at a time, with two coupled rules:
    #
    #   GATE (per-branch support): a child branch is traversable only if it
    #   carries positive *net* derived support at the branch itself --
    #       support = DER_CALL + DER_refmatch ,  conflict = ANC_CALL
    #       traversable iff support >= min_support AND support > conflict
    #   This forbids "tunnelling" through unsupported branches, so an isolated
    #   deep artifact (reachable only via its unsupported ancestors) is never
    #   reached, and the descent halts at the deepest genuinely supported node.
    #
    #   ROUTE (subtree look-ahead): among traversable children, step into the
    #   one whose SUBTREE carries the most positive variant calls (DER_CALL).
    #   This routes the ancient backbone correctly even where an intermediate
    #   branch (e.g. HIJK) is only weakly ref-matched but leads to the signal-
    #   rich R subtree, and it ignores shallow artifacts whose subtree is empty.
    #
    # DER_refmatch lets the backbone (shared with the HG002/J reference) route;
    # DER_CALL drives the R-specific descent and the subtree look-ahead.
    def supp(name):
        dc, dr, ac = score(byname[name], SEQ, vcf)
        return dc + dr, ac, dc  # support, conflict, der_call

    sys.setrecursionlimit(100000)
    subtree_dc = {}

    def calc_subtree(name):
        tot = score(byname[name], SEQ, vcf)[0]
        for ch in children.get(name, []):
            tot += calc_subtree(ch)
        subtree_dc[name] = tot
        return tot

    for rt in roots:
        calc_subtree(rt)

    node = roots[0]
    path = [node]
    ambiguous = []
    while True:
        valid = []
        for ch in children.get(node, []):
            s, c, dc = supp(ch)              # s=DER_CALL+DER_refmatch, c=ANC_CALL
            sub = subtree_dc[ch]
            if s >= args.min_support and s > c:
                ok = True                    # direct net positive support
            elif args.conflict_tol > 0 and c > 0 and sub >= max(args.min_support,
                                                                args.conflict_tol * c):
                ok = True                    # downstream support overwhelms a lone
                                             # conflict (likely a repeat-region artifact)
            else:
                ok = False
            if ok:
                valid.append((sub, dc, s, ch))
        if not valid:
            break
        valid.sort()
        strong = [v for v in valid if v[1] >= 1]  # children with real variant calls
        if len(strong) > 1:
            ambiguous.append((node, [v[3] for v in strong]))
        node = valid[-1][3]
        path.append(node)

    # Report the deepest node with positive VARIANT evidence (DER_CALL); trim any
    # ref-match-only tail, since a single coincidental ref-match must not extend a
    # terminal call. (Backbone routing above still used ref-match + subtree look-
    # ahead, so it is unaffected.) Falls back to the descent end for a sample that
    # only reaches the ref-matched backbone.
    descent_end = node
    terminal = next((nm for nm in reversed(path) if score(byname[nm], SEQ, vcf)[0] > 0),
                    descent_end)
    path = path[: path.index(terminal) + 1]
    print("=== Y-DNA haplogroup placement (parsimony path-supported descent) ===")
    print(f"Terminal haplogroup: {terminal}")
    tdc, tdr, tac = score(byname[terminal], SEQ, vcf)
    print(f"  terminal branch support: DER_CALL={tdc} DER_refmatch={tdr} ANC_CALL={tac}")
    if descent_end != terminal:
        print(f"  (descent continued via ref-match only to {descent_end}; not reported as "
              f"terminal -- no positive variant evidence below {terminal})")
    if ambiguous:
        print("  WARNING: ambiguous branching (>1 supported child) at: "
              + "; ".join(f"{p}->{ch}" for p, ch in ambiguous)
              + "  -- possible paralog/contamination.")
    print("\nSupported path (root -> terminal), per-node [DER_CALL / DER_refmatch / ANC_CALL]:")
    for nm in path:
        d, r, a = score(byname[nm], SEQ, vcf)
        flag = "" if d else "  (backbone ref-match only)"
        print(f"  {nm:<28} [{d:>3} / {r:>4} / {a}]{flag}")

    if args.expect:
        # Report how the expected terminal relates to what we could resolve.
        cur, chain = args.expect, []
        while cur and cur in byname:
            chain.append(cur)
            cur = byname[cur].get("parentName")
        chain = chain[::-1]
        if args.expect in byname:
            resolved = path[-1]
            # Measure the gap in lineage terms (chain may include nodes that were
            # collapsed out of the descent path, so raw path depth is not comparable).
            print(f"\nExpected terminal: {args.expect}")
            print(f"Resolved to:       {resolved}")
            if resolved == args.expect:
                print("  -> FULLY RESOLVED to the expected terminal.")
            elif resolved in chain:
                gap = (len(chain) - 1) - chain.index(resolved)
                print(f"  -> On the correct lineage but {gap} node(s) short of the "
                      f"expected terminal (terminal-defining markers not callable here).")
            else:
                print("  -> Resolved node is NOT on the expected lineage.")
        else:
            print(f"\nExpected terminal {args.expect} not found in tree.")


if __name__ == "__main__":
    main()
