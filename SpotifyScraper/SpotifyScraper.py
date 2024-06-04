import csv
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


# Get current user's playlists created by the user
def get_user_playlists(sp, user_id):
    playlists = []
    offset = 0
    limit = 50
    while True:
        response = sp.current_user_playlists(offset=offset, limit=limit)
        user_playlists = [
            playlist
            for playlist in response["items"]
            if playlist["owner"]["id"] == user_id
        ]
        playlists.extend(user_playlists)
        if len(response["items"]) < limit:
            break
        offset += limit
    return playlists


# Function to get all tracks in a playlist
def get_playlist_tracks(sp, playlists):
    playlist_tracks = {}
    for playlist in playlists:
        tracks = []
        results = sp.playlist_tracks(playlist["id"])
        tracks.extend(
            [
                f"{item['track']['artists'][0]['name']} - {item['track']['name']}"
                for item in results["items"]
            ]
        )
        while results["next"]:
            results = sp.next(results)
            tracks.extend(
                [
                    f"{item['track']['artists'][0]['name']} - {item['track']['name']}"
                    for item in results["items"]
                ]
            )
        playlist_tracks[playlist["name"]] = tracks
    return playlist_tracks


# Fetch the playlists
user_playlists = get_user_playlists(sp, SpotifySecrets.SPOTIFY_USERNAME)
# Fetch tracks for each playlist
playlist_tracks = get_playlist_tracks(sp, user_playlists)
# Prepare data for CSV
csv_data = []
for playlist_name, tracks in playlist_tracks.items():
    for track in tracks:
        csv_data.append(["Charlie", f"{playlist_name} Charlie", track])

# Export to CSV
csv_file = "Charlies_playlists.csv"
with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["user_id", "playlist_name", "song"])  # Write header
    writer.writerows(csv_data)  # Write data

print(f"Data has been exported to {csv_file}")
exit()
# Display the tracks in each playlist
for playlist_name, tracks in playlist_tracks.items():
    print(f"Playlist: {playlist_name}")
    for track in tracks:
        print(f" - {track}")
    print("-" * 40)
