import csv
import spotipy
import SpotifySecrets  # Rename SpotifySecretsGeneric.py to SpotifySecrets.py, and add your secret info
from spotipy.oauth2 import SpotifyOAuth
import SpotipyBootstrap as SpotipyBootstrap


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
            and playlist["collaborative"] == False
            and "Un mix curato con l&#x27;IA Spotify" not in playlist["description"]
            and "A mix curated with Spotify AI" not in playlist["description"]
            and "Twenty noiine" not in playlist["name"]
        ]
        playlists.extend(user_playlists)
        if len(response["items"]) < limit:
            break
        offset += limit
    return playlists


# Function to get all tracks in a playlist
def get_playlist_track_ids(sp, playlists):
    playlist_track_ids = set()
    for playlist in playlists:
        results = sp.playlist_tracks(playlist["id"])
        playlist_track_ids.update([item["track"]["id"] for item in results["items"]])
        while results["next"]:
            results = sp.next(results)
            playlist_track_ids.update(
                [item["track"]["id"] for item in results["items"]]
            )
        print("got a playlists tracks")
    return playlist_track_ids


# Function to get all tracks in a playlist
def get_current_user_saved_tracks(sp: SpotipyBootstrap.spotipy.Spotify):
    saved_track_ids = set()
    results = sp.current_user_saved_tracks(offset=0, limit=50)
    saved_track_ids.update([item["track"]["id"] for item in results["items"]])
    while results["next"]:
        results = sp.next(results)
        saved_track_ids.update([item["track"]["id"] for item in results["items"]])
    return saved_track_ids


def save_tracks_to_user(sp: SpotipyBootstrap.spotipy.Spotify, tracks):
    while tracks:
        track_slice = []
        try:
            for i in range(50):
                track_slice.append(tracks.pop())
        except KeyError:
            pass
        sp.current_user_saved_tracks_add(track_slice)


def main():
    saved_track_ids = get_current_user_saved_tracks(SpotipyBootstrap.sp)
    print("got saved track ids")
    # Fetch the playlists
    user_playlists = get_user_playlists(
        SpotipyBootstrap.sp, SpotifySecrets.SPOTIFY_USERNAME
    )
    print("got user playlists")
    # Fetch tracks for each playlist
    all_playlist_track_ids = get_playlist_track_ids(SpotipyBootstrap.sp, user_playlists)
    print("got all tracks from all playlists")
    # Prepare data for CSV
    save_tracks_to_user(SpotipyBootstrap.sp, all_playlist_track_ids - saved_track_ids)


if __name__ == "__main__":
    main()
