import asyncio
import logging
import os
import time
from typing import List

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

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
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            var ellipsisSpan;

            ws.onmessage = function(event) {
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
                var input = document.getElementById("messageText");
                var messages = document.getElementById('messages');
                
                var userMessage = document.createElement('span');
                var userContent = document.createTextNode("You: " + input.value);
                userMessage.appendChild(userContent);
                messages.appendChild(userMessage);

                var lineBreak = document.createElement('br');
                messages.appendChild(lineBreak);

                var chatBotMessage = document.createElement('span');
                var chatBotContent = document.createTextNode("Chatbot: ");
                chatBotMessage.appendChild(chatBotContent);
                messages.appendChild(chatBotMessage);

                ellipsisSpan = document.createElement('span');
                ellipsisSpan.classList.add("ellipsis");
                messages.appendChild(ellipsisSpan);

                ws.send(input.value);
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""


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
