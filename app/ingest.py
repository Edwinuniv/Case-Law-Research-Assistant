"""Loading the filtered files (data/work) into PostgreSQL."""
import gzip
import json
import hashlib
import re
from collections import defaultdict
from app import config, db
from app.chunking import pick_text, OPINION_TYPES


def opinion_label(op):
    label = OPINION_TYPES.get(op.get("type"), "Opinion")
    if op.get("per_curiam"):
        return f"{label} (per curiam)"
    author = (op.get("author_str") or "").strip()
    return f"{label} ({author})" if author else label


def shingles(text, n=5):
    """The set of 5-word sequences of a text: two copies of one opinion share almost all of them."""
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    return {" ".join(words[i:i + n]) for i in range(max(len(words) - n + 1, 1))}


def same_text(a, b, threshold=0.6):
    """True if two opinion texts are copies (Jaccard similarity of their 5-word sequences)."""
    return len(a & b) / max(len(a | b), 1) >= threshold


def group_opinions(group, opinions_by_cluster):
    """One decision = several clusters (copies, or one cluster per separate opinion).
    Returns (main cluster, [(opinion, text, field)], copies skipped, opinions without text).
    Opinions of ALL clusters are kept, except copies of an opinion already kept."""
    def text_size(c):
        return sum(len(pick_text(o)[0]) for o in opinions_by_cluster[c["cluster_id"]])
    group = sorted(group, key=text_size, reverse=True)     # the main cluster has the most text
    kept, kept_shingles, copies, empty = [], [], 0, 0
    for c in group:
        for o in opinions_by_cluster[c["cluster_id"]]:
            text, field = pick_text(o)
            if not text:
                empty += 1
                continue
            sh = shingles(text)
            if any(same_text(sh, k) for k in kept_shingles):
                copies += 1
                continue
            kept.append((o, text, field))
            kept_shingles.append(sh)
    return group[0], kept, copies, empty


def _name_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def find_duplicate_decisions(con, days=60, threshold=0.8):
    """Copies of one decision that CourtListener stores twice, e.g. a slip opinion and a later
    version filed some days apart (Bruen: 6480696 and 7686272). Two decisions are copies when they
    have the same case name, dates at most `days` apart, and opinion texts at least `threshold`
    identical (5-word sequences). Same-name decisions with different texts stay apart
    (Bush v. Gore: the stay of Dec 9 and the decision of Dec 12, 2000).
    Returns (groups, pairs): groups = [(kept id, [merged ids])], pairs = every comparison made."""
    rows = con.execute("SELECT decision_id, case_name, date_filed FROM decisions").fetchall()
    by_name = defaultdict(list)
    for r in rows:
        by_name[_name_key(r["case_name"])].append(r)
    text_cache = {}

    def text_of(decision_id):
        if decision_id not in text_cache:
            texts = [r["text"] for r in con.execute(
                "SELECT text FROM opinions WHERE decision_id = %s ORDER BY opinion_id", (decision_id,))]
            words = " ".join(texts).split()
            text_cache[decision_id] = (len(words), shingles(" ".join(words[:6000])))
        return text_cache[decision_id]

    parent, pairs = {}, []

    def root(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for same in by_name.values():
        for i, a in enumerate(same):
            for b in same[i + 1:]:
                if abs((a["date_filed"] - b["date_filed"]).days) > days:
                    continue
                sa, sb = text_of(a["decision_id"])[1], text_of(b["decision_id"])[1]
                sim = len(sa & sb) / max(len(sa | sb), 1)
                copy = sim >= threshold
                pairs.append((a["decision_id"], b["decision_id"], a["case_name"], a["date_filed"],
                               b["date_filed"], round(sim, 3), copy))
                if copy:
                    ra, rb = root(a["decision_id"]), root(b["decision_id"])
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    members = defaultdict(list)
    for d in {x for p in pairs if p[6] for x in p[:2]}:
        members[root(d)].append(d)
    groups = []
    for ids in members.values():
        kept = max(ids, key=lambda d: (text_of(d)[0], -d))     # the copy with the most text
        groups.append((kept, sorted(d for d in ids if d != kept)))
    return groups, pairs


def merge_duplicate_decisions(log=print):
    """Keep one decision per group of copies; the others' cluster ids become aliases of it and
    their opinions and chunks are deleted (no new embeddings needed)."""
    with db.connect() as con:
        groups, pairs = find_duplicate_decisions(con)
        for kept, merged in groups:
            for d in merged:
                con.execute("UPDATE cluster_alias SET decision_id = %s WHERE decision_id = %s", (kept, d))
                con.execute("""UPDATE decisions k SET
                                 all_cluster_ids = (SELECT array_agg(DISTINCT x) FROM unnest(k.all_cluster_ids || m.all_cluster_ids) x),
                                 citations = (SELECT coalesce(array_agg(DISTINCT x), '{}') FROM unnest(k.citations || m.citations) x)
                               FROM decisions m WHERE k.decision_id = %s AND m.decision_id = %s""", (kept, d))
                con.execute("DELETE FROM decisions WHERE decision_id = %s", (d,))   # cascades to opinions, chunks
        n_chunks = con.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
    report = {"pairs_compared": len(pairs), "groups_merged": len(groups),
              "decisions_removed": sum(len(m) for _, m in groups),
              "merged": {str(k): m for k, m in groups}}
    meta = db.get_settings().get("index_meta")
    if meta:                                   # the index lost the copies' chunks
        db.set_setting("index_meta", {**meta, "chunks": n_chunks, "duplicates_merged": report["decisions_removed"]})
    db.save_report("duplicates", report)
    log(f"{len(groups)} groups of copies merged, {report['decisions_removed']} decisions removed "
        f"({len(pairs)} same-name pairs compared).")
    return report


def load_corpus():
    """clusters.jsonl + opinions.jsonl -> decisions, cluster_alias, opinions (SR10, SR11)."""
    clusters = {c["cluster_id"]: c for c in map(json.loads, open(config.WORK / "clusters.jsonl"))}
    opinions_by_cluster = defaultdict(list)
    for op in map(json.loads, open(config.WORK / "opinions.jsonl")):
        opinions_by_cluster[op["cluster_id"]].append(op)

    # Merge copies of one decision into one row. scripts/scope_decisions.py sets decision_group
    # (same date + same docket, name or official citation); otherwise: same docket and date.
    groups = defaultdict(list)
    for c in clusters.values():
        groups[c.get("decision_group") or (c["docket_id"], c["date_filed"])].append(c)

    report = {"clusters": len(clusters), "decisions": 0, "duplicates_merged": 0,
              "decisions_without_text": 0, "opinions": 0, "opinions_without_text": 0,
              "opinion_copies_skipped": 0,
              "rejected_without_licence": 0,
              "filters": {f.stem[7:]: json.load(open(f)) for f in sorted(config.WORK.glob("report_*.json"))}}
    with db.connect() as con:
        con.execute("TRUNCATE decisions, cluster_alias, opinions, chunks CASCADE")
        for group in groups.values():
            main, ops, copies, empty = group_opinions(group, opinions_by_cluster)
            report["opinion_copies_skipped"] += copies
            report["opinions_without_text"] += empty
            if not ops:
                report["decisions_without_text"] += 1
                continue
            licence = config.LICENCE
            if not licence:                                          # SR11
                report["rejected_without_licence"] += 1
                continue
            report["decisions"] += 1
            report["duplicates_merged"] += len(group) - 1
            con.execute("""INSERT INTO decisions (decision_id, all_cluster_ids, docket_id, docket_number,
                case_name, date_filed, source_url, licence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (main["cluster_id"], [c["cluster_id"] for c in group], main["docket_id"],
                         main["docket_number"], main["case_name"], main["date_filed"],
                         main["source_url"], licence))
            for c in group:
                con.execute("INSERT INTO cluster_alias VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (c["cluster_id"], main["cluster_id"]))
            for o, text, field in ops:
                con.execute("""INSERT INTO opinions (opinion_id, decision_id, cluster_id, type, label,
                    author, text, text_field, sha256, licence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (o["opinion_id"], main["cluster_id"], o["cluster_id"], o.get("type"),
                             opinion_label(o), o.get("author_str"), text, field,
                             hashlib.sha256(text.encode()).hexdigest(), licence))
                report["opinions"] += 1
    refresh_decision_citations()
    report["duplicate_decisions_removed"] = merge_duplicate_decisions()["decisions_removed"]
    db.save_report("corpus", report)
    return report


def load_citations():
    """citations.csv.gz -> citations (SR12); citation_map.csv -> citation_map."""
    with db.connect() as con:
        con.execute("DROP INDEX IF EXISTS citations_lookup")
        con.execute("TRUNCATE citations, citation_map")
        n = 0
        with con.cursor().copy("COPY citations (volume, reporter, page, cluster_id) FROM STDIN") as cp, \
                gzip.open(config.WORK / "citations.csv.gz", "rt") as f:
            for line in f:
                cp.write(line)
                n += 1
        m = 0
        with con.cursor().copy("COPY citation_map (citing_opinion_id, cited_opinion_id, cited_cluster_id, depth) "
                               "FROM STDIN WITH (FORMAT csv)") as cp, open(config.WORK / "citation_map.csv") as f:
            for line in f:
                cp.write(line)
                m += 1
        print("Building the citation index (can take a few minutes)...")
        con.execute(db.INDEXES)
    refresh_decision_citations()
    db.save_report("citations", {"citations_loaded": n, "citation_map_rows": m})


def refresh_decision_citations():
    """Copy each decision's own citations (e.g. '603 U.S. 593') from the citations table.
    One join that reads the 17.8 million citations once (a sub-query per decision read them
    once PER decision, which took hours)."""
    with db.connect() as con:
        con.execute("""UPDATE decisions d SET citations = x.cites
            FROM (SELECT a.decision_id,
                         array_agg(DISTINCT c.volume || ' ' || c.reporter || ' ' || c.page) AS cites
                  FROM cluster_alias a JOIN citations c ON c.cluster_id = a.cluster_id
                  GROUP BY a.decision_id) x
            WHERE d.decision_id = x.decision_id""")
