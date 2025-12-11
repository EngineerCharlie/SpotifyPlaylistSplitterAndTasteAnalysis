import os, json, csv

base_dir = os.path.dirname(__file__)  # .../SpotifyPlaylistSplitter/PlaylistSplitter
filename = "spotify_playlists_data_1.json"
filename = "spotify_playlists_data_backup_2025_12_10.json"
library_path = os.path.join(base_dir, "..", "data", "library.csv")
unmatched_path = os.path.join(base_dir, "..", "data", "unmatched_songs_1.csv")
matched_path = os.path.join(base_dir, "..", "data", "matched_songs_1.csv")
json_path = os.path.join(base_dir, "..", "data", filename)

json_path = os.path.abspath(json_path)


def filter_database_by_matched_songs(json_path: str, matched_songs: set):
    """
    Filters the large database to only include songs that are in the matched set.

    Expected structure:
    [
        {
            "playlist_id": "...",
            "playlist_name": "...",
            "user_id": "...",
            "tracks": [
                ["Track Name", "Artist Name"],
                ...
            ]
        },
        ...
    ]

    Returns a filtered list of playlists containing only matched songs.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    filtered_playlists = []
    total_tracks_before = 0
    total_tracks_after = 0

    for playlist in data:
        tracks = playlist.get("tracks", [])
        total_tracks_before += len(tracks)

        # Filter tracks to only keep those in matched_songs
        filtered_tracks = []
        for track in tracks:
            if isinstance(track, list) and len(track) == 2:
                title, artist = track
                # Check if this exact song is in matched_songs
                if (title, artist) in matched_songs:
                    filtered_tracks.append(track)

        # Only keep playlists that have more than 1 track after filtering
        if len(filtered_tracks) > 1:
            filtered_playlist = playlist.copy()
            filtered_playlist["tracks"] = filtered_tracks
            filtered_playlists.append(filtered_playlist)
            total_tracks_after += len(filtered_tracks)

    print(
        f"Original database: {len(data)} playlists, {total_tracks_before} total tracks"
    )
    print(
        f"Filtered database: {len(filtered_playlists)} playlists, {total_tracks_after} total tracks"
    )
    print(
        f"Removed {total_tracks_before - total_tracks_after} tracks that weren't matched"
    )

    return filtered_playlists


def extract_matched_songs(csv_path: str):
    """
    Extracts database titles and artists from matched songs CSV.

    Expected CSV structure:
    library_title,library_artist,database_title,database_artist,artist_score,title_score

    Returns a set of (database_title, database_artist) tuples.
    """

    unique_songs = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            database_title = row.get("database_title", "").strip()
            database_artist = row.get("database_artist", "").strip()

            if database_title and database_artist:
                unique_songs.add((database_title, database_artist))

    return unique_songs


if __name__ == "__main__":
    # Step 1: Extract matched songs from CSV
    print("Step 1: Loading matched songs from CSV...")
    matched_songs = extract_matched_songs(matched_path)
    print(f"Extracted {len(matched_songs)} unique songs from matched_songs_1.csv\n")

    # Step 2: Filter the large database to only include matched songs
    print("Step 2: Filtering large database by matched songs...")
    filtered_playlists = filter_database_by_matched_songs(json_path, matched_songs)

    # Optional: Save the filtered database
    output_path = os.path.join(base_dir, "..", "data", "filtered_playlists.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered_playlists, f, ensure_ascii=False, indent=2)
    print(f"\nFiltered database saved to: {output_path}")
