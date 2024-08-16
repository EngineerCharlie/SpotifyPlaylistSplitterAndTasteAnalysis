import spotipy
import SpotifySecrets  # Rename SpotifySecretsGeneric.py to SpotifySecrets.py, and add your secret info
from spotipy.oauth2 import SpotifyOAuth

# Define your Spotify API credentials
SPOTIPY_CLIENT_ID = SpotifySecrets.SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET = SpotifySecrets.SPOTIPY_CLIENT_SECRET
SPOTIPY_REDIRECT_URI = SpotifySecrets.SPOTIPY_REDIRECT_URI

# Scope for accessing user's playlists
scope = "playlist-read-private"  # playlist-read-collaborative"

# Authenticate and create a Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=scope,
    )
)
