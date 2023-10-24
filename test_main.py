from unittest.mock import patch

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
