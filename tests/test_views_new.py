import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def test_command_view_with_no_data_returns_400(client):
    response = client.post("/v3/command/1/")
    assert response.status_code == 400


def test_command_view(client):
    response = client.post(
        "/v3/command/1/",
        data={
            "user_id": 1,
            "command": "Pulse Open",
            "msg_time_int": 0,
            "dry_run": False,
            "link_type": "cheeks",
        },
    )
    assert response.status_code == 200
