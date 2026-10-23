"""WEEK 1 - Step 1.4b: keep only real decisions, not the one-line orders ("certiorari denied").

Why: CourtListener stores many Supreme Court orders as their own clusters (188,045 clusters for
2000-2024, while the Court decides about 70-90 cases a year). The Supreme Court Database (SCDB)
lists the real decisions, but CourtListener links it only up to 2019.

Rule (SPEC section 2), the same for every year:
  keep a decision (its clusters with the same docket and date) if one of them has an scdb_id,
  or if its longest opinion has >= MIN_WORDS words.
MIN_WORDS is chosen on 2000-2019, where SCDB tells us the right answer. The long texts outside SCDB
are mostly real opinions too (dissents from a denial, in-chambers opinions, copies of SCDB cases).

Run AFTER filter_clusters and filter_opinions, BEFORE filter_citation_map:
  python -m scripts.scope_decisions                  # only shows the calibration table
  python -m scripts.scope_decisions --min-words 700  # applies the rule
The first time the rule is applied, the full files are kept as clusters_all.jsonl and
opinions_all.jsonl, so the rule can be changed and applied again."""
import gzip
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from app import config
from app.bulk import save_filter_report

TAG = re.compile(r"<[^>]+>")
TEXT_FIELDS = ["html_with_citations", "html", "xml_harvard", "html_lawbox", "html_columbia",
               "html_anon_2020", "plain_text"]
THRESHOLDS = [100, 200, 300, 500, 700, 1000, 1500, 2000]


def source(name):
    """The full (unscoped) file: the backup if the rule was already applied once."""
    full = config.WORK / f"{name}_all.jsonl"
    return full if full.exists() else config.WORK / f"{name}.jsonl"


def words(op):
    text = next((op[f] for f in TEXT_FIELDS if op.get(f)), "")
    return len(TAG.sub(" ", text).split())


clusters = [json.loads(line) for line in open(source("clusters"))]
if clusters and "scdb_id" not in clusters[0]:
    sys.exit("clusters.jsonl has no scdb_id: run `python -m scripts.filter_clusters` again first.")

longest = defaultdict(int)                       # cluster id -> words of its longest opinion
for line in open(source("opinions")):
    op = json.loads(line)
    longest[op["cluster_id"]] = max(longest[op["cluster_id"]], words(op))

def group(c):
    """Duplicate clusters of one decision share the docket and the date (merged again at loading)."""
    return c["docket_id"], c["date_filed"]


scdb_groups = {group(c) for c in clusters if c["scdb_id"]}
in_scdb = {c["cluster_id"]: group(c) in scdb_groups for c in clusters}
group_words = defaultdict(int)                  # decision -> words of its longest opinion
for c in clusters:
    group_words[group(c)] = max(group_words[group(c)], longest[c["cluster_id"]])
linked_years = {c["date_filed"][:4] for c in clusters if c["scdb_id"]}
calib = {group(c) for c in clusters if c["date_filed"][:4] in linked_years}   # decisions
names = {group(c): c for c in clusters}

print(f"Years with SCDB links: {min(linked_years)}-{max(linked_years)}: "
      f"{len(calib):,} decisions (duplicate clusters merged), "
      f"{len(calib & scdb_groups):,} of them in SCDB")
print("Calibration on those years: a decision is 'kept' if its longest opinion has >= N words")
print(f"{'N words':>8} {'kept':>7} {'SCDB kept (recall)':>20} {'kept that are SCDB (precision)':>32}")
total = len(calib & scdb_groups)
for n in THRESHOLDS:
    kept = {g for g in calib if group_words[g] >= n}
    hits = len(kept & scdb_groups)
    print(f"{n:>8} {len(kept):>7,} {hits:>9,} ({hits / max(total, 1):.0%}){'':>4}"
          f"{hits:>14,} ({hits / max(len(kept), 1):.0%})")


def show(g):
    c = names[g]
    return (f"  {c['date_filed']}  {group_words[g]:>6} words  {c['case_name'][:55]:55}  "
            f"https://www.courtlistener.com/opinion/{c['cluster_id']}/x/")


print("\nExamples kept at 1000 words but NOT in SCDB (check what they are):")
for g in sorted(g for g in calib - scdb_groups if group_words[g] >= 1000)[:12]:
    print(show(g))
print("Examples in SCDB with no opinion text (>= 100 words):")
for g in sorted(g for g in calib & scdb_groups if group_words[g] < 100)[:6]:
    print(show(g))

if "--min-words" not in sys.argv:
    sys.exit("\nCalibration only. Choose N and run again with --min-words N to apply the rule.")

min_words = int(sys.argv[sys.argv.index("--min-words") + 1])
keep = {c["cluster_id"] for c in clusters
        if in_scdb[c["cluster_id"]] or group_words[group(c)] >= min_words}
kept_clusters = [c for c in clusters if c["cluster_id"] in keep]

# ---- Merge copies of one decision (step 1.4c) ----
# CourtListener sometimes stores one decision as several clusters, under different dockets or
# with differently written names. Clusters are joined (union-find) when they share the same date and
# the same docket, OR the same case name (letters and digits only), OR the same official citation.
parent = {c["cluster_id"]: c["cluster_id"] for c in kept_clusters}


def root(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def join_by(key_of):
    first = {}
    for c in kept_clusters:
        for key in key_of(c):
            if key in first:
                a, b = root(first[key]), root(c["cluster_id"])
                parent[max(a, b)] = min(a, b)
            else:
                first[key] = c["cluster_id"]


def name_key(c):
    return re.sub(r"[^a-z0-9]", "", c["case_name"].lower())[:40]


official = defaultdict(set)                      # cluster id -> its U.S. / S. Ct. / L. Ed. citations
cit_file = config.WORK / "citations.csv.gz"
if cit_file.exists():
    for line in gzip.open(cit_file, "rt"):
        vol, rep, page, cid = line.rstrip("\n").split("\t")
        if rep in ("U.S.", "S. Ct.", "L. Ed. 2d") and int(cid) in parent:
            official[int(cid)].add(f"{vol} {rep} {page}")
else:
    print("(citations.csv.gz not found: copies with the same citation are not merged)")

join_by(lambda c: [("docket", c["docket_id"], c["date_filed"])])
join_by(lambda c: [("name", name_key(c), c["date_filed"])])
join_by(lambda c: [("cite", cite, c["date_filed"]) for cite in official[c["cluster_id"]]])

members = defaultdict(list)
for c in kept_clusters:
    c["decision_group"] = root(c["cluster_id"])  # the loader merges clusters with the same group
    members[c["decision_group"]].append(c)
merged = [cs for cs in members.values() if len({group(c) for c in cs}) > 1]
print(f"\nCopies merged (same date + same name or same citation, different docket): {len(merged)} decisions")
for cs in merged[:6]:
    print("  " + " | ".join(f"{c['case_name'][:38]} ({c['date_filed']}, cluster {c['cluster_id']})" for c in cs[:3]))

# ---- Write the scoped files (the full ones are kept once as *_all.jsonl) ----
for name in ("clusters", "opinions"):
    full = config.WORK / f"{name}_all.jsonl"
    if not full.exists():
        shutil.copy(config.WORK / f"{name}.jsonl", full)

n_ops = 0
with open(config.WORK / "clusters.jsonl", "w") as out:
    for c in kept_clusters:
        out.write(json.dumps(c) + "\n")
with open(config.WORK / "opinions.jsonl", "w") as out:
    for line in open(source("opinions")):
        if json.loads(line)["cluster_id"] in keep:
            out.write(line)
            n_ops += 1

per_year = Counter(cs[0]["date_filed"][:4] for cs in members.values())
by_scdb = sum(1 for cs in members.values() if any(in_scdb[c["cluster_id"]] for c in cs))
print("\nDecisions per year:", ", ".join(f"{y}: {per_year[y]}" for y in sorted(per_year)))
print(f"Done: {len(clusters):,} clusters -> {len(keep):,} clusters kept = {len(members):,} decisions "
      f"({by_scdb:,} in SCDB, the others by >= {min_words} words; {len(merged)} merged from copies), "
      f"{n_ops:,} opinions kept.")
save_filter_report("scope", clusters_read=len(clusters), clusters_kept=len(keep), decisions=len(members),
                   decisions_in_scdb=by_scdb, copies_merged=len(merged), opinions_kept=n_ops,
                   min_words=min_words, scdb_years=f"{min(linked_years)}-{max(linked_years)}")
