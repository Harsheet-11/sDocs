import os
import logging
from typing import List, Dict, Tuple

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError

logger = logging.getLogger(__name__)


def extract_text_with_lines(pdf_path: str) -> Tuple[List[Dict], str]:

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at path: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError(f"File does not have .pdf extension: {pdf_path}")

    all_lines: List[Dict] = []
    all_text_parts: List[str] = []

    global_line_number = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:

            total_pages = len(pdf.pages)
            logger.info(f"Processing PDF with {total_pages} pages: {pdf_path}")

            for page_index, page in enumerate(pdf.pages, start=1):

                page_text = page.extract_text()

                if not page_text or not page_text.strip():
                    logger.debug(f"Page {page_index}: no text found, skipping")
                    continue

                page_lines = page_text.split("\n")

                for raw_line in page_lines:

                    cleaned_line = raw_line.strip()

                    if not cleaned_line:
                        continue

                    # Skip page numbers like "1", "23", etc.
                    if cleaned_line.isdigit() and len(cleaned_line) <= 3:
                        continue

                    global_line_number += 1

                    line_dict = {
                        "page_number": page_index,
                        "line_number": global_line_number,
                        "text": cleaned_line,
                    }

                    all_lines.append(line_dict)
                    all_text_parts.append(cleaned_line)

    except PDFSyntaxError as e:
        raise ValueError(
            f"Cannot read PDF - file may be corrupted: {str(e)}"
        ) from e

    except Exception as e:
        raise RuntimeError(
            f"Error processing PDF {pdf_path}: {str(e)}"
        ) from e

    if not all_lines:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "The paper may be a scanned image. "
            "Only text-based PDFs are supported."
        )

    logger.info(f"Extracted {len(all_lines)} lines from {total_pages} pages")

    full_text = "\n".join(all_text_parts)

    return all_lines, full_text

def get_paper_stats(lines: List[Dict]) -> Dict:
    
    if not lines:
        return {"total_lines": 0, "total_pages": 0, "total_words": 0}
    
    total_lines = len(lines)
    
    total_pages = max(line["page_number"] for line in lines)
    
    total_words = sum(len(line["text"].split()) for line in lines)
    
    return {
        "total_lines": total_lines,
        "total_pages": total_pages,
        "total_words": total_words
    }