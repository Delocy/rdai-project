import json
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..llm import VISION, complete, image_part
from ..paths import IMAGES
from ..schemas import Candidate

SYSTEM = (
    "You rank shopping search results. Given the request, the candidate items, one image with "
    "a numbered photo of each candidate, and sometimes the shopper's own reference photo, reply "
    'with JSON {"ranking": [{"id": str, "rationale": str, "relevant": bool}]}, one entry per '
    "candidate, ordered best first. Judge what each photo actually shows, not just its title. "
    "relevant is true only when the item genuinely matches the request - these are nearest "
    "neighbours from a vector search, and some can be unrelated. Don't stretch a rationale to "
    "justify a bad match; mark it false instead. Each rationale is one short sentence."
)

TILE = (160, 200)  # one candidate photo on the contact sheet
HEADER = 34  # strip above the photos for their numbers


def _photo_path(candidate: Candidate) -> Path | None:
    """The candidate's catalogue photo on local disk. image_url may be a remote copy
    (e.g. raw.githubusercontent.com), so match on the file name."""
    if not candidate.image_url:
        return None
    name = PurePosixPath(urlparse(candidate.image_url).path).name
    path = IMAGES / name
    return path if name and path.is_file() else None


def _contact_sheet(paths: list[Path]) -> bytes:
    """The photos side by side under their numbers, as one JPEG. Five separate images
    overflow Ollama's default 4096-token context; one sheet doesn't."""
    sheet = Image.new("RGB", (TILE[0] * len(paths), TILE[1] + HEADER), "white")
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=26)
    for i, path in enumerate(paths):
        with Image.open(path) as photo:
            tile = ImageOps.contain(photo.convert("RGB"), TILE)  # scales small photos up too
        sheet.paste(tile, (i * TILE[0] + (TILE[0] - tile.width) // 2, HEADER + (TILE[1] - tile.height) // 2))
        draw.text((i * TILE[0] + TILE[0] // 2, 3), str(i + 1), fill="black", font=font, anchor="mt")
    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def justify(
    request: str, candidates: list[Candidate], query_image: bytes | None = None
) -> list[Candidate]:
    if not candidates:
        return []

    listing = [
        {
            "id": candidate.id,
            "title": candidate.title,
            "price": candidate.price,
            "colour": candidate.colour,
            "category": candidate.category,
        }
        for candidate in candidates
    ]
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"Request: {request or 'find similar items'}\nCandidates: {json.dumps(listing)}"}
    ]
    if query_image:
        content += [{"type": "text", "text": "Reference photo from the shopper:"}, image_part(query_image)]
    pictured = [(candidate, path) for candidate in candidates if (path := _photo_path(candidate))]
    if pictured:
        numbering = ", ".join(f"{n} = {candidate.id}" for n, (candidate, _) in enumerate(pictured, 1))
        content += [
            {"type": "text", "text": f"Photos of the candidates, numbered left to right ({numbering}):"},
            image_part(_contact_sheet([path for _, path in pictured])),
        ]

    raw = complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        VISION,
        json_mode=True,
    )
    try:
        ranking = json.loads(raw).get("ranking", [])
    except (json.JSONDecodeError, AttributeError):
        return candidates

    by_id = {candidate.id: candidate for candidate in candidates}
    ordered: list[Candidate] = []
    for entry in ranking:
        candidate = by_id.pop(str(entry.get("id")), None)
        if not candidate or entry.get("relevant", True) is False:
            continue
        candidate.rationale = entry.get("rationale")
        ordered.append(candidate)
    # anything left in by_id is a candidate the model never mentioned (e.g. a
    # truncated response) rather than one it actively rejected - keep those
    # rather than silently dropping results because the model half-answered
    return ordered + list(by_id.values())
