import re
import threading

from rewards_bot.search import catalog
from rewards_bot.search.bank import QueryBank
from rewards_bot.search.catalog import CATEGORIES, POPULAR_CATEGORY, all_queries, popular_queries


def test_catalog_has_no_duplicates():
    qs = [q.lower() for _, q in all_queries()]
    assert len(qs) == len(set(qs))
    assert len(CATEGORIES) >= 10


def test_catalog_queries_are_long_and_cover_games_and_it():
    qs = all_queries(popular=False)
    assert len(qs) >= 2000
    assert all(len(q.split()) >= 5 for _, q in qs)
    assert all("{" not in q for _, q in qs)
    text = " ".join(q.lower() for _, q in qs)
    for kw in ("roblox", "league of legends", "fortnite", "nginx", "load balancing", "mqtt", "kubernetes"):
        assert kw in text


def test_popular_queries_are_a_separate_clean_category():
    pop = popular_queries()
    assert len(pop) >= 9000
    assert len({q.lower() for q in pop}) == len(pop)
    assert all(3 <= len(q) <= 80 and q == q.strip() for q in pop)
    assert not [q for q in pop if re.search(r"\b(porn\w*|nude\w*|nsfw|hentai|xxx)\b", q, re.I)]
    cats = {c for c, _ in all_queries()}
    assert POPULAR_CATEGORY in cats and POPULAR_CATEGORY not in CATEGORIES
    assert all(c != POPULAR_CATEGORY for c, _ in all_queries(popular=False))


def test_missing_popular_file_falls_back_to_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "POPULAR_FILE", tmp_path / "none.json")
    catalog.popular_queries.cache_clear()
    try:
        assert catalog.popular_queries() == ()
        assert len(all_queries()) == len(all_queries(popular=False))
    finally:
        catalog.popular_queries.cache_clear()


def test_bank_mixes_popular_with_other_categories(tmp_path):
    rows = QueryBank(tmp_path / "h.json").generate(120)
    cats = [r["category"] for r in rows]
    assert POPULAR_CATEGORY in cats
    assert cats.count(POPULAR_CATEGORY) < len(cats) / 3


def test_table_unique_and_varied(tmp_path):
    rows = QueryBank(tmp_path / "h.json").generate(60)
    assert len({r["query"] for r in rows}) == 60
    assert all(a["category"] != b["category"] for a, b in zip(rows, rows[1:]))


def test_parallel_takes_never_repeat(tmp_path):
    bank = QueryBank(tmp_path / "h.json")
    bank.generate(10)
    got, lock = [], threading.Lock()

    def worker(name):
        for _ in range(50):
            q = bank.take(name)
            with lock:
                got.append(q)

    ts = [threading.Thread(target=worker, args=(n,)) for n in "ABC"]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(got) == 150 and len(set(got)) == 150


def test_used_queries_not_reused_after_restart(tmp_path):
    f = tmp_path / "h.json"
    used = {QueryBank(f).take("A") for _ in range(20)}
    fresh = {r["query"] for r in QueryBank(f).generate(300)}
    assert not used & fresh
