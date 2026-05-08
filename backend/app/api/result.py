# result.py - Return analysis results for a specific paper

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import (
    get_db,
    LineMap,
    Paper,
    Result,
)

logger = logging.getLogger(__name__)


# ROUTER

router = APIRouter(tags=["Results"])


# RESPONSE MODELS (Pydantic v2)

class LineData(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    line_number: int
    page_number: int
    text: str


class ClaimData(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    claim_text: str
    claim_type: str
    section: str
    page_estimate: int
    importance: str


class PaperResultResponse(BaseModel):


    model_config = ConfigDict(from_attributes=True)

    paper_id: int
    filename: str
    status: str

    error_message: Optional[str] = None

    claims: list[ClaimData] = []
    lines: list[LineData] = []

    total_lines: int = 0
    total_claims: int = 0


class PaperListItem(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    created_at: Optional[str] = None


class PaperListResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    papers: list[PaperListItem]
    total: int


# GET PAPER RESULT

@router.get(
    "/result/{paper_id}",
    response_model=PaperResultResponse,
)
def get_paper_result(
    paper_id: int,
    db: Session = Depends(get_db),
) -> PaperResultResponse:

    # FETCH PAPER

    paper = db.scalar(
        select(Paper).where(Paper.id == paper_id)
    )

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with id {paper_id} not found.",
        )

    # STILL PROCESSING

    if paper.status == "processing":

        return PaperResultResponse(
            paper_id=paper.id,
            filename=paper.filename,
            status="processing",
        )

    # FAILED

    if paper.status == "failed":

        return PaperResultResponse(
            paper_id=paper.id,
            filename=paper.filename,
            status="failed",
            error_message=paper.error_message,
        )

    # FETCH LINES

    line_records = db.scalars(
        select(LineMap)
        .where(LineMap.paper_id == paper_id)
        .order_by(LineMap.line_number)
    ).all()

    lines = [
        LineData.model_validate(line)
        for line in line_records
    ]

    # FETCH CLAIMS

    result_record = db.scalar(
        select(Result).where(Result.paper_id == paper_id)
    )

    claims: list[ClaimData] = []

    if result_record and result_record.claims_json:

        try:
            raw_claims = json.loads(result_record.claims_json)

            for raw_claim in raw_claims:

                try:

                    claim = ClaimData(
                        claim_text=raw_claim.get(
                            "claim_text",
                            "",
                        ),
                        claim_type=raw_claim.get(
                            "claim_type",
                            "methodology",
                        ),
                        section=raw_claim.get(
                            "section",
                            "Unknown",
                        ),
                        page_estimate=raw_claim.get(
                            "page_estimate",
                            1,
                        ),
                        importance=raw_claim.get(
                            "importance",
                            "medium",
                        ),
                    )

                    claims.append(claim)

                except Exception as e:

                    logger.warning(
                        "Skipping malformed claim: %s",
                        e,
                    )

        except json.JSONDecodeError as e:

            logger.error(
                "Invalid claims JSON for paper_id=%s: %s",
                paper_id,
                e,
            )

    # RETURN COMPLETE RESPONSE

    return PaperResultResponse(
        paper_id=paper.id,
        filename=paper.filename,
        status=paper.status,
        claims=claims,
        lines=lines,
        total_lines=len(lines),
        total_claims=len(claims),
    )


# LIST PAPERS

@router.get(
    "/papers",
    response_model=PaperListResponse,
)
def list_papers(
    db: Session = Depends(get_db),
) -> PaperListResponse:
    """
    Return all uploaded papers.
    """

    papers = db.scalars(
        select(Paper)
        .order_by(Paper.created_at.desc())
    ).all()

    response_items = [
        PaperListItem(
            id=paper.id,
            filename=paper.filename,
            status=paper.status,
            created_at=(
                paper.created_at.isoformat()
                if paper.created_at
                else None
            ),
        )
        for paper in papers
    ]

    return PaperListResponse(
        papers=response_items,
        total=len(response_items),
    )