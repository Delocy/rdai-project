from pydantic import BaseModel, Field


class Constraints(BaseModel):
    intent: str = ""
    category: str | None = None
    colour: str | None = None
    price_max: float | None = None
    relative_cheaper: bool = False


class Candidate(BaseModel):
    id: str
    title: str
    price: float
    category: str | None = None
    colour: str | None = None
    image_url: str | None = None
    score: float
    rationale: str | None = None


class Step(BaseModel):
    iteration: int
    action: str
    detail: str
    kept: int


class SearchResponse(BaseModel):
    constraints: Constraints
    results: list[Candidate]
    trace: list[Step] = Field(default_factory=list)
    degraded: bool = False
