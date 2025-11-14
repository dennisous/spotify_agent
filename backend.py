# Step 1: Basic Imports and Setup
from fastapi import FastAPI
from pydantic import BaseModel
from agent_script import create_graph, invoke_our_graph
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables (for API keys)
load_dotenv()

# Step 2: Application Lifecycle Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create the agent when the server starts
    print("Starting up... Creating Spotify agent...")
    app.state.agent = await create_graph()
    print("Agent created successfully!")
    
    yield  # Server is running
    
    # Shutdown: Clean up when server stops
    print("Shutting down...")

# Step 3: Create FastAPI app with lifecycle management
app = FastAPI(
    title="Spotify Agent API",
    description="A FastAPI backend for the Spotify agent",
    lifespan=lifespan
)

# Step 4: Define Request/Response Models
class ChatQuery(BaseModel):
    input: List[Dict[str, Any]]

# Step 5: Create API Endpoint (NOT indented under the class)
@app.post("/chat")
async def chat(query: ChatQuery):
    agent = app.state.agent
    if agent is None:
        return {"error": "Agent not initialized"}

    # Convert dict messages to tuples format
    messages = [(msg.get("type", "human"), msg.get("content", "")) for msg in query.input]
    response = await invoke_our_graph(agent, messages)
    print(response)
    return {"response": response}