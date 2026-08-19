import csv
from io import StringIO


def test_export_tickets_as_csv(client, auth_headers, ticket_payload):
    created = client.post("/tickets", json=ticket_payload, headers=auth_headers).json()

    response = client.get("/tickets/export.csv", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
            "id": str(created["id"]),
            "title": "Cannot access billing portal",
            "customer_email": "alex@example.com",
            "category": "billing",
            "priority": "high",
            "status": "open",
        }
    ]
