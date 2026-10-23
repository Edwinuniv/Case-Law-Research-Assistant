"""WEEK 1 - Step 1.4b: keep only real decisions, not the one-line orders ("certiorari denied").

Why: CourtListener stores many Supreme Court orders as their own clusters (188,045 clusters for
2000-2024, while the Court decides about 70-90 cases a year). The Supreme Court Database (SCDB)
lists the real decisions, but CourtListener links it only up to 2019.

Rule (SPEC section 2):
  keep a cluster if it (or a duplicate cluster: same docket, same date) has an scdb_id,
  or if it was filed in a year without SCDB links and its longest opinion has >= MIN_WORDS words.
MIN_WORDS is chosen on 2000-2019, where SCDB tells us the right answer.

Run AFTER filter_clusters and filter_opinions, BEFORE filter_citation_map:
  python -m scripts.scope_decisions                  # only shows the calibration table
  python -m scripts.scope_decisions --min-words 700  # applies the rule
The first time the rule is applied, the full files are kept as clusters_all.jsonl and
opinions_all.jsonl, so the rule can be changed and applied again."""
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
        if in_scdb[c["cluster_id"]] or (c["date_filed"][:4] not in linked_years
                            and longest[c["cluster_id"]] >= min_words)}

for name in ("clusters", "opinions"):           # keep the full files once, as *_all.jsonl
    full = config.WORK / f"{name}_all.jsonl"
    if not full.exists():
        shutil.copy(config.WORK / f"{name}.jsonl", full)

n_ops = 0
with open(config.WORK / "clusters.jsonl", "w") as out:
    for c in clusters:
        if c["cluster_id"] in keep:
            out.write(json.dumps(c) + "\n")
with open(config.WORK / "opinions.jsonl", "w") as out:
    for line in open(source("opinions")):
        if json.loads(line)["cluster_id"] in keep:
            out.write(line)
            n_ops += 1

per_year = Counter(c["date_filed"][:4] for c in clusters if c["cluster_id"] in keep)
print("\nKept per year:", ", ".join(f"{y}: {per_year[y]}" for y in sorted(per_year)))
kept_groups = {group(c) for c in clusters if c["cluster_id"] in keep}
print(f"Done: {len(clusters):,} clusters -> {len(keep):,} clusters kept = {len(kept_groups):,} decisions "
      f"({len(kept_groups & scdb_groups):,} by SCDB, "
      f"the rest by >= {min_words} words), {n_ops:,} opinions kept.")
save_filter_report("scope", clusters_read=len(clusters), kept=len(keep), decisions=len(kept_groups), opinions_kept=n_ops,
                   min_words=min_words, scdb_years=f"{min(linked_years)}-{max(linked_years)}")
