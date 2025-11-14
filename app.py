import os
from dotenv import load_dotenv

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent_script import invoke_our_graph, create_graph

import asyncio
import nest_asyncio

import time
import requests
import json

load_dotenv()  # Load environment variables from a .env file if present

st.title("🎵Spotify Agent🎵")

# Load Spotify credentials for API calls
def load_spotify_config():
    """Load Spotify configuration from config file"""
    try:
        # Try multiple possible paths
        possible_paths = [
            'spotify-config.json',
            'spotify-mcp-server/spotify-config.json',
            os.path.join(os.path.dirname(__file__), 'spotify-mcp-server', 'spotify-config.json')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        
        st.warning("Could not find spotify-config.json. Audio preview will be disabled.")
        return None
    except Exception as e:
        st.error(f"Could not load Spotify config: {e}")
        return None

def get_playlist_preview(playlist_id, access_token):
    """Get the first track with a preview URL from a playlist"""
    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Add a small delay to allow tracks to be added to the playlist
        time.sleep(2)
        
        # Request more tracks to increase chances of finding one with a preview
        response = requests.get(
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=10',
            headers=headers
        )
        
        print(f"\n🔍 Searching for preview in playlist {playlist_id}...")
        
        if response.status_code == 200:
            data = response.json()
            if data['items'] and len(data['items']) > 0:
                print(f"✅ Found {len(data['items'])} tracks in playlist")
                
                # Try to find a track with a preview URL
                for idx, item in enumerate(data['items'], 1):
                    track = item['track']
                    if track:
                        track_name = track.get('name', 'Unknown')
                        has_preview = track.get('preview_url') is not None
                        print(f"  Track {idx}: {track_name} - Preview: {'✅ YES' if has_preview else '❌ NO'}")
                        
                        if has_preview:
                            print(f"🎵 Found track with preview: {track_name}")
                            return {
                                'name': track['name'],
                                'artist': track['artists'][0]['name'],
                                'preview_url': track['preview_url'],
                                'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                            }
                
                # If no preview found, return info without preview
                print("⚠️ No tracks with preview found in first 10 songs")
                track = data['items'][0]['track']
                return {
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'preview_url': None,
                    'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
            else:
                print("❌ No tracks found in playlist")
                return None
        else:
            print(f"❌ Failed to fetch playlist tracks. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error fetching playlist preview: {e}")
        return None


if "messages" not in st.session_state:
    # default initial message to render in message state
    st.session_state["messages"] = [AIMessage(content="How can I help you?")]

if "agent" not in st.session_state:
    st.session_state["agent"] = asyncio.run(create_graph())

agent = st.session_state["agent"]

for msg in st.session_state.messages:
    if type(msg) == AIMessage:
        st.chat_message("assistant").write(msg.content)
    if type(msg) == HumanMessage:
        st.chat_message("user").write(msg.content)

# takes new input in chat box from user and invokes the graph
if prompt := st.chat_input():
    st.session_state.messages.append(HumanMessage(content=prompt))
    st.chat_message("user").write(prompt)

    # Process the AI's response and handles graph events using the callback mechanism
    with st.chat_message("assistant"):
        # Convert LangChain messages to serializable dictionaries
        serialized_messages = []
        for msg in st.session_state.messages:
            if isinstance(msg, AIMessage):
                serialized_messages.append({"type": "ai", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                serialized_messages.append({"type": "human", "content": msg.content})
        
        # Send serialized messages to backend
        output = requests.post("http://localhost:8000/chat", json={"input": serialized_messages})
        output = output.json()
        response_text = output["response"]["messages"][-1]['content']
        print(f"\n{'='*50}")
        print(f"DEBUG - Response Text:")
        print(response_text)
        print(f"{'='*50}\n")
        
        # Check if this is a playlist creation response
        is_playlist_creation = (
            ("playlist" in response_text.lower() or "tracks" in response_text.lower()) 
            and any(keyword in response_text.lower() for keyword in ["created", "added", "curated", "here's"])
            and any(char.isdigit() for char in response_text)  # Has numbered list
        )
        
        print(f"DEBUG - is_playlist_creation: {is_playlist_creation}")
        print(f"DEBUG - has 'playlist': {'playlist' in response_text.lower()}")
        print(f"DEBUG - has 'created/added/curated/here's': {any(keyword in response_text.lower() for keyword in ['created', 'added', 'curated'])}")
        print(f"DEBUG - has numbers: {any(char.isdigit() for char in response_text)}")
        print(f"DEBUG - has spotify URL: {'spotify.com/playlist/' in response_text}")
        print(f"{'='*50}\n")
        
        # Alternative detection: if there's a Spotify playlist URL, it's probably a playlist creation
        has_spotify_url = 'spotify.com/playlist/' in response_text or 'open.spotify.com/playlist/' in response_text
        if has_spotify_url and not is_playlist_creation:
            print("DEBUG - Detected via Spotify URL fallback")
            is_playlist_creation = True
        
        if is_playlist_creation:
            # Show fancy playlist building animation
            st.write("🎵 Building your playlist...")
            progress_bar = st.progress(0)
            
            # Parse song count from response (look for numbered items)
            import re
            song_matches = re.findall(r'^\d+\.', response_text, re.MULTILINE)
            total_songs = len(song_matches) if song_matches else 10
            
            # Simulate building process with progress bar
            for i in range(total_songs):
                progress_bar.progress((i + 1) / total_songs)
                time.sleep(0.15)  # Brief pause for effect
            
            st.success(f"✅ Playlist created with {total_songs} songs!")
            
            # Try to extract playlist ID from response and fetch preview
            # Look for Spotify playlist URLs in the response
            playlist_url_match = re.search(r'spotify\.com/playlist/([a-zA-Z0-9]+)', response_text)
            if playlist_url_match:
                playlist_id = playlist_url_match.group(1)
                spotify_config = load_spotify_config()
                
                if spotify_config and 'accessToken' in spotify_config:
                    st.write("🎧 Loading first preview of the added songs...")
                    preview_data = get_playlist_preview(playlist_id, spotify_config['accessToken'])
                    
                    if preview_data:
                        # Show song info with album art
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if preview_data['album_art']:
                                st.image(preview_data['album_art'], width=80)
                        with col2:
                            st.write(f"**{preview_data['name']}**")
                            st.caption(f"by {preview_data['artist']}")
                        
                        # Play preview if available
                        if preview_data['preview_url']:
                            st.audio(preview_data['preview_url'], format='audio/mp3')
                        else:
                            st.info("Preview not available for the added tracks")
                    else:
                        st.warning("⚠️ Playlist created but tracks are still being added. Check your Spotify app to see the playlist!")
                else:
                    st.info("Audio preview disabled - check spotify-config.json")
            else:
                st.info("Playlist URL not found in response - preview unavailable")
            
            time.sleep(0.5)
            
            # Now show the response with streaming effect
            placeholder = st.empty()
            streamed_text = ""
            for token in response_text.split():
                streamed_text += token + " "
                placeholder.write(streamed_text)
                time.sleep(0.05)  # Faster since we already showed progress
        else:
            # Regular response - just stream the text
            placeholder = st.empty()
            streamed_text = ""
            for token in response_text.split():
                streamed_text += token + " "
                placeholder.write(streamed_text)
                time.sleep(0.07)  # Adjust speed as needed

        st.session_state.messages.append(AIMessage(content=response_text))



