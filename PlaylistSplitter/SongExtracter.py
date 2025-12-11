import json, os, csv, re
from rapidfuzz import fuzz, process

base_dir = os.path.dirname(__file__)  # .../SpotifyPlaylistSplitter/PlaylistSplitter
filename = "spotify_playlists_data_1.json"
# filename = "spotify_playlists_data_backup_2025_12_10.json"
json_path = os.path.join(base_dir, "..", "SpotifyScraper", filename)
json_path = os.path.abspath(json_path)
library_path = os.path.join(base_dir, "..", "data", "library.csv")


def extract_unique_songs_json(json_path: str):
    """
    Extracts unique songs from a JSON file of playlists.

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
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    unique_songs = set()

    for playlist in data:
        tracks = playlist.get("tracks", [])
        for track in tracks:
            if isinstance(track, list) and len(track) == 2:
                title, artist = track
                unique_songs.add((title, artist))

    return unique_songs


def extract_songs_from_csv(csv_path: str):
    """
    Extracts unique songs from a CSV structured like:

    Artist,Title
    "2Pac; Big Syke","All Eyez on Me"

    Returns a set of (title, artist) tuples.
    """

    unique_songs = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            artist_field = row.get("Artist", "").strip()
            title = row.get("Title", "").strip()

            if not title or not artist_field:
                print(title, artist_field)
                continue

            # Split multiple artists by semicolon, normalize whitespace
            artists = [a.strip() for a in artist_field.split(";")]
            artist_string = ",".join(artists)

            record = (title, artist_string)

            if record in unique_songs:
                # print(f"Duplicate='{title}', '{artist_string}'")
                pass
            else:
                unique_songs.add(record)

    return unique_songs


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ----------------------
# Fuzzy matching function
# ----------------------


def fuzzy_match_songs(
    songs_extracted, songs_library, title_thresh=90, artist_thresh=90
):
    # library_tracks: list of (title, artist_raw)
    library_index = {}

    for title, artist_raw in songs_extracted:
        norm_title = normalize_text(title)
        norm_artists = tuple(
            sorted([normalize_text(a.strip()) for a in re.split(r"[;,]", artist_raw)])
        )

        # Use normalized title as key
        if norm_title not in library_index:
            library_index[norm_title] = []

        library_index[norm_title].append(
            {"title": title, "artists": artist_raw, "norm_artists": norm_artists}
        )

    matches = []
    unmatched_playlist = []

    for p_title, p_artist_raw in songs_library:
        norm_p_title = normalize_text(p_title)
        norm_p_artists = tuple(
            sorted([normalize_text(a.strip()) for a in p_artist_raw.split(",")])
        )

        # Get candidate library tracks (exact title match)
        candidates = library_index.get(norm_p_title, [])

        best_match = None
        best_score = 0

        for lib in candidates:
            # Fuzzy artist match
            artist_score = fuzz.token_sort_ratio(
                " ".join(norm_p_artists), " ".join(lib["norm_artists"])
            )
            if artist_score > best_score:
                best_score = artist_score
                best_match = (p_title, p_artist_raw, lib["title"], lib["artists"])

        if best_match and best_score >= 90:  # threshold adjustable
            matches.append(best_match)
        else:
            unmatched_playlist.append((p_title, p_artist_raw))
    return matches, unmatched_playlist


if __name__ == "__main__":
    songs_extracted = extract_unique_songs_json(json_path)
    print(len(songs_extracted), "unique songs extracted from playlists.")
    songs_library = extract_songs_from_csv(library_path)
    print(len(songs_library), "unique songs extracted from library.")
    matches, unmatched = fuzzy_match_songs(list(songs_extracted), list(songs_library))

    print("Matched tracks:", len(matches))
    print(unmatched)
    # for playlist_song, library_song in matches:
    #     print("Playlist:", playlist_song, "-> Library:", library_song)

    # # print("\nUnmatched playlist tracks:")
    # # for track in unmatched:
    # #     print(track)
