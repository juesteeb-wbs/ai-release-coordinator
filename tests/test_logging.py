import logging


def test_request_logging_records_completed_request(client, caplog):
    caplog.set_level(logging.INFO, logger="support_api.requests")

    response = client.get("/health")

    assert response.status_code == 200
    log_record = next(
        record for record in caplog.records if record.name == "support_api.requests"
    )
    assert log_record.message == "request completed"
    assert log_record.method == "GET"
    assert log_record.path == "/health"
    assert log_record.status_code == 200
    assert log_record.duration_ms >= 0
