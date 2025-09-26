# scripts/smoke_ai_writer.py
import json
from services.ai_writer import generate_draft

worker = {
    "name": "יוסי כהן",
    "field": "חשמלאי מוסמך",
    "experience": 7,
    "area": "פתח תקווה",
    "base_city": "פתח תקווה",
    "company_name": ""
}

draft = generate_draft(worker, lang="he")
print(json.dumps(draft, ensure_ascii=False, indent=2))
