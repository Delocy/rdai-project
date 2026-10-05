import base64
import io
import json

from PIL import Image

import app.agent.justify as ranking
from app.schemas import Candidate


def candidate(id: str, image_url: str | None) -> Candidate:
    return Candidate(id=id, title=f"item {id}", price=10.0, score=0.5, image_url=image_url)


def photo(folder, name: str, colour: str = "red") -> None:
    Image.new("RGB", (60, 80), colour).save(folder / name, format="JPEG")


def model_ranks(monkeypatch, entries: list | None = None) -> list:
    """Make the vision model answer with `entries`; returns the list each request's messages land in."""
    sent = []

    def fake_complete(messages, kind, json_mode=False):
        sent.append(messages)
        return json.dumps({"ranking": entries or []})

    monkeypatch.setattr(ranking, "complete", fake_complete)
    return sent


def images_with_labels(sent: list) -> list[tuple[str, Image.Image]]:
    """(label text just before it, decoded image) for every image in the one request."""
    content = sent[0][1]["content"]
    return [
        (content[i - 1]["text"], Image.open(io.BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1]))))
        for i, part in enumerate(content)
        if part["type"] == "image_url"
    ]


def test_the_shortlist_photos_go_in_as_one_numbered_sheet(monkeypatch, tmp_path):
    # one image however long the shortlist - five separate photos overflow the 4096-token
    # context small local vision models get by default
    photo(tmp_path, "a.jpg")
    photo(tmp_path, "b.jpg", "blue")
    monkeypatch.setattr(ranking, "IMAGES", tmp_path)
    sent = model_ranks(monkeypatch)

    ranking.justify(
        "blue shirt",
        [
            candidate("item-a", "https://raw.githubusercontent.com/x/y/main/data/images/a.jpg"),
            candidate("item-b", "/images/b.jpg"),
        ],
    )

    [(label, sheet)] = images_with_labels(sent)
    assert "1 = item-a" in label
    assert "2 = item-b" in label
    assert sheet.width == 2 * ranking.TILE[0]


def test_candidates_without_a_local_photo_are_left_off_the_sheet_but_still_ranked(monkeypatch, tmp_path):
    photo(tmp_path, "a.jpg")
    monkeypatch.setattr(ranking, "IMAGES", tmp_path)
    sent = model_ranks(monkeypatch, [{"id": "a", "rationale": "fits", "relevant": True}])

    result = ranking.justify("watch", [candidate("a", "/images/a.jpg"), candidate("b", "/images/missing.jpg")])

    [(label, sheet)] = images_with_labels(sent)
    assert "1 = a" in label
    assert "b" not in label.split("(", 1)[1]
    assert sheet.width == ranking.TILE[0]
    assert [c.id for c in result] == ["a", "b"]


def test_no_photos_means_no_image_at_all(monkeypatch, tmp_path):
    monkeypatch.setattr(ranking, "IMAGES", tmp_path)
    sent = model_ranks(monkeypatch)
    ranking.justify("watch", [candidate("x", None)])
    assert images_with_labels(sent) == []


def test_the_shoppers_reference_photo_is_sent_separately_and_labelled(monkeypatch, tmp_path):
    monkeypatch.setattr(ranking, "IMAGES", tmp_path)
    sent = model_ranks(monkeypatch)

    ranking.justify("like this", [candidate("x", None)], query_image=b"reference")

    _, label, image = sent[0][1]["content"]
    assert "reference" in label["text"].lower()
    assert image["image_url"]["url"].endswith(base64.b64encode(b"reference").decode())


def test_items_the_model_marks_irrelevant_are_dropped(monkeypatch, tmp_path):
    monkeypatch.setattr(ranking, "IMAGES", tmp_path)
    model_ranks(
        monkeypatch,
        [
            {"id": "y", "rationale": "best fit", "relevant": True},
            {"id": "x", "rationale": "wrong item", "relevant": False},
        ],
    )

    result = ranking.justify("watch", [candidate("x", None), candidate("y", None)])

    assert [(c.id, c.rationale) for c in result] == [("y", "best fit")]
