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


def find_isolated_tracks(json_path: str, matched_songs: set):
    """
    Find tracks that only ever appear alone in playlists (as the only matched song).

    Returns a set of (database_title, database_artist) tuples.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Track how many times each song appears alone vs. with others
    song_appearances = {}  # (title, artist): {'alone': count, 'with_others': count}

    for playlist in data:
        tracks = playlist.get("tracks", [])

        # Filter to only matched songs
        matched_tracks = []
        for track in tracks:
            if isinstance(track, list) and len(track) == 2:
                title, artist = track
                if (title, artist) in matched_songs:
                    matched_tracks.append((title, artist))

        # Count appearances
        if len(matched_tracks) == 1:
            # This song appears alone
            song = matched_tracks[0]
            if song not in song_appearances:
                song_appearances[song] = {"alone": 0, "with_others": 0}
            song_appearances[song]["alone"] += 1
        elif len(matched_tracks) > 1:
            # These songs appear together
            for song in matched_tracks:
                if song not in song_appearances:
                    song_appearances[song] = {"alone": 0, "with_others": 0}
                song_appearances[song]["with_others"] += 1

    # Find songs that ONLY appear alone (never with other matched songs)
    isolated_tracks = set()
    for song, counts in song_appearances.items():
        if counts["alone"] > 0 and counts["with_others"] == 0:
            isolated_tracks.add(song)

    return isolated_tracks


def save_isolated_tracks(isolated_tracks: set, output_path: str):
    """
    Save isolated tracks to a CSV file.

    CSV format: database_title, database_artist
    """

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["database_title", "database_artist"])

        for title, artist in sorted(isolated_tracks):
            writer.writerow([title, artist])

    print(f"Isolated tracks saved to: {output_path} (count={len(isolated_tracks)})")


if __name__ == "__main__":
    # Step 1: Extract matched songs from CSV
    print("Step 1: Loading matched songs from CSV...")
    matched_songs = extract_matched_songs(matched_path)
    print(f"Extracted {len(matched_songs)} unique songs from matched_songs_1.csv\n")

    # Step 2: Filter the large database to only include matched songs
    print("Step 2: Filtering large database by matched songs...")
    filtered_playlists = filter_database_by_matched_songs(json_path, matched_songs)

    # Step 3: Find tracks that only appear alone in playlists
    print("\nStep 3: Finding tracks that only appear alone in playlists...")
    isolated_tracks = find_isolated_tracks(json_path, matched_songs)
    isolated_output_path = os.path.join(base_dir, "..", "data", "isolated_songs.csv")
    save_isolated_tracks(isolated_tracks, isolated_output_path)

    # Save the filtered database
    output_path = os.path.join(base_dir, "..", "data", "filtered_playlists.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered_playlists, f, ensure_ascii=False, indent=2)
    print(f"\nFiltered database saved to: {output_path}")
