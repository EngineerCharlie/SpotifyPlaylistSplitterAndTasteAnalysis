import spotipy
import SpotifySecrets  # Rename SpotifySecretsGeneric.py to SpotifySecrets.py, and add your secret info
from spotipy.oauth2 import SpotifyOAuth

# Define your Spotify API credentials
SPOTIPY_CLIENT_ID = SpotifySecrets.SPOTIPY_CLIENT_ID
SPOTIPY_CLIENT_SECRET = SpotifySecrets.SPOTIPY_CLIENT_SECRET
SPOTIPY_REDIRECT_URI = SpotifySecrets.SPOTIPY_REDIRECT_URI

# Scope for accessing user's playlists
scope = "playlist-read-private playlist-read-collaborative"

# Authenticate and create a Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=scope,
    )
)


# Get current user's playlists
def get_user_playlists(sp):
    playlists = []
    offset = 0
    limit = 50
    while True:
        response = sp.current_user_playlists(offset=offset, limit=limit)
        playlists.extend(response["items"])
        if len(response["items"]) < limit:
            break
        offset += limit
    return playlists


# Fetch the playlists
user_playlists = get_user_playlists(sp)

# Display playlist details
for playlist in user_playlists:
    print(f"Name: {playlist['name']}")
    print(f"ID: {playlist['id']}")
    print(f"Tracks: {playlist['tracks']['total']}")
    print("-" * 40)
