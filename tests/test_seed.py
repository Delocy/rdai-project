import numpy as np
import pytest

from app import seed

HEADER = "title,price,image,category,colour,image_url\n"
FIVE = [f"Item {i},{10 + i},{i}.jpg,Shirts,Blue," for i in range(5)]


def catalogue(tmp_path, rows: list[str], images: list[str]):
    csv = tmp_path / "catalogue.csv"
    csv.write_text(HEADER + "".join(row + "\n" for row in rows), encoding="utf-8")
    folder = tmp_path / "images"
    folder.mkdir()
    for name in images:
        (folder / name).write_bytes(b"jpg")
    return csv, folder


def quiet(message: str) -> None:
    pass


@pytest.fixture
def index(monkeypatch):
    """Records what gets embedded and stored instead of running models or Qdrant."""
    state = {"batches": [], "points": {}, "existing": set(), "count": 0}

    def embed(paths):
        state["batches"].append(len(paths))
        return [np.ones(512, dtype=np.float32) for _ in paths]

    monkeypatch.setattr(seed, "embed_image_paths", embed)
    monkeypatch.setattr(seed.store, "upsert", lambda points: state["points"].update({p.id: p for p in points}))
    monkeypatch.setattr(seed.store, "existing_ids", lambda ids: {i for i in ids if i in state["existing"]})
    monkeypatch.setattr(seed.store, "count", lambda: state["count"])
    return state


def test_ids_are_stable_per_image_file():
    assert seed.point_id({"image": "15970.jpg"}) == seed.point_id({"image": "15970.jpg"})
    assert seed.point_id({"image": "15970.jpg"}) != seed.point_id({"image": "39386.jpg"})


def test_images_are_embedded_in_batches(tmp_path, index):
    csv, images = catalogue(tmp_path, FIVE, [f"{i}.jpg" for i in range(5)])
    assert seed.seed_from_csv(csv, images, batch_size=2, log=quiet) == 5
    assert index["batches"] == [2, 2, 1]
    assert len(index["points"]) == 5


def test_reindex_overwrites(tmp_path, index):
    csv, images = catalogue(tmp_path, FIVE, [f"{i}.jpg" for i in range(5)])
    seed.seed_from_csv(csv, images, log=quiet)
    seed.seed_from_csv(csv, images, log=quiet)
    assert len(index["points"]) == 5


def test_skips_incomplete_rows(tmp_path, index):
    rows = [
        "Item 0,10,0.jpg,Shirts,Blue,",
        ",11,1.jpg,Shirts,Blue,",
        "Item 2,,2.jpg,Shirts,Blue,",
        "Item 3,13,missing.jpg,Shirts,Blue,",
    ]
    csv, images = catalogue(tmp_path, rows, ["0.jpg", "1.jpg", "2.jpg"])
    assert seed.seed_from_csv(csv, images, log=quiet) == 1


def test_seed_missing_resumes(tmp_path, index):
    csv, images = catalogue(tmp_path, FIVE, [f"{i}.jpg" for i in range(5)])
    index["existing"] = {seed.point_id(row) for row in list(seed.rows(csv))[:3]}
    index["count"] = 3
    assert seed.seed_missing(csv, images, log=quiet) == 2
    assert index["batches"] == [2]


def test_seed_missing_when_done(tmp_path, index):
    csv, images = catalogue(tmp_path, FIVE, [f"{i}.jpg" for i in range(5)])
    index["existing"] = {seed.point_id(row) for row in seed.rows(csv)}
    index["count"] = 5
    assert seed.seed_missing(csv, images, log=quiet) == 0
    assert index["batches"] == []


def test_seed_missing_skips_foreign_collection(tmp_path, index):
    csv, images = catalogue(tmp_path, FIVE, [f"{i}.jpg" for i in range(5)])
    index["count"] = 40  # holds data, but none of these rows' ids
    assert seed.seed_missing(csv, images, log=quiet) == 0
    assert index["points"] == {}
