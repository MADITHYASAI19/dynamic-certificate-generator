from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar("T")

class PaginationResponse(BaseModel, Generic[T]):
    page: int
    page_size: int
    total: int
    items: List[T]
