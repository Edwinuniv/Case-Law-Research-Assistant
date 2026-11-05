"""Step 1.8: one decision stored as several clusters (copies, or one cluster per opinion)."""
from app.ingest import group_opinions

MAJORITY = " ".join(f"The statute requires notice before removal in case number {i}." for i in range(60))
DISSENT = " ".join(f"I would grant the petition because the lower court erred on point {i}." for i in range(60))


def test_copies_of_one_opinion_are_kept_once():
    # the same opinion in two clusters, once as plain text and once as HTML with a header
    group = [{"cluster_id": 1}, {"cluster_id": 2}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": MAJORITY}],
           2: [{"opinion_id": 20, "cluster_id": 2, "html": f"<p>Syllabus</p><p>{MAJORITY}</p>"}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert len(kept) == 1 and copies == 1 and empty == 0


def test_separate_opinions_in_separate_clusters_are_all_kept():
    # e.g. Thompson v. McNeil (2009): a statement and a dissent stored as two clusters
    group = [{"cluster_id": 1}, {"cluster_id": 2}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": MAJORITY}],
           2: [{"opinion_id": 20, "cluster_id": 2, "plain_text": DISSENT}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert sorted(o["opinion_id"] for o, _, _ in kept) == [10, 20] and copies == 0


def test_main_cluster_is_the_one_with_most_text():
    group = [{"cluster_id": 1}, {"cluster_id": 2}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": DISSENT[:300]}],
           2: [{"opinion_id": 20, "cluster_id": 2, "plain_text": MAJORITY + DISSENT}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert main["cluster_id"] == 2


def test_opinion_without_text_is_counted():
    group = [{"cluster_id": 1}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": MAJORITY},
               {"opinion_id": 11, "cluster_id": 1}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert len(kept) == 1 and empty == 1


CONCURRENCE = " ".join(f"I write separately to stress the historical point number {i}." for i in range(60))


def test_combined_text_is_dropped_when_the_separate_opinions_cover_it():
    # e.g. Heller: one row with the whole decision, plus separate majority and dissent rows
    group = [{"cluster_id": 1}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": MAJORITY + " " + DISSENT},
               {"opinion_id": 11, "cluster_id": 1, "plain_text": MAJORITY},
               {"opinion_id": 12, "cluster_id": 1, "plain_text": DISSENT}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert sorted(o["opinion_id"] for o, _, _ in kept) == [11, 12] and copies == 1


def test_parts_are_dropped_when_the_combined_text_holds_more():
    # e.g. Citizens United: the combined text also holds a concurrence that has no separate row
    group = [{"cluster_id": 1}]
    ops = {1: [{"opinion_id": 10, "cluster_id": 1, "plain_text": MAJORITY + " " + DISSENT + " " + CONCURRENCE},
               {"opinion_id": 11, "cluster_id": 1, "plain_text": MAJORITY}]}
    main, kept, copies, empty = group_opinions(group, ops)
    assert [o["opinion_id"] for o, _, _ in kept] == [10] and copies == 1
