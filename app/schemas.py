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
    # how this result breaks the original request, e.g. "over budget by 4.50" - non-empty
    # only when the agent had to relax a constraint to find anything
    misses: list[str] = Field(default_factory=list)


class Step(BaseModel):
    iteration: int
    action: str
    detail: str
    kept: int


class Embedding(BaseModel):
    model: str
    dimensions: int
    text: list[float] | None = None
    image: list[float] | None = None
    # cosine similarity between the text and the image, when both were given
    similarity: float | None = None


class SearchResponse(BaseModel):
    # what the shopper asked for, and what the search ended up applying after repairs
    requested: Constraints = Field(default_factory=Constraints)
    constraints: Constraints
    results: list[Candidate]
    trace: list[Step] = Field(default_factory=list)
    # "rules" or "llm" read the request; "similarity" or "llm" ordered the results
    parser: str = "rules"
    ranker: str = "similarity"
    # a configured LLM failed, so this search fell back to rules / similarity
    degraded: bool = False
