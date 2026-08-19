def test_create_ticket(client, auth_headers, ticket_payload):
    response = client.post("/tickets", json=ticket_payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == ticket_payload["title"]
    assert body["customer_email"] == ticket_payload["customer_email"]
    assert body["category"] == "billing"
    assert body["priority"] == "high"
    assert body["status"] == "open"
    assert body["created_at"]
    assert body["updated_at"]


def test_create_ticket_rejects_invalid_payload(client, auth_headers):
    response = client.post(
        "/tickets",
        json={
            "title": "No",
            "description": "Too short",
            "customer_email": "not-an-email",
            "category": "billing",
            "priority": "urgent",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_list_tickets_returns_created_tickets(client, auth_headers, ticket_payload):
    client.post("/tickets", json=ticket_payload, headers=auth_headers)
    client.post(
        "/tickets",
        json={
            **ticket_payload,
            "title": "Mobile app crashes after login",
            "customer_email": "sam@example.com",
            "category": "technical",
            "priority": "urgent",
        },
        headers=auth_headers,
    )

    response = client.get("/tickets", headers=auth_headers)

    assert response.status_code == 200
    assert [ticket["title"] for ticket in response.json()] == [
        "Cannot access billing portal",
        "Mobile app crashes after login",
    ]


def test_list_tickets_filters_by_category_priority_and_status(
    client,
    auth_headers,
    ticket_payload,
):
    first = client.post("/tickets", json=ticket_payload, headers=auth_headers).json()
    second = client.post(
        "/tickets",
        json={
            **ticket_payload,
            "title": "Question about roadmap",
            "customer_email": "jordan@example.com",
            "category": "product",
            "priority": "low",
        },
        headers=auth_headers,
    ).json()
    client.patch(
        f"/tickets/{second['id']}",
        json={"status": "resolved"},
        headers=auth_headers,
    )

    high_response = client.get("/tickets?priority=high", headers=auth_headers)
    resolved_product_response = client.get(
        "/tickets?category=product&status=resolved",
        headers=auth_headers,
    )

    assert [ticket["id"] for ticket in high_response.json()] == [first["id"]]
    assert [ticket["id"] for ticket in resolved_product_response.json()] == [second["id"]]


def test_list_tickets_filters_by_customer_email(client, auth_headers, ticket_payload):
    first = client.post("/tickets", json=ticket_payload, headers=auth_headers).json()
    client.post(
        "/tickets",
        json={
            **ticket_payload,
            "title": "Mobile app crashes after login",
            "customer_email": "sam@example.com",
            "category": "technical",
        },
        headers=auth_headers,
    )

    response = client.get(
        "/tickets?customer_email=alex@example.com",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert [ticket["id"] for ticket in response.json()] == [first["id"]]


def test_get_ticket_by_id(client, auth_headers, ticket_payload):
    created = client.post("/tickets", json=ticket_payload, headers=auth_headers).json()

    response = client.get(f"/tickets/{created['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_ticket_returns_404_for_unknown_ticket(client, auth_headers):
    response = client.get("/tickets/999", headers=auth_headers)

    assert response.status_code == 404


def test_update_ticket(client, auth_headers, ticket_payload):
    created = client.post("/tickets", json=ticket_payload, headers=auth_headers).json()

    response = client.patch(
        f"/tickets/{created['id']}",
        json={"status": "in_progress", "priority": "urgent", "category": "technical"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "urgent"
    assert body["category"] == "technical"
    assert body["updated_at"] >= body["created_at"]


def test_update_ticket_returns_404_for_unknown_ticket(client, auth_headers):
    response = client.patch(
        "/tickets/999",
        json={"status": "closed"},
        headers=auth_headers,
    )

    assert response.status_code == 404
