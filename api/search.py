"""
Vercel serverless function: USAspending.gov awarded contracts search.

POST /api/search
Body: {keyword, state, naics, min_amount, max_amount, page}
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
            state = body.get("state", "")
            naics = body.get("naics", "")
            raw_min = body.get("min_amount")
            raw_max = body.get("max_amount")
            min_amount = float(raw_min) if raw_min not in (None, "") else None
            max_amount = float(raw_max) if raw_max not in (None, "") else None
            page = int(body.get("page", 1))

            # Combine keyword and NAICS into keywords list
            keywords_list = []
            if keyword:
                keywords_list.append(keyword)
            if naics:
                keywords_list.append(naics)
            if not keywords_list:
                keywords_list.append("*")

            # Build filters
            filters = {
                "keywords": keywords_list,
                "time_period": [
                    {
                        "start_date": "2024-01-01",
                        "end_date": "2026-12-31",
                    }
                ],
                "award_type_codes": ["A", "B", "C", "D"],
            }

            if state:
                filters["place_of_performance_locations"] = [
                    {"country": "USA", "state": state}
                ]

            if min_amount is not None or max_amount is not None:
                amount_filter = {}
                if min_amount is not None:
                    amount_filter["lower_bound"] = min_amount
                if max_amount is not None:
                    amount_filter["upper_bound"] = max_amount
                filters["award_amounts"] = [amount_filter]

            # Build the API request body
            api_body = {
                "filters": filters,
                "fields": [
                    "Award ID",
                    "Recipient Name",
                    "Start Date",
                    "End Date",
                    "Award Amount",
                    "Awarding Agency",
                    "Awarding Sub Agency",
                    "Contract Award Type",
                    "Description",
                    "Place of Performance State Code",
                    "Place of Performance City",
                    "generated_internal_id",
                ],
                "page": page,
                "limit": 25,
                "sort": "Award Amount",
                "order": "desc",
            }

            url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
            payload = json.dumps(api_body).encode("utf-8")

            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "GovContractFinder/1.0")

            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            raw_results = data.get("results", [])
            has_next = data.get("hasNext", False)
            page_metadata = data.get("page_metadata", {})

            # USAspending doesn't always give a total count; use hasNext for paging
            # If hasNext is true we know there are more, show "25+" style total
            total = page_metadata.get("total", None)
            if total is None:
                total = f"{len(raw_results)}+" if has_next else len(raw_results)

            results = []
            for item in raw_results:
                results.append({
                    "award_id": item.get("Award ID", ""),
                    "recipient": item.get("Recipient Name", ""),
                    "start_date": item.get("Start Date", ""),
                    "end_date": item.get("End Date", ""),
                    "amount": item.get("Award Amount", 0),
                    "agency": item.get("Awarding Agency", ""),
                    "sub_agency": item.get("Awarding Sub Agency", ""),
                    "award_type": item.get("Contract Award Type", ""),
                    "description": item.get("Description", ""),
                    "state": item.get("Place of Performance State Code", ""),
                    "city": item.get("Place of Performance City", ""),
                    "internal_id": item.get("generated_internal_id", ""),
                })

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
