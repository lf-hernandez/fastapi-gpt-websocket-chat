from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

mock_openai_response = [{"choices": [{"delta": {"content": "Mocked response"}}]}]


def test_get_homepage():
    response = client.get("/")
    assert response.status_code == 200
    assert "<h1>WebSocket Chat</h1>" in response.text


@patch("openai.ChatCompletion.create")
def test_query_endpoint(mock_openai):
    mock_openai.return_value = mock_openai_response
    response = client.post("/query", json={"text": "Hello"})
    assert response.status_code == 200
    response_content = response.content
    assert len(response_content) > 0


@patch("openai.ChatCompletion.create")
def test_websocket_endpoint(mock_openai):
    mock_openai.return_value = mock_openai_response
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        assert "Mocked response" in data


def test_data_processing():
    event_sample = {"choices": [{"delta": {"content": "Sample response."}}]}

    chunk_message = ""
    if (
        "choices" in event_sample
        and event_sample["choices"][0].get("delta")
        and "content" in event_sample["choices"][0]["delta"]
    ):
        chunk_message = event_sample["choices"][0]["delta"]["content"]

    assert chunk_message == "Sample response."
