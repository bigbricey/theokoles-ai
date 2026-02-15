"""
Vercel serverless function: Grants.gov opportunity search.

POST /api/grants
Body: {keyword, status, page}
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}

            keyword = body.get("keyword", "")
            status = body.get("status", "posted")
            page = int(body.get("page", 0))

            # Build the Grants.gov API request body
            api_body = {
                "keyword": keyword,
                "rows": 25,
                "startRecord": page * 25,
                "oppStatuses": status,
            }

            url = "https://apply07.grants.gov/grantsws/rest/opportunities/search"
            payload = json.dumps(api_body).encode("utf-8")

            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "GovContractFinder/1.0")

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Parse results
            raw_results = data.get("oppHits", [])
            total = int(data.get("totalCount", data.get("hitCount", 0)))

            results = []
            for item in raw_results:
                opp_id = item.get("id", item.get("oppId", ""))
                results.append({
                    "id": opp_id,
                    "title": item.get("title", item.get("oppTitle", "")),
                    "agency": item.get("agency", item.get("agencyName", "")),
                    "number": item.get("number", item.get("oppNumber", "")),
                    "status": item.get("oppStatus", status),
                    "open_date": item.get("openDate", ""),
                    "close_date": item.get("closeDate", ""),
                    "doc_type": item.get("docType", ""),
                    "grants_url": f"https://www.grants.gov/search-results-detail/{opp_id}",
                })

            has_next = ((page + 1) * 25) < total

            result = {
                "results": results,
                "total": total,
                "page": page,
                "has_next": has_next,
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
