"""Loading the filtered files (data/work) into PostgreSQL."""
import gzip
import json
import hashlib
from collections import defaultdict
from app import config, db
from app.chunking import pick_text, OPINION_TYPES


def opinion_label(op):
    label = OPINION_TYPES.get(op.get("type"), "Opinion")
    if op.get("per_curiam"):
        return f"{label} (per curiam)"
    author = (op.get("author_str") or "").strip()
    return f"{label} ({author})" if author else label


def load_corpus():
    """clusters.jsonl + opinions.jsonl -> decisions, cluster_alias, opinions (SR10, SR11)."""
    clusters = {c["cluster_id"]: c for c in map(json.loads, open(config.WORK / "clusters.jsonl"))}
    opinions_by_cluster = defaultdict(list)
    for op in map(json.loads, open(config.WORK / "opinions.jsonl")):
        opinions_by_cluster[op["cluster_id"]].append(op)

    # Merge duplicate clusters (same docket, same date) into one decision.
    groups = defaultdict(list)
    for c in clusters.values():
        groups[(c["docket_id"], c["date_filed"])].append(c)

    report = {"clusters": len(clusters), "decisions": 0, "duplicates_merged": 0,
              "decisions_without_text": 0, "opinions": 0, "opinions_without_text": 0,
              "rejected_without_licence": 0,
              "filters": {f.stem[7:]: json.load(open(f)) for f in sorted(config.WORK.glob("report_*.json"))}}
    with db.connect() as con:
        con.execute("TRUNCATE decisions, cluster_alias, opinions, chunks CASCADE")
        for group in groups.values():
            # keep the cluster whose opinions have the most text
            def text_size(c):
                return sum(len(pick_text(o)[0]) for o in opinions_by_cluster[c["cluster_id"]])
            group.sort(key=text_size, reverse=True)
            main = group[0]
            ops = [(o, *pick_text(o)) for o in opinions_by_cluster[main["cluster_id"]]]
            ops = [(o, text, field) for o, text, field in ops if text]
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
            report["opinions_without_text"] += len(opinions_by_cluster[main["cluster_id"]]) - len(ops)
    refresh_decision_citations()
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
    """Copy each decision's own citations (e.g. '603 U.S. 593') from the citations table."""
    with db.connect() as con:
        con.execute("""UPDATE decisions d SET citations = COALESCE((
            SELECT array_agg(DISTINCT c.volume || ' ' || c.reporter || ' ' || c.page)
            FROM citations c WHERE c.cluster_id = ANY(d.all_cluster_ids)), '{}')""")
