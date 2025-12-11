import os
import csv
from collections import defaultdict

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "..", "data")
clusters_path = os.path.join(data_dir, "song_clusters.csv")
isolated_path = os.path.join(data_dir, "isolated_songs.csv")
matched_path = os.path.join(data_dir, "matched_songs.csv")
library_path = os.path.join(data_dir, "library.csv")
output_dir = os.path.join(base_dir, "..", "playlists")


def load_matched_songs_mapping(csv_path: str):
    """
    Load the mapping from database songs to library songs.
    Returns dict: (database_title, database_artist) -> (library_title, library_artist)
    """
    mapping = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_title = row.get("database_title", "").strip()
            db_artist = row.get("database_artist", "").strip()
            lib_title = row.get("library_title", "").strip()
            lib_artist = row.get("library_artist", "").strip()

            if db_title and db_artist and lib_title and lib_artist:
                mapping[(db_title, db_artist)] = (lib_title, lib_artist)

    return mapping


def load_library_paths(csv_path: str):
    """
    Load library with file paths.
    Returns dict: (title, artist) -> file_path
    Assumes library.csv has columns: Artist, Title, and potentially FilePath or Location
    """
    library = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            artist = row.get("Artist", "").strip()
            title = row.get("Title", "").strip()
            # Try common column names for file path
            file_path = (
                row.get("FilePath", "")
                or row.get("Location", "")
                or row.get("Path", "")
                or row.get("File", "")
            ).strip()

            if title and artist:
                # If no path in CSV, construct a placeholder
                if not file_path:
                    file_path = f"{artist} - {title}.mp3"
                library[(title, artist)] = file_path

    return library


def load_clusters(csv_path: str):
    """
    Load song clusters.
    Returns dict: cluster_id -> list of (song_title, song_artist)
    """
    clusters = defaultdict(list)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("song_title", "").strip()
            artist = row.get("song_artist", "").strip()
            cluster_id = row.get("cluster_id", "").strip()

            if title and artist and cluster_id:
                clusters[cluster_id].append((title, artist))

    return clusters


def load_isolated_songs(csv_path: str):
    """
    Load isolated songs.
    Returns list of (song_title, song_artist)
    """
    isolated = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("database_title", "").strip()
            artist = row.get("database_artist", "").strip()

            if title and artist:
                isolated.append((title, artist))

    return isolated


def create_m3u_playlist(songs, output_path, playlist_name):
    """
    Create an .m3u playlist file.

    Args:
        songs: list of file paths
        output_path: path to save the .m3u file
        playlist_name: name of the playlist
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Playlist: {playlist_name}\n")
        f.write(f"# Songs: {len(songs)}\n")
        for song_path in songs:
            f.write(f"{song_path}\n")

    print(f"Created playlist: {output_path} ({len(songs)} tracks)")


def main():
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print("Loading matched songs mapping...")
    db_to_lib_mapping = load_matched_songs_mapping(matched_path)
    print(f"Loaded {len(db_to_lib_mapping)} song mappings")

    print("\nLoading library paths...")
    library = load_library_paths(library_path)
    print(f"Loaded {len(library)} library tracks")

    print("\nLoading clusters...")
    clusters = load_clusters(clusters_path)
    print(f"Loaded {len(clusters)} clusters")

    print("\nLoading isolated songs...")
    isolated_songs = load_isolated_songs(isolated_path)
    print(f"Loaded {len(isolated_songs)} isolated tracks")

    # Track statistics
    total_playlists = 0
    total_tracks_in_playlists = 0
    songs_not_found = []

    # Create playlists for each cluster
    print("\nCreating cluster playlists...")
    def sort_key(item):
        cid = item[0]
        # Handle mixed numeric/string cluster ids safely
        return (0, int(cid)) if isinstance(cid, str) and cid.isdigit() else (1, str(cid))

    for cluster_id, songs in sorted(clusters.items(), key=sort_key):
        file_paths = []

        for db_title, db_artist in songs:
            # Map database song to library song
            lib_key = db_to_lib_mapping.get((db_title, db_artist))

            if lib_key and lib_key in library:
                file_paths.append(library[lib_key])
            else:
                songs_not_found.append((db_title, db_artist, "cluster", cluster_id))

        if file_paths:
            playlist_path = os.path.join(output_dir, f"cluster_{cluster_id}.m3u")
            create_m3u_playlist(file_paths, playlist_path, f"Cluster {cluster_id}")
            total_playlists += 1
            total_tracks_in_playlists += len(file_paths)

    # Create playlist for isolated songs
    if isolated_songs:
        print("\nCreating isolated songs playlist...")
        file_paths = []

        for db_title, db_artist in isolated_songs:
            lib_key = db_to_lib_mapping.get((db_title, db_artist))

            if lib_key and lib_key in library:
                file_paths.append(library[lib_key])
            else:
                songs_not_found.append((db_title, db_artist, "isolated", "N/A"))

        if file_paths:
            playlist_path = os.path.join(output_dir, "isolated_songs.m3u")
            create_m3u_playlist(file_paths, playlist_path, "Isolated Songs")
            total_playlists += 1
            total_tracks_in_playlists += len(file_paths)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total playlists created: {total_playlists}")
    print(f"Total tracks in playlists: {total_tracks_in_playlists}")
    print(f"Songs not found in library: {len(songs_not_found)}")

    if songs_not_found:
        print(f"\nFirst 10 songs not found:")
        for i, (title, artist, source, cluster) in enumerate(songs_not_found[:10]):
            print(f"  {i+1}. {title} - {artist} (from {source} {cluster})")

        # Save not found songs to CSV
        not_found_path = os.path.join(data_dir, "songs_not_found_in_library.csv")
        with open(not_found_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["database_title", "database_artist", "source", "cluster_id"]
            )
            for title, artist, source, cluster in songs_not_found:
                writer.writerow([title, artist, source, cluster])
        print(f"\nFull list saved to: {not_found_path}")

    print(f"\nPlaylists saved to: {output_dir}")


if __name__ == "__main__":
    main()
