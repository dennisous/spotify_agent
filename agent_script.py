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
        print("âŒ Missing Spotify credentials in .env file")
        
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
            print("âœ… Spotify API credentials are valid.")
            return True
        else:
            print(f"âŒ Spotify API credentials are invalid. Status Code: {response.status_code}")

            print(f"Response: {response.json()}")

            return False

    except Exception as e:
        print(f"âŒ An error occurred while contacting the Spotify API: {e}")

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
            print("âœ… Groq API key is valid.")
            return True
        else:
            print(f"âŒ Groq API key is invalid. Status Code: {response.status_code}")
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

    CRITICAL TOOL CALLING RULES:
    - When calling tools, provide parameter values DIRECTLY without any wrapper objects
    - CORRECT format: {"name": "My Playlist", "limit": 5, "public": false}
    - WRONG format: {"name": {"name": "My Playlist"}, "limit": {"limit": 5}}
    - Pass raw values only: strings as "text", numbers as 5, booleans as true/false

    When creating playlists, follow this EXACT workflow:
    1. First, use searchSpotify to find songs matching the user's request
    2. Then, use createPlaylist to create an empty playlist with a name and description
    3. Then, use addTracksToPlaylist to add the track URIs from your search results
    4. Finally, include the playlist URL in your response
    
    Playlist creation rules:
    - If the user does not specify playlist size, limit playlist lengths to only 10 songs
    - Always provide helpful music recommendations based on user preferences and create well-curated playlists with appropriate descriptions
    - IMPORTANT: You MUST call addTracksToPlaylist after creating the playlist - never leave a playlist empty
    - IMPORTANT: After creating and populating a playlist, you MUST include the Spotify playlist URL in your response. The createPlaylist tool returns an object with 'id' and 'external_urls'. Always mention the URL like: "Listen here: https://open.spotify.com/playlist/[playlist_id]"
"""
    def fix_tool_call_parameters(tool_calls):
        if not tool_calls:
            return tool_calls
        
        fixed_calls = []
        for call in tool_calls:
            fixed_call = call.copy()
            
            if 'args' in fixed_call and isinstance(fixed_call['args'], dict):
                fixed_args = {}
                for key, value in fixed_call['args'].items():
                    # Handle both {"description": val} and {"key": {"key": val}} patterns
                    if isinstance(value, dict):
                        # Try "description" key first
                        if 'description' in value:
                            fixed_args[key] = value['description']
                        # Try the key itself (e.g., {"limit": {"limit": 5}})
                        elif key in value:
                            fixed_args[key] = value[key]
                        # If single-key dict, extract the value
                        elif len(value) == 1:
                            fixed_args[key] = list(value.values())[0]
                        else:
                            fixed_args[key] = value
                    else:
                        fixed_args[key] = value
                
                fixed_call['args'] = fixed_args
            
            fixed_calls.append(fixed_call)
        
        return fixed_calls
        # Define assistant (INSIDE create_graph, after llm_with_tools and system_msg)
    def assistant(state: MessagesState):
        try:
            response = llm_with_tools.invoke([system_msg] + state["messages"])
            
            # Fix malformed tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"\nðŸ”§ Fixing {len(response.tool_calls)} tool call(s)...")
                fixed_tool_calls = fix_tool_call_parameters(response.tool_calls)
                response.tool_calls = fixed_tool_calls
                
                for i, call in enumerate(fixed_tool_calls):
                    print(f"   Tool {i+1}: {call.get('name', 'unknown')} with args: {call.get('args', {})}")
            
            return {"messages": [response]}
        
        except Exception as e:
            print(f"âŒ Error in assistant: {e}")
            from langchain_core.messages import AIMessage
            error_msg = AIMessage(content=f"I encountered an error: {str(e)}. Please try rephrasing your request.")
            return {"messages": [error_msg]}
                
    
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

async def invoke_our_graph(agent, st_messages):

    response = await agent.ainvoke({"messages": st_messages})

    return response


# Example of how to run the function

async def main():
    print("Checking API credentials...\n")

    spotify_valid = check_spotify_credentials()
    groq_valid = check_groq_credentials()

    print(f"\nCredentials Summary:")
    print(f"Spotify: {'âœ… Valid' if spotify_valid else 'âŒ Invalid'}")
    print(f"Groq: {'âœ… Valid' if groq_valid else 'âŒ Invalid'}")

    if spotify_valid and groq_valid:
        print("\nðŸŽ‰ All credentials are working!")
    else:
        print("\nâš ï¸  Please fix invalid credentials before proceeding.")
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