import os
import csv
from collections import defaultdict

try:
    from mutagen.easyid3 import EasyID3

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "..", "data")
music_dir = os.path.join(os.path.expanduser("~"), "Music")
clusters_path = os.path.join(data_dir, "song_clusters.csv")
isolated_path = os.path.join(data_dir, "isolated_songs.csv")
matched_path = os.path.join(data_dir, "matched_songs.csv")
library_path = os.path.join(data_dir, "library.csv")
unmatched_path = os.path.join(data_dir, "unmatched_songs.csv")
output_dir = os.path.join(base_dir, "..", "playlists")


def load_matched_songs_mapping(csv_path: str):
    """
    Load the mapping from database songs to library songs.
    Returns dict: (database_title, database_artist) -> list of (library_title, library_artist)
    Note: A single database track may map to multiple library tracks.
    """
    mapping = defaultdict(list)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_title = row.get("database_title", "").strip()
            db_artist = row.get("database_artist", "").strip()
            lib_title = row.get("library_title", "").strip()
            lib_artist = row.get("library_artist", "").strip()

            if db_title and db_artist and lib_title and lib_artist:
                mapping[(db_title, db_artist)].append((lib_title, lib_artist))

    return mapping


def load_music_files_from_disk(music_dir: str):
    """
    Scan the music directory and extract metadata from audio files.
    Returns dict: (title, artist) -> {"path": file_path, "duration": duration_seconds}
    """
    music_files = {}

    if not MUTAGEN_AVAILABLE:
        print(
            "WARNING: mutagen library not available. Install with: pip install mutagen"
        )
        return music_files

    print(f"Scanning music directory: {music_dir}")
    file_count = 0
    failed_count = 0
    for root, dirs, files in os.walk(music_dir):
        for filename in files:
            if filename.lower().endswith((".mp3", ".flac", ".m4a", ".ogg")):
                file_path = os.path.join(root, filename)
                try:
                    # Use generic mutagen.File to handle all formats automatically
                    from mutagen import File as MutagenFile

                    audio = MutagenFile(file_path, easy=True)

                    if audio is None:
                        print(f"Failed to load file: {filename}")
                        failed_count += 1
                        continue

                    # Get metadata (easy=True provides uniform interface)
                    title = None
                    artist = None

                    if "title" in audio:
                        title = (
                            audio["title"][0]
                            if isinstance(audio["title"], list)
                            else audio["title"]
                        )
                    if "artist" in audio:
                        artist = (
                            audio["artist"][0]
                            if isinstance(audio["artist"], list)
                            else audio["artist"]
                        )

                    # Get duration
                    duration = 0
                    if audio.info:
                        duration = int(audio.info.length)

                    if title and artist:
                        key = (title, artist)
                        music_files[key] = {"path": file_path, "duration": duration}
                        file_count += 1
                    else:
                        print(f"Missing title/artist tags in file: {filename}")
                        failed_count += 1
                except Exception as e:
                    # Silently skip files that can't be read
                    print(f"Failed to read metadata for file: {filename} ({e})")
                    failed_count += 1

    print(f"Found {file_count} music files with readable metadata")
    print(f"Failed to read metadata for {failed_count} files")
    return music_files


def normalize_library_key(title: str, artist: str) -> str:
    """Create a normalized key for fuzzy matching titles and artists."""
    import unicodedata
    import re

    def normalize(s):
        # Normalize unicode
        s = unicodedata.normalize("NFKD", s)
        # Convert to lowercase
        s = s.lower()
        # Remove extra whitespace
        s = re.sub(r"\s+", " ", s).strip()
        # Remove special characters except common separators
        s = re.sub(r"[^\w\s\-&]", "", s)
        return s

    return f"{normalize(title)}|{normalize(artist)}"


def match_library_to_disk(library_dict: dict, disk_files: dict):
    """
    Match library entries to actual disk files using fuzzy matching on metadata.
    Returns: merged dict with actual file paths and durations from disk.
    """
    from rapidfuzz import fuzz

    matched_count = 0
    unmatched_entries = []

    result = {}

    for lib_key, lib_info in library_dict.items():
        lib_title, lib_artist = lib_key
        best_match = None
        best_score = 0

        # Try exact match first with normalized keys
        lib_norm_key = normalize_library_key(lib_title, lib_artist)
        for disk_key in disk_files.keys():
            disk_title, disk_artist = disk_key
            disk_norm_key = normalize_library_key(disk_title, disk_artist)
            if lib_norm_key == disk_norm_key:
                best_match = disk_key
                best_score = 100
                break

        # If no exact match, try fuzzy matching
        if best_score < 100:
            for disk_key in disk_files.keys():
                disk_title, disk_artist = disk_key
                title_score = fuzz.token_sort_ratio(
                    lib_title.lower(), disk_title.lower()
                )
                artist_score = fuzz.token_sort_ratio(
                    lib_artist.lower(), disk_artist.lower()
                )
                avg_score = (title_score + artist_score) / 2

                if avg_score > best_score and avg_score >= 80:
                    best_match = disk_key
                    best_score = avg_score

        if best_match:
            result[lib_key] = disk_files[best_match]
            matched_count += 1
        else:
            result[lib_key] = lib_info  # Fall back to library info
            unmatched_entries.append(lib_key)

    print(f"Matched {matched_count}/{len(library_dict)} library entries to disk files")
    if unmatched_entries and len(unmatched_entries) <= 10:
        print(f"Unmatched: {unmatched_entries[:10]}")

    return result


def load_library_paths(csv_path: str):
    """
    Load library with file paths and duration.
    Returns dict: (title, artist) -> {"path": file_path, "duration": duration_seconds}
    Assumes library.csv has columns: Artist, Title, Duration, and potentially FilePath or Location
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
            # Try common column names for duration
            duration_str = (
                row.get("Duration", "") or row.get("Length", "") or row.get("Time", "")
            ).strip()

            if title and artist:
                # If no path in CSV, construct a placeholder
                if not file_path:
                    file_path = f"{artist} - {title}.mp3"

                # Convert duration to seconds (handle "MM:SS" or seconds format)
                duration_seconds = 0
                if duration_str:
                    try:
                        if ":" in duration_str:
                            parts = duration_str.split(":")
                            duration_seconds = int(parts[0]) * 60 + int(parts[1])
                        else:
                            duration_seconds = int(duration_str)
                    except (ValueError, IndexError):
                        duration_seconds = 0

                library[(title, artist)] = {
                    "path": file_path,
                    "duration": duration_seconds,
                }

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


def load_unmatched_songs(csv_path: str):
    """
    Load unmatched library songs.
    Returns list of (library_title, library_artist)
    """
    unmatched = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("library_title", "").strip()
            artist = row.get("library_artist", "").strip()

            if title and artist:
                unmatched.append((title, artist))

    return unmatched


def create_m3u_playlist(tracks, output_path, playlist_name):
    """
    Create an .m3u playlist file with EXTINF metadata.

    Args:
        tracks: list of tuples (title, artist, duration, file_path)
        output_path: path to save the .m3u file
        playlist_name: name of the playlist
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#EXTENC: UTF-8\n")
        f.write(f"#PLAYLIST:{playlist_name}\n")

        for title, artist, duration, file_path in tracks:
            # Convert absolute path to relative path
            rel_path = os.path.relpath(file_path, os.path.dirname(output_path))
            # Normalize path separators for m3u format
            rel_path = rel_path.replace("\\", "/")

            # Format: #EXTINF:<duration>,<artist> - <title>
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")
            f.write(f"{rel_path}\n")

    print(f"Created playlist: {output_path} ({len(tracks)} tracks)")


def main():
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print("Loading matched songs mapping...")
    db_to_lib_mapping = load_matched_songs_mapping(matched_path)
    print(f"Loaded {len(db_to_lib_mapping)} song mappings")

    print("\nLoading library paths...")
    library = load_library_paths(library_path)
    print(f"Loaded {len(library)} library tracks")

    print("\nScanning music directory for actual files...")
    disk_files = load_music_files_from_disk(music_dir)

    if disk_files:
        print("Matching library entries to disk files...")
        library = match_library_to_disk(library, disk_files)
    else:
        print(
            "WARNING: No music files found on disk. Playlists may have invalid paths."
        )

    print("\nLoading clusters...")
    clusters = load_clusters(clusters_path)
    print(f"Loaded {len(clusters)} clusters")

    print("\nLoading isolated songs...")
    isolated_songs = load_isolated_songs(isolated_path)
    print(f"Loaded {len(isolated_songs)} isolated tracks")

    print("\nLoading unmatched songs...")
    unmatched_songs = load_unmatched_songs(unmatched_path)
    print(f"Loaded {len(unmatched_songs)} unmatched tracks")

    # Track statistics
    total_playlists = 0
    total_tracks_in_playlists = 0
    songs_not_found = []

    # Create playlists for each cluster
    print("\nCreating cluster playlists...")

    def sort_key(item):
        cid = item[0]
        # Handle mixed numeric/string cluster ids safely
        return (
            (0, int(cid)) if isinstance(cid, str) and cid.isdigit() else (1, str(cid))
        )

    for cluster_id, songs in sorted(clusters.items(), key=sort_key):
        tracks = []

        for db_title, db_artist in songs:
            # Map database song to library songs (may be multiple)
            lib_keys = db_to_lib_mapping.get((db_title, db_artist), [])

            if lib_keys:
                for lib_key in lib_keys:
                    if lib_key in library:
                        lib_title, lib_artist = lib_key
                        lib_info = library[lib_key]
                        tracks.append(
                            (
                                lib_title,
                                lib_artist,
                                lib_info["duration"],
                                lib_info["path"],
                            )
                        )
                    else:
                        songs_not_found.append(
                            (lib_key[0], lib_key[1], "cluster", cluster_id)
                        )
            else:
                songs_not_found.append((db_title, db_artist, "cluster", cluster_id))

        if tracks:
            playlist_path = os.path.join(output_dir, f"cluster_{cluster_id}.m3u")
            create_m3u_playlist(tracks, playlist_path, f"Cluster {cluster_id}")
            total_playlists += 1
            total_tracks_in_playlists += len(tracks)

    # Create playlist for isolated songs
    if isolated_songs or unmatched_songs:
        print("\nCreating isolated songs playlist...")
        tracks = []

        for db_title, db_artist in isolated_songs:
            # Map database song to library songs (may be multiple)
            lib_keys = db_to_lib_mapping.get((db_title, db_artist), [])

            if lib_keys:
                for lib_key in lib_keys:
                    if lib_key in library:
                        lib_title, lib_artist = lib_key
                        lib_info = library[lib_key]
                        tracks.append(
                            (
                                lib_title,
                                lib_artist,
                                lib_info["duration"],
                                lib_info["path"],
                            )
                        )
                    else:
                        songs_not_found.append(
                            (lib_key[0], lib_key[1], "isolated", "N/A")
                        )

        for lib_title, lib_artist in unmatched_songs:
            if (lib_title, lib_artist) in library:
                lib_info = library[(lib_title, lib_artist)]
                tracks.append(
                    (lib_title, lib_artist, lib_info["duration"], lib_info["path"])
                )
            else:
                songs_not_found.append((lib_title, lib_artist, "unmatched", "N/A"))

        if tracks:
            playlist_path = os.path.join(output_dir, "isolated_songs.m3u")
            create_m3u_playlist(tracks, playlist_path, "Isolated Songs")
            total_playlists += 1
            total_tracks_in_playlists += len(tracks)

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
