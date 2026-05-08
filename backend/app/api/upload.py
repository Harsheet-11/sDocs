#   User Uploads PDF
#           ↓
#   Check file name, type, size 
#           ↓
#   Save PDF temporarily
#           ↓
#   Verify it's a real PDF
#           ↓
#   Create database record
#           ↓
#   Extract text from PDF
#           ↓
#   Save extracted lines
#           ↓
#   Run AI analysis
#           ↓
#   Mark paper as completed
#           ↓
#   Send response back

from __future__ import annotations

import io
import logging
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db, Paper, LineMap
from app.services.pdf_parser import (
    extract_text_with_lines,
    get_paper_stats,
)
from app.services.analyzer import analyze_paper

# ENV + LOGGING

load_dotenv()

logger = logging.getLogger(__name__)


# ROUTER SETUP

router = APIRouter(tags=["Upload"])


UPLOAD_DIR = Path("./temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


# RESPONSE MODELS (Pydantic v2)

class UploadResponse(BaseModel):
    
    model_config = ConfigDict(from_attributes=True)

    paper_id: int
    message: str
    status: str
    filename: str
    stats: dict


class ErrorResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    error: str
    detail: str


# HELPERS

def is_valid_pdf(file_path: Path) -> bool:

    try:
        with file_path.open("rb") as f:
            header = f.read(4)

        return header == b"%PDF"

    except Exception:
        return False


def save_upload_to_disk(upload_file: UploadFile) -> Path:

    unique_prefix = uuid.uuid4().hex[:8]

    safe_filename = Path(upload_file.filename or "uploaded.pdf").name

    unique_filename = f"{unique_prefix}-{safe_filename}"

    file_path = UPLOAD_DIR / unique_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    logger.info("Saved upload to %s", file_path)

    return file_path


def save_lines_to_db(
    *,
    lines: list[dict],
    paper_id: int,
    db: Session,
) -> None:

    line_records = [
        {
            "paper_id": paper_id,
            "page_number": line["page_number"],
            "line_number": line["line_number"],
            "text": line["text"],
        }
        for line in lines
    ]

    db.bulk_insert_mappings(LineMap.__mapper__, line_records)

    logger.info(
        "Saved %s lines for paper_id=%s",
        len(line_records),
        paper_id,
    )


# UPLOAD ENDPOINT

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_paper(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """
    Upload and analyze a PDF paper.
    """

    temp_file_path: Path | None = None

    try:

        # VALIDATE FILENAME

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided.",
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are accepted.",
            )

        # READ FILE CONTENT

        file_content = await file.read()

        file_size = len(file_content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File too large "
                    f"({file_size / 1024 / 1024:.1f}MB). "
                    f"Maximum size is 20MB."
                ),
            )

        # Reset file pointer
        
        file.file = io.BytesIO(file_content)

        # SAVE TO DISK

        temp_file_path = save_upload_to_disk(file)

        # VALIDATE PDF MAGIC BYTES

        if not is_valid_pdf(temp_file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file.",
            )

        # CREATE PAPER RECORD

        original_filename = Path(file.filename).name

        new_paper = Paper(
            filename=original_filename,
            status="processing",
        )

        db.add(new_paper)
        db.flush()

        paper_id = new_paper.id

        logger.info("Created paper record id=%s", paper_id)

        # EXTRACT TEXT

        try:
            lines, full_text = extract_text_with_lines(
                str(temp_file_path)
            )

        except ValueError as e:

            new_paper.status = "failed"
            new_paper.error_message = str(e)

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        stats = get_paper_stats(lines)

        logger.info("Paper stats: %s", stats)

        # SAVE LINE MAPS

        save_lines_to_db(
            lines=lines,
            paper_id=paper_id,
            db=db,
        )

        # RUN ANALYSIS

        try:
            claims = analyze_paper(
                paper_text=full_text,
                paper_id=paper_id,
                db=db,
            )

        except Exception as e:

            new_paper.status = "failed"
            new_paper.error_message = str(e)

            db.commit()

            logger.exception("AI analysis failed")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI analysis failed: {str(e)}",
            )

        # COMPLETE PAPER

        new_paper.status = "completed"

        db.commit()

        logger.info(
            "Completed paper_id=%s with %s claims",
            paper_id,
            len(claims),
        )

        return UploadResponse(
            paper_id=paper_id,
            message=f"Analysis complete. Found {len(claims)} claims.",
            status="completed",
            filename=original_filename,
            stats=stats,
        )

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        logger.exception("Unexpected upload error")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )

    finally:

        if temp_file_path and temp_file_path.exists():

            temp_file_path.unlink(missing_ok=True)

            logger.info(
                "Deleted temp file %s",
                temp_file_path,
            )