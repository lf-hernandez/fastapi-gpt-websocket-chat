import asyncio
import json
import logging
import os
import time
from typing import List

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
app = FastAPI()
logging.basicConfig(level=logging.DEBUG)

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
        <style>
            body {
                margin: 0;
                padding: 50px;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }
            #messages {
                margin-top: 10px;
                max-width: 30vw;
            }
            @keyframes ellipsis {
                0% { content: '.'; }
                33% { content: '..'; }
                66% { content: '...'; }
                100% { content: '.'; }
            }
            .ellipsis {
                display: inline-block;
                width: 20px;
                height: 20px;
                position: relative;
                top: -2px;
            }
            .ellipsis::after {
                content: '.';
                animation: ellipsis 1.5s infinite;
            }
        </style>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <div id='messages'>
        </div>
    </body>
</html>
"""

websocket_js = """
<script>
    var ws = new WebSocket('ws://localhost:8000/ws');
    var ellipsisSpan;

    ws.onmessage = function (event) {
        var messages = document.getElementById('messages');

        if (ellipsisSpan) {
            ellipsisSpan.remove();
        }

        var message = document.createElement('span');
        var content = document.createTextNode(event.data);
        message.appendChild(content);
        messages.appendChild(message);
    };

    function sendMessage(event) {
        var input = document.getElementById('messageText');
        var messages = document.getElementById('messages');

        var userMessage = document.createElement('span');
        var userContent = document.createTextNode('You: ' + input.value);
        userMessage.appendChild(userContent);
        messages.appendChild(userMessage);

        var lineBreak = document.createElement('br');
        messages.appendChild(lineBreak);

        var chatBotMessage = document.createElement('span');
        var chatBotContent = document.createTextNode('Chatbot: ');
        chatBotMessage.appendChild(chatBotContent);
        messages.appendChild(chatBotMessage);

        ellipsisSpan = document.createElement('span');
        ellipsisSpan.classList.add('ellipsis');
        messages.appendChild(ellipsisSpan);

        ws.send(input.value);
        input.value = '';
        event.preventDefault();
    }
</script>
"""
http_js = """
<script>
    var ellipsisSpan;

    function sendMessage(event) {
        var input = document.getElementById('messageText');
        var messages = document.getElementById('messages');

        var userMessage = document.createElement('span');
        var userContent = document.createTextNode('You: ' + input.value);
        userMessage.appendChild(userContent);
        messages.appendChild(userMessage);

        var lineBreak = document.createElement('br');
        messages.appendChild(lineBreak);

        var chatBotMessage = document.createElement('span');
        var chatBotContent = document.createTextNode('Chatbot: ');
        chatBotMessage.appendChild(chatBotContent);
        messages.appendChild(chatBotMessage);

        ellipsisSpan = document.createElement('span');
        ellipsisSpan.classList.add('ellipsis');
        messages.appendChild(ellipsisSpan);

        fetchQuery(input.value, chatBotMessage);

        input.value = '';
        event.preventDefault();
    }

    function fetchQuery(inputValue, chatBotMessage) {
        fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: inputValue }),
        })
            .then((response) => {
                if (!response.body) {
                    throw new Error('ReadableStream not present in response');
                }
                const reader = response.body.getReader();
                return processStream(reader, chatBotMessage);
            })
            .catch((error) => {
                console.error('There was an error querying the endpoint:', error);
            });
    }

    function processStream(reader, chatBotMessage) {
        return reader.read().then(({ done, value }) => {
            if (done) {
                return;
            }

            const text = new TextDecoder('utf-8').decode(value);

            try {
                const data = JSON.parse(text);
                if (data.status === 'pending') {
                    return processStream(reader, chatBotMessage);
                } else {
                    if (ellipsisSpan) {
                        ellipsisSpan.remove();
                    }
                    var messageContent = document.createTextNode(data.message);
                    chatBotMessage.appendChild(messageContent);
                }
            } catch (err) {
                console.error('Error parsing JSON:', err);
            }
            return processStream(reader, chatBotMessage);
        });
    }
</script>
"""
html = html + http_js
# html = html + websocket_js


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_response(self, websocket: WebSocket, message: str):
        if websocket in self.active_connections:
            await websocket.send_text(message)


manager = ConnectionManager()


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.post("/query")
async def query_endpoint(data: dict):
    text = data.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    async def stream_response():
        start_time = time.time()
        completion_text = ""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": text}],
            stream=True,
        )

        for event in response:
            if (
                "choices" in event
                and event["choices"][0].get("delta")
                and "content" in event["choices"][0]["delta"]
            ):
                elapsed_time = time.time() - start_time
                chunk_message = event["choices"][0]["delta"]["content"]
                logging.debug(
                    f"Text received: {chunk_message} ({elapsed_time:.2f} seconds after request)"
                )
                completion_text += chunk_message
                await asyncio.sleep(0.1)
                yield json.dumps({"message": chunk_message})

        logging.debug(
            f"Full response received {elapsed_time:.2f} seconds after request"
        )
        logging.debug(f"Full text received: {completion_text}")

    return StreamingResponse(stream_response(), media_type="text/plain")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()

            start_time = time.time()
            completion_text = ""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": data}],
                stream=True,
            )

            for event in response:
                if (
                    "choices" in event
                    and event["choices"][0].get("delta")
                    and "content" in event["choices"][0]["delta"]
                ):
                    chunk_message = event["choices"][0]["delta"]["content"]
                    elapsed_time = time.time() - start_time
                    if chunk_message:
                        logging.debug(
                            f"Text received: {chunk_message} ({elapsed_time:.2f} seconds after request)"
                        )
                        completion_text += chunk_message
                        await asyncio.sleep(0.1)
                        await manager.send_response(websocket, chunk_message)
            logging.debug(
                f"Full response received {elapsed_time:.2f} seconds after request"
            )
            logging.debug(f"Full text received: {completion_text}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
