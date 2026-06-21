from __future__ import annotations
from pathlib import Path
import pytest
from usecase.builtin_components import _xql_enrichment as xe

DATA = Path(xe.__file__).resolve().parent / "xql_data"


def test_extract_stage_names():
    q = "dataset = xdr_data\n| filter a = 1\n| alter b = 2\n| comp count() by b"
    assert xe.extract_stage_names(q) == {"filter", "alter", "comp"}


def test_extract_dataset():
    assert xe.extract_dataset("dataset = panw_ngfw_traffic_raw\n| filter x") == "panw_ngfw_traffic_raw"
    assert xe.extract_dataset("| filter x") is None


def test_collect_stage_docs_returns_snippets_for_known_stages():
    out = xe.collect_stage_docs(DATA, ["filter"])
    assert isinstance(out, list)
    assert any(d["stage"] == "filter" and d["snippet"] for d in out)


def test_collect_dataset_fields_shape():
    out = xe.collect_dataset_fields(DATA, ["nonexistent_dataset_xyz"])
    assert out == []  # unknown dataset -> empty, never error
