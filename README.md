# 🦦 fastapi-gpt-websocket-http-stream-chat 🦦

A Proof of Concept (PoC) that leverages websockets and HTTP streaming to relay OpenAI's GPT chat completions in real-time using the FastAPI framework. While FastAPI is used here, any API framework supporting websockets and HTTP streaming can be adapted for this purpose.

## Docker Deployment 🐳

### Production Setup 🚀

1. **Build the Docker Image:**

    From the project root, execute:

    ```bash
    docker build -t app .
    ```

2. **Run the Container:**

    ```bash
    docker run -d -p 8000:8000 app
    ```

    The application will be available at: `http://localhost:8000`.

### Development Setup 💻

FastAPI development is made smoother with hot-reloading. I have added a dedicated `Dockerfile.dev` for this.

1. **Build the Development Image:**

    From the project root, execute:

    ```bash
    docker build -f Dockerfile.dev -t app-dev .
    ```

2. **Run the Container with Volume Mount:**

    This mounts the current project directory to the container, allowing you to observe changes in real-time:

    ```bash
    docker run -p 8000:8000 -v $(pwd):/app app-dev
    ```

    Navigate to `http://localhost:8000`. Any source code modifications will instantly reflect in the application.
