import os
import requests
from dotenv import load_dotenv

load_dotenv()

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

# Example of how to run the function

def main():

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



if __name__ == "__main__":

    main()