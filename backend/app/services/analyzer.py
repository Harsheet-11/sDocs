#   get_groq_client()               -> Connect to Groq AI
#   build_claim_extraction_prompt() -> Tell AI exactly what to extract
#   call_groq()                     -> Send paper to AI
#   parse_claims_json()             -> Converts AI text response into Python objects safely.
#   validate_claim()                -> Ensure claims are valid
#   analyze_paper()                 -> Run the entire pipeline end-to-end



import os
import json
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pydantic import SecretStr
from sqlalchemy.orm import Session
from app.database import Result, Paper

from langchain_groq import ChatGroq

from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

logger = logging.getLogger(__name__)

def get_groq_client() -> ChatGroq:
    
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found in environment. "
            "Please add it to your .env file. "
            "Get a free key at https://console.groq.com"
        )
        
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        
    return ChatGroq(
        api_key=SecretStr(api_key),
        model=model_name,
        temperature=0,
        max_tokens=2048
    )
    
def build_claim_extraction_prompt(paper_text: str) -> str:
    
    max_chars = 12000
    
    if len(paper_text) > max_chars:
        truncated_text = paper_text[:max_chars]
        
        logger.warning(f"Paper text truncated from {len(paper_text)} to {max_chars} chars")
        
    else:
        truncated_text = paper_text
        
    prompt = f"""You are a research paper analysis expert. Your job is to extract key claims from academic papers.

A CLAIM is a specific, verifiable assertion made by the authors. Examples:
- Performance claims: "Our method achieves 94.2% accuracy on MemBench"
- Comparison claims: "Our approach is 3x faster than the baseline"
- Novelty claims: "We are the first to apply X to Y"
- Limitation claims: "Our method fails when the input exceeds 512 tokens"

NOT a claim:
- General statements: "Deep learning is popular"
- Background information: "Transformers were introduced in 2017"
- Vague statements: "Our method works well"

INSTRUCTIONS:
1. Read the paper text below
2. Extract ALL specific, verifiable claims
3. For each claim, note which section it appears in (Abstract, Introduction, Methods, Results, Conclusion, Limitations)
4. Estimate the page number based on the content flow (start at 1)
5. Assign a type: "performance", "comparison", "novelty", "limitation", or "methodology"
6. Return ONLY a valid JSON array. No explanation. No markdown. No ```json``` blocks. Just the raw JSON array.

OUTPUT FORMAT (return exactly this structure):
[
  {{
    "claim_text": "exact quote or close paraphrase of the claim",
    "claim_type": "performance",
    "section": "Results",
    "page_estimate": 5,
    "importance": "high"
  }}
]

importance values: "high" (key contribution), "medium" (supporting evidence), "low" (minor detail)

PAPER TEXT:
{truncated_text}

Remember: Return ONLY the JSON array. Start your response with [ and end with ]"""
    
    return prompt

def call_groq(prompt: str) -> str:

    llm = get_groq_client()

    messages = [
        SystemMessage(content=(
            "You are a research paper analysis expert. "
            "You extract structured information from academic papers. "
            "You always return valid JSON when asked. "
            "You never add explanations outside the JSON structure."
        )),
        HumanMessage(content=prompt)
    ]

    logger.info("Sending request to Groq AI...")

    response = llm.invoke(messages)

    content = response.content

    if isinstance(content, str):
        response_text = content
    else:
        response_text = json.dumps(content)

    logger.info(f"Received response from Groq ({len(response_text)} chars)")

    return response_text

#   The AI MIGHT return:
#    1. Perfect JSON: [{"claim_text": "..."}]

#    2. JSON with markdown: ```json\n[{"claim_text": #"..."}]\n```

#    3. JSON with extra text: "Here are the claims:\n[...]"

#    4. Invalid JSON: [{"claim_text": "unclosed}]

#    5. Empty response: ""

def parse_claims_json(response_text: str) -> List[Dict]:
    if not response_text or not response_text.strip():
        logger.warning("Empty response from Groq")
        return []

    cleaned = response_text.strip()

    # ---------------------------------------------------
    # Attempt 1: Direct JSON parsing
    # ---------------------------------------------------
    try:
        result = json.loads(cleaned)

        if isinstance(result, list):
            return result

        elif isinstance(result, dict) and "claims" in result:
            return result["claims"]

        else:
            logger.warning(f"Unexpected JSON structure: {type(result)}")
            return []

    except json.JSONDecodeError:
        pass

    # ---------------------------------------------------
    # Attempt 2: Extract JSON from markdown code blocks
    # ---------------------------------------------------
    if "```" in cleaned:

        lines = cleaned.split("\n")
        json_lines = []

        inside_code_block = False

        for line in lines:

            if line.strip().startswith("```"):
                inside_code_block = not inside_code_block
                continue

            if inside_code_block:
                json_lines.append(line)

        if json_lines:
            try:
                result = json.loads("\n".join(json_lines))

                if isinstance(result, list):
                    logger.info("Successfully parsed JSON from code block")
                    return result

            except json.JSONDecodeError:
                pass

    # ---------------------------------------------------
    # Attempt 3: Extract substring between [ ... ]
    # ---------------------------------------------------
    start_bracket = cleaned.find('[')
    end_bracket = cleaned.rfind(']')

    if (
        start_bracket != -1
        and end_bracket != -1
        and start_bracket < end_bracket
    ):

        json_substring = cleaned[start_bracket:end_bracket + 1]

        try:
            result = json.loads(json_substring)

            if isinstance(result, list):
                logger.info("Successfully extracted JSON from response")
                return result

        except json.JSONDecodeError:
            pass

    logger.error(
        f"Could not parse Groq response as JSON.\n"
        f"Response preview:\n{response_text[:500]}"
    )

    return []

def validate_claim(claim: Dict) -> Optional[Dict]:

    if "text" in claim and "claim_text" not in claim:
        claim["claim_text"] = claim.pop("text")
    
    if "claim" in claim and "claim_text" not in claim:
        claim["claim_text"] = claim.pop("claim")
    
    
    claim_text = claim.get("claim_text", "").strip()
    if not claim_text:
        return None  
    
    valid_types = {"performance", 
                   "comparison",
                   "novelty", 
                   "limitation", 
                   "methodology"}
    
    claim_type = claim.get("claim_type", "").lower()
    
    if claim_type not in valid_types:
        claim_type = "methodology"  
    
    valid_sections = {"Abstract", 
                      "Introduction", 
                      "Methods", 
                      "Results", 
                      "Conclusion", 
                      "Limitations", 
                      "Discussion"}
    
    section = claim.get("section", "Unknown")
    
    if section not in valid_sections:
        section = "Unknown"
    
    page_estimate = claim.get("page_estimate", 1)
    
    try:
        page_estimate = max(1, int(page_estimate))  
    except (ValueError, TypeError):
        page_estimate = 1
    
    valid_importance = {"high", "medium", "low"}
    
    importance = claim.get("importance", "medium").lower()
    
    if importance not in valid_importance:
        importance = "medium"
    
    return {
        "claim_text": claim_text,
        "claim_type": claim_type,
        "section": section,
        "page_estimate": page_estimate,
        "importance": importance
    }

def analyze_paper(paper_text: str, paper_id: int, db: Session) -> List[Dict]:
    
    logger.info(f"Starting analysis for paper_id: {paper_id}")
    
    try:
        #   1. Build the prompt
        prompt = build_claim_extraction_prompt(paper_text)
        logger.info(f"Built prompt ({len(prompt)} chars)")
        
        #   2. Call Groq
        raw_response = call_groq(prompt)
        
        #   3. Parse JSON
        raw_claims = parse_claims_json(raw_response)
        logger.info(f"Parsed {len(raw_claims)} raw claims from response")
        
        #   4. Validate each claim
        validated_claims = []
        for raw_claim in raw_claims:
            validated = validate_claim(raw_claim)
            if validated is not None:
                validated_claims.append(validated)
        logger.info(f"After validation: {len(validated_claims)} valid claims")
        
        #   5. Save to database
        existing_result = db.query(Result).filter(
            Result.paper_id == paper_id
        ).first()
        
        claims_json_string = json.dumps(validated_claims)
        
        if existing_result:
            # Update existing result
            existing_result.claims_json = claims_json_string
            logger.info("Updated existing result record")
        else:
            # Create new result record
            new_result = Result(
                paper_id=paper_id,
                claims_json=claims_json_string
            )
            db.add(new_result)
            logger.info("Created new result record")
            
        db.commit()
        logger.info(f"Analysis complete. Found {len(validated_claims)} claims.")
        return validated_claims
        
    except Exception as e:
        db.rollback()
        logger.error(f"Analysis failed for paper_id {paper_id}: {str(e)}")
        
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            paper.status = "failed"
            paper.error_message = str(e)
            db.commit()
            
        raise