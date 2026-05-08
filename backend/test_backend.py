# =============================================================================
# test_backend.py - Manual backend verification script
# Run:
#     python test_backend.py
# =============================================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select


# =============================================================================
# PYTHON PATH SETUP
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))


# =============================================================================
# HEADER
# =============================================================================

print("=" * 60)
print("TESTING RESEARCH PAPER TOOL BACKEND")
print("=" * 60)


# =============================================================================
# LOAD ENVIRONMENT VARIABLES
# =============================================================================

load_dotenv()


# =============================================================================
# TEST 1: IMPORTS
# =============================================================================

print("\n[TEST 1] Importing modules...")

try:

    from app.database import (
        create_tables,
        LineMap,
        Paper,
        Result,
        SessionLocal,
    )

    print("  ✅ database.py imports OK")

except Exception as e:

    print(f"  ❌ database.py import FAILED: {e}")

    sys.exit(1)


try:

    from app.services.pdf_parser import (
        extract_text_with_lines,
        get_paper_stats,
    )

    print("  ✅ pdf_parser.py imports OK")

except Exception as e:

    print(f"  ❌ pdf_parser.py import FAILED: {e}")

    sys.exit(1)


try:

    from app.services.analyzer import (
        parse_claims_json,
        validate_claim,
    )

    print("  ✅ analyzer.py imports OK")

except Exception as e:

    print(f"  ❌ analyzer.py import FAILED: {e}")

    sys.exit(1)


# =============================================================================
# TEST 2: DATABASE TABLE CREATION
# =============================================================================

print("\n[TEST 2] Creating database tables...")

try:

    create_tables()

    print("  ✅ Tables created successfully")

except Exception as e:

    print(f"  ❌ Table creation FAILED: {e}")

    sys.exit(1)


# =============================================================================
# TEST 3: DATABASE READ / WRITE
# =============================================================================

print("\n[TEST 3] Testing database read/write...")

try:

    with SessionLocal() as db:

        # -------------------------------------------------------------
        # CREATE TEST PAPER
        # -------------------------------------------------------------

        test_paper = Paper(
            filename="test.pdf",
            status="completed",
        )

        db.add(test_paper)

        db.commit()

        # Refresh object from database
        db.refresh(test_paper)

        # -------------------------------------------------------------
        # READ IT BACK (SQLAlchemy 2.0 STYLE)
        # -------------------------------------------------------------

        found = db.scalar(
            select(Paper).where(
                Paper.filename == "test.pdf"
            )
        )

        assert found is not None, (
            "Paper not found after saving."
        )

        assert found.status == "completed", (
            "Paper status mismatch."
        )

        # -------------------------------------------------------------
        # CLEANUP
        # -------------------------------------------------------------

        db.delete(found)

        db.commit()

    print("  ✅ Database read/write works")

except Exception as e:

    print(f"  ❌ Database test FAILED: {e}")

    sys.exit(1)


# =============================================================================
# TEST 4: JSON CLAIM PARSING
# =============================================================================

print("\n[TEST 4] Testing JSON claim parsing...")

try:

    # -------------------------------------------------------------
    # PERFECT JSON
    # -------------------------------------------------------------

    perfect_json = """
    [
        {
            "claim_text": "94.2% accuracy",
            "claim_type": "performance",
            "section": "Results",
            "page_estimate": 5,
            "importance": "high"
        }
    ]
    """

    result = parse_claims_json(perfect_json)

    assert len(result) == 1

    assert (
        result[0]["claim_text"]
        == "94.2% accuracy"
    )

    print("  ✅ Perfect JSON parsing OK")

    # -------------------------------------------------------------
    # MARKDOWN-WRAPPED JSON
    # -------------------------------------------------------------

    markdown_json = """
    ```json
    [
        {
            "claim_text": "test claim",
            "claim_type": "performance",
            "section": "Results",
            "page_estimate": 1,
            "importance": "high"
        }
    ]
    ```
    """

    result = parse_claims_json(markdown_json)

    assert len(result) == 1

    print("  ✅ Markdown JSON parsing OK")

    # -------------------------------------------------------------
    # EMPTY RESPONSE
    # -------------------------------------------------------------

    result = parse_claims_json("")

    assert result == []

    print("  ✅ Empty response handling OK")

except Exception as e:

    print(f"  ❌ JSON parsing FAILED: {e}")

    sys.exit(1)


# =============================================================================
# TEST 5: CLAIM VALIDATION
# =============================================================================

print("\n[TEST 5] Testing claim validation...")

try:

    # -------------------------------------------------------------
    # VALID CLAIM
    # -------------------------------------------------------------

    valid = validate_claim(
        {
            "claim_text": (
                "Our method achieves 94.2% accuracy"
            ),
            "claim_type": "performance",
            "section": "Results",
            "page_estimate": 5,
            "importance": "high",
        }
    )

    assert valid is not None

    print("  ✅ Valid claim accepted")

    # -------------------------------------------------------------
    # INVALID CLAIM
    # -------------------------------------------------------------

    invalid = validate_claim(
        {
            "claim_type": "performance"
        }
    )

    assert invalid is None

    print("  ✅ Invalid claim rejected")

    # -------------------------------------------------------------
    # FIELD AUTO-CORRECTION
    # -------------------------------------------------------------

    renamed = validate_claim(
        {
            "text": "Some claim",
            "claim_type": "performance",
        }
    )

    assert renamed is not None

    assert (
        renamed["claim_text"]
        == "Some claim"
    )

    print("  ✅ Wrong field corrected")

except Exception as e:

    print(f"  ❌ Claim validation FAILED: {e}")

    sys.exit(1)


# =============================================================================
# TEST 6: ENVIRONMENT VARIABLES
# =============================================================================

print("\n[TEST 6] Checking environment variables...")

groq_key = os.getenv("GROQ_API_KEY")

if groq_key and groq_key != "your_groq_api_key_here":

    print("  ✅ GROQ_API_KEY is configured")

else:

    print(
        "  ⚠️ GROQ_API_KEY not configured "
        "(add it to your .env file)"
    )


# =============================================================================
# COMPLETE
# =============================================================================

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)

print("\nNext steps:")
print("1. Configure your .env file")
print("2. Start server:")
print("   uvicorn app.main:app --reload --port 8000")
print("3. Open:")
print("   http://localhost:8000/docs")
print("4. Verify health:")
print("   http://localhost:8000/health")