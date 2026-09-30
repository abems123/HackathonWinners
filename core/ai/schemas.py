from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(StrictSchema):
    quote: str = Field(min_length=1, max_length=50000)
    subject: str = Field(max_length=200)
    value: str = Field(max_length=300)


class Claims(StrictSchema):
    claims: list[Claim] = Field(max_length=30)


class Comparison(StrictSchema):
    relation: Literal["SUPPORTS", "CONTRADICTS", "UNRELATED", "UNKNOWN"]
    quote_a: str = Field(max_length=50000)
    quote_b: str = Field(max_length=50000)


class Triage(StrictSchema):
    label: Literal["VALUE_CHANGED", "SCOPE_CHANGED", "WORDING_CHANGED", "UNKNOWN"]
