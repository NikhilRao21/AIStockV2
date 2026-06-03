import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def parse_recommendation(raw_json: str) -> Optional[dict]:
    try:
        # Strip potential markdown fences
        clean_json = raw_json.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        
        data = json.loads(clean_json.strip())
        
        required_keys = ["ticker", "action", "confidence", "bull_case", "bear_case", 
                         "supporting_evidence", "key_risks", "catalysts", 
                         "position_size_pct", "expected_holding_days", "reasoning_summary"]
                         
        for key in required_keys:
            if key not in data:
                logger.error(f"Missing required key in recommendation: {key}")
                return None
                
        if data["action"] not in ["BUY", "SELL", "HOLD", "NO_ACTION"]:
            logger.error(f"Invalid action in recommendation: {data['action']}")
            return None
            
        conf = data.get("confidence", 0)
        if not (0.0 <= conf <= 1.0):
            logger.error(f"Confidence out of range: {conf}")
            return None
            
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recommendation JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing recommendation: {e}")
        return None
