"""WEEK 1 - Step 1.4b: keep only real decisions, not the one-line orders ("certiorari denied").

Why: CourtListener stores many Supreme Court orders as their own clusters (188,045 clusters for
2000-2024, while the Court decides about 70-90 cases a year). The Supreme Court Database (SCDB)
lists the real decisions, but CourtListener links it only up to 2019.

Rule (SPEC section 2):
  keep a cluster if it has an scdb_id,
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

linked_years = {c["date_filed"][:4] for c in clusters if c["scdb_id"]}
calib = [c for c in clusters if c["date_filed"][:4] in linked_years]

print(f"Years with SCDB links: {min(linked_years)}-{max(linked_years)} "
      f"({len(calib):,} clusters, {sum(1 for c in calib if c['scdb_id']):,} with an scdb_id)")
print("Calibration on those years: a cluster is 'kept' if its longest opinion has >= N words")
print(f"{'N words':>8} {'kept':>7} {'SCDB kept (recall)':>20} {'kept that are SCDB (precision)':>32}")
for n in THRESHOLDS:
    kept = [c for c in calib if longest[c["cluster_id"]] >= n]
    hits = sum(1 for c in kept if c["scdb_id"])
    total = sum(1 for c in calib if c["scdb_id"])
    print(f"{n:>8} {len(kept):>7,} {hits:>9,} ({hits / max(total, 1):.0%}){'':>4}"
          f"{hits:>14,} ({hits / max(len(kept), 1):.0%})")

if "--min-words" not in sys.argv:
    sys.exit("\nCalibration only. Choose N and run again with --min-words N to apply the rule.")

min_words = int(sys.argv[sys.argv.index("--min-words") + 1])
keep = {c["cluster_id"] for c in clusters
        if c["scdb_id"] or (c["date_filed"][:4] not in linked_years
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
print(f"Done: {len(clusters):,} clusters -> {len(keep):,} decisions kept "
      f"({sum(1 for c in clusters if c['scdb_id'] and c['cluster_id'] in keep):,} by SCDB, "
      f"the rest by >= {min_words} words), {n_ops:,} opinions kept.")
save_filter_report("scope", clusters_read=len(clusters), kept=len(keep), opinions_kept=n_ops,
                   min_words=min_words, scdb_years=f"{min(linked_years)}-{max(linked_years)}")
