from pydantic import BaseModel
from typing import List


class ResearchReport(BaseModel):
    topic: str
    answer: str
    sources: List[str]
