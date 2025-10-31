import os
import requests
from dotenv import load_dotenv
import subprocess
from langchain_groq import ChatGroq

from langgraph.graph import StateGraph, START, END

from langgraph.prebuilt import tools_condition, ToolNode

from langgraph.graph import MessagesState

import asyncio

from mcp_use.client import MCPClient

from mcp_use.adapters.langchain_adapter import LangChainAdapter

load_dotenv()
PORT = 8090

def check_spotify_credentials():

    """

    Check if Spotify API credentials are valid by attempting to get an access token.

    Returns True if valid, False otherwise.

    """

    client_id = os.getenv("SPOTIFY_CLIENT_ID")

    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")


    
    # Check if credentials exist

    if not all ([client_id, client_secret, redirect_uri]):
        print("❌ Missing Spotify credentials in .env file")
        
        return False

    
    # Test credentials by requesting a client credentials token

    auth_url = "https://accounts.spotify.com/api/token"

    auth_headers = {

        "Content-Type": "application/x-www-form-urlencoded"

    }

    auth_data = {

        "grant_type": "client_credentials",

        "client_id": client_id,

        "client_secret": client_secret

    }


    try:
        response = requests.post(auth_url, headers = auth_headers, data = auth_data)

        if response.status_code == 200:
            print("✅ Spotify API credentials are valid.")
            return True
        else:
            print(f"❌ Spotify API credentials are invalid. Status Code: {response.status_code}")

            print(f"Response: {response.json()}")

            return False

    except Exception as e:
        print(f"❌ An error occurred while contacting the Spotify API: {e}")

        return False

            
def check_groq_credentials():
    """
    Checks if the Groq API key is valid by attempting to list available models.

    Returns:
        bool: True if the key is valid, False otherwise.
    """
    # 1. Get the API key from environment variables
    api_key = os.getenv("GROQ_API_KEY")

    # 2. Check if the API key exists in the .env file
    if not api_key:
        print("Missing groq api key in .env file")
        return False
    # 3. Prepare the request based on Groq's API reference
    # This endpoint is simple and good for a health check.
    models_url = "https://api.groq.com/openai/v1/models"
        
    # The header must be in the format "Authorization: Bearer YOUR_API_KEY"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # 4. Make the API request and handle potential errors
    try:
        response = requests.get(models_url, headers = headers)
        # A 200 status code means the request was successful and the key is valid.
        if response.status_code  == 200:
            print("✅ Groq API key is valid.")
            return True
        else:
            print(f"❌ Groq API key is invalid. Status Code: {response.status_code}")
            print(f"      Response: {response.json()}")
            return False
            # If the key is invalid, Groq typically returns a 401 Unauthorized status.
    except requests.exceptions.RequestException as e:
        print(f" An error occured while contacting the Groq API: {e}")
        return False

def kill_processes_on_port(port = PORT):

    """Kill processes on Windows"""

    try:

        # Find processes using the port

        result = subprocess.run(['netstat', '-ano'],

                              capture_output=True, text=True, check=False)

       

        if result.returncode == 0:

            lines = result.stdout.split('\n')

            pids_to_kill = []

           

            for line in lines:

                if f':{port}' in line and 'LISTENING' in line:

                    parts = line.split()

                    if len(parts) >= 5:

                        pid = parts[-1]  # Last column is PID

                        if pid.isdigit():

                            pids_to_kill.append(pid)

           

            if pids_to_kill:

                print(f"Found processes on port {port}: {pids_to_kill}")

                for pid in pids_to_kill:

                    try:

                        subprocess.run(['taskkill', '/F', '/PID', pid],

                                     check=True, capture_output=True)

                        print(f"Killed process {pid} on port {port}")

                    except subprocess.CalledProcessError as e:

                        print(f"Failed to kill process {pid}: {e}")

            else:

                print(f"No processes found on port {port}")

        else:

            print(f"Failed to run netstat: {result.stderr}")

           

    except Exception as e:

        print(f"Error killing processes on port {port}: {e}")

async def create_graph():
    # Create client
    client = MCPClient.from_config_file("mcp_config.json")
    
    # Create adapter instance
    adapter = LangChainAdapter()
    
    # Load in tools from the MCP client
    tools = await adapter.create_tools(client)
    
    tools = [t for t in tools if t.name not in ['getNowPlaying', 'getRecentlyPlayed', 'getQueue', 'playMusic', 'pausePlayback', 'skipToNext', 'skipToPrevious', 'resumePlayback', 'addToQueue', 'getMyPlaylists', 'getUsersSavedTracks', 'saveOrRemoveAlbum', 'checkUsersSavedAlbums']]
    
    # Define llm
    llm = ChatGroq(model='meta-llama/llama-4-scout-17b-16e-instruct')
    
    # Bind tools
    llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)
    
    system_msg = """You are a helpful assistant that has access to Spotify. You can create playlists, find songs, and provide music recommendations.

    When creating playlists:
    - If the user does not specify playlist size, limit playlist lengths to only 10 songs
    - Always provide helpful music recommendations based on user preferences and create well-curated playlists with appropriate descriptions
    - When the User requests a playlist to be created, ensure that there are actually songs added to the playlist you create
    """
    
    # Define assistant (INSIDE create_graph, after llm_with_tools and system_msg)
    def assistant(state: MessagesState):
        return {"messages": [llm_with_tools.invoke([system_msg] + state["messages"])]}
    
    # Graph
    builder = StateGraph(MessagesState)
    
    # Define nodes: these do the work
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    
    # Define edges: these determine the control flow
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        tools_condition,
    )
    builder.add_edge("tools", "assistant")
    
    graph = builder.compile()
    
    return graph

# Example of how to run the function

async def main():
    print("Checking API credentials...\n")

    spotify_valid = check_spotify_credentials()
    groq_valid = check_groq_credentials()

    print(f"\nCredentials Summary:")
    print(f"Spotify: {'✅ Valid' if spotify_valid else '❌ Invalid'}")
    print(f"Groq: {'✅ Valid' if groq_valid else '❌ Invalid'}")

    if spotify_valid and groq_valid:
        print("\n🎉 All credentials are working!")
    else:
        print("\n⚠️  Please fix invalid credentials before proceeding.")
        return  # Exit if credentials invalid

    kill_processes_on_port(PORT)
    
    agent = await create_graph()

    while True:
        final_text = ""
        message = input("User: ")
        
        # Exit condition
        if message.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        # Invoke the agent with the user's message
        response = await agent.ainvoke({"messages": [("user", message)]})
        
        # Extract and print the assistant's response
        assistant_message = response["messages"][-1].content
        print(f"Assistant: {assistant_message}\n")


if __name__ == "__main__":
    asyncio.run(main())