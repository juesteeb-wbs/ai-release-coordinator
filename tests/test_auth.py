def test_ticket_endpoints_require_api_key(client):
    response = client.get("/tickets")

    assert response.status_code == 401
    assert response.json()["detail"] == "A valid X-API-Key header is required."


def test_ticket_endpoints_reject_invalid_api_key(client):
    response = client.get("/tickets", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_ticket_endpoints_reject_blank_api_key(client):
    response = client.get("/tickets", headers={"X-API-Key": "   "})

    assert response.status_code == 401


def test_ticket_endpoints_reject_padded_api_key(client, api_key):
    response = client.get("/tickets", headers={"X-API-Key": f" {api_key} "})

    assert response.status_code == 401
