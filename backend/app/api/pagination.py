"""FastAPI adapter for the shared page-number contract."""

from typing import Annotated

from fastapi import Depends, Query

from app.schemas.pagination import PageParams


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PaginationParams = Annotated[PageParams, Depends(get_page_params)]
