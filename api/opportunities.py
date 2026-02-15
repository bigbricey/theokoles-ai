"""
Vercel serverless function: SAM.gov opportunity search.

POST /api/opportunities
Body: {keyword, opp_type, active_only, naics, page}
"""

from http.server import BaseHTTPRequestHandler
import json
import re
import urllib.request
import urllib.parse


def strip_html(text):
    """Remove HTML tags from a string."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def safe_org(hierarchy, index):
    """Safely extract an organization name from the hierarchy list."""
    try:
        return hierarchy[index].get("name", "")
    except (IndexError, TypeError, AttributeError):
        return ""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}

            keyword = body.get("keyword", "")
            opp_type = body.get("opp_type", "")
            active_only = body.get("active_only", False)
            naics = body.get("naics", "")
            page = int(body.get("page", 0))

            # Build the query string: combine keyword and NAICS if both present
            query_parts = []
            if keyword:
                query_parts.append(keyword)
            if naics:
                query_parts.append(naics)
            q = " ".join(query_parts) if query_parts else "*"

            # Build URL parameters
            params = {
                "index": "opp",
                "q": q,
                "page": str(page),
                "size": "25",
                "sort": "-modifiedDate",
                "mode": "search",
                "responseType": "json",
            }

            if active_only:
                params["is_active"] = "true"

            if opp_type:
                params["notice_type"] = opp_type

            url = "https://sam.gov/api/prod/sgs/v1/search?" + urllib.parse.urlencode(params)

            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "GovContractFinder/1.0")

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Parse results
            embedded = data.get("_embedded", {})
            raw_results = embedded.get("results", [])
            page_info = data.get("page", {})
            total_elements = page_info.get("totalElements", 0)
            page_number = page_info.get("number", 0)
            total_pages = page_info.get("totalPages", 0)

            results = []
            for item in raw_results:
                org_hierarchy = item.get("organizationHierarchy", [])
                opp_type_obj = item.get("type", {})
                descriptions = item.get("descriptions", [])
                description_html = descriptions[0].get("content", "") if descriptions else ""

                results.append({
                    "id": item.get("_id", ""),
                    "title": item.get("title", ""),
                    "sol_number": item.get("solicitationNumber", ""),
                    "department": safe_org(org_hierarchy, 0),
                    "agency": safe_org(org_hierarchy, 1),
                    "office": safe_org(org_hierarchy, 2),
                    "type_code": opp_type_obj.get("code", ""),
                    "type_value": opp_type_obj.get("value", ""),
                    "posted_date": item.get("postedDate", ""),
                    "modified_date": item.get("modifiedDate", ""),
                    "response_deadline": item.get("responseDeadLine", ""),
                    "description": strip_html(description_html)[:500],
                    "active": item.get("active", ""),
                    "sam_url": f"https://sam.gov/opp/{item.get('_id', '')}/view",
                })

            result = {
                "results": results,
                "total": total_elements,
                "page": page_number,
                "has_next": (page_number + 1) < total_pages,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
