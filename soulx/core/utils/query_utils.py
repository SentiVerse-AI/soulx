import json
from typing import Dict, List, Any
import re 

def load_sse_jsons(raw_response: str) -> List[Dict[str, Any]]:

    chunks = []
    # Pattern to extract data after "data: " prefix
    pattern = r'data: (.*?)(?=\ndata:|$)'
    
    matches = re.findall(pattern, raw_response, re.DOTALL)
    
    for match in matches:
        data = match.strip()
        if data == "[DONE]":
            continue
            
        try:
            json_obj = json.loads(data)
            chunks.append(json_obj)
        except json.JSONDecodeError as e:
            print(f"Could not parse JSON: {e}")
            print(f"Raw data (first 100 chars): {data[:100]}...")
    
    return chunks