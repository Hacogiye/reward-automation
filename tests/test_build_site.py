"""The public site (packaging/build_site.py) stays consistent: same version everywhere, sitemap follows noindex,
JSON-LD has no empty fields and only states what the page shows."""

import html
import importlib.util
import json
import re
from pathlib import Path

import rewards_bot

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_site", ROOT / "packaging" / "build_site.py")
build_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_site)


def _jsonld(text: str, kind: str = "SoftwareApplication") -> dict:
    blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', text, re.S)]
    found = [b for b in blocks if b["@type"] == kind]
    assert len(found) == 1
    return found[0]


def test_site_builds_with_one_source_of_truth(tmp_path):
    out = build_site.build(tmp_path / "site")
    for page in build_site.PAGES:
        text = (out / page["path"] / "index.html").read_text(encoding="utf-8")
        data = _jsonld(text)
        assert data["softwareVersion"] == rewards_bot.__version__
        assert rewards_bot.__version__ in text  # the version is also shown as text
        assert data["description"] in text  # JSON-LD description is visible on the page
        assert "aggregateRating" not in data and "review" not in data
        build_site.check_no_empty(data)
        assert f'lang="{page["lang"]}"' in text
        assert ('name="robots" content="noindex"' in text) == page["noindex"]
        faq = _jsonld(text, "FAQPage")
        assert len(faq["mainEntity"]) == len(page["faq"])
        for item in faq["mainEntity"]:  # every FAQ answer in JSON-LD is shown on the page
            assert html.escape(item["name"]) in text
            assert html.escape(item["acceptedAnswer"]["text"]) in text

    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    for page in build_site.PAGES:
        assert (build_site.page_url(page) + "<") in sitemap or page["noindex"]
        assert (build_site.page_url(page) + "<" not in sitemap) or not page["noindex"]

    robots = (out / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: OAI-SearchBot\nAllow: /" in robots
    assert "Disallow" not in robots
    assert f"Sitemap: {build_site.SITE_URL}sitemap.xml" in robots

    assert rewards_bot.__version__ in (out / "llms.txt").read_text(encoding="utf-8")
    for name in build_site.IMAGES.values():
        assert (out / "images" / name).is_file()

    payload = build_site.indexnow_payload()
    key = build_site.SITE["indexnow_key"]
    assert (out / f"{key}.txt").read_text(encoding="utf-8") == key
    assert payload["keyLocation"] == f"{build_site.SITE_URL}{key}.txt"
    assert all(u.startswith(build_site.SITE_URL) for u in payload["urlList"])


def test_empty_jsonld_value_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        build_site.check_no_empty({"a": {"b": ""}})
