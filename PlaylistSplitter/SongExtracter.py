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
                continue

            # Split multiple artists by semicolon, normalize whitespace
            artists = [a.strip() for a in artist_field.split(";")]

            for artist in artists:
                unique_songs.add((title, artist))

    return unique_songs


# ----------------------
# Normalization functions
# ----------------------


def normalize_text(s: str) -> str:
    s = s.lower()
    # Remove punctuation
    s = re.sub(r"[^\w\s]", "", s)
    # Collapse spaces
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_artists(artists_raw: str) -> list:
    # Split on ',' or ';'
    parts = re.split(r"[;,]", artists_raw)
    return [normalize_text(p) for p in parts if p.strip()]


def canonical_key(title: str, artists: list) -> tuple:
    norm_title = normalize_text(title)
    norm_artists = sorted(normalize_artists(",".join(artists)))
    return (norm_title, tuple(norm_artists))


# ----------------------
# Fuzzy matching function
# ----------------------


def fuzzy_match_songs(
    playlist_tracks, library_tracks, title_thresh=90, artist_thresh=90
):
    """
    Match playlist_tracks to library_tracks using fuzzy string matching.

    playlist_tracks & library_tracks: list of (title, artist_raw) tuples
    title_thresh & artist_thresh: minimum fuzzy ratio for match
    """
    matches = []
    unmatched_playlist = []

    # Pre-normalize library for faster matching
    library_norm = []
    for title, artist_raw in library_tracks:
        artists = [a.strip() for a in re.split(r"[;,]", artist_raw)]
        norm_title = normalize_text(title)
        norm_artists = sorted(normalize_artists(",".join(artists)))
        library_norm.append(
            {
                "original": (title, artist_raw),
                "title": norm_title,
                "artists": norm_artists,
            }
        )

    for p_title, p_artist_raw in playlist_tracks:
        p_artists = [a.strip() for a in p_artist_raw.split(",")]
        p_norm_title = normalize_text(p_title)
        p_norm_artists = sorted(normalize_artists(",".join(p_artists)))

        best_match = None
        best_score = 0

        for lib in library_norm:
            # Compare title
            title_score = fuzz.ratio(p_norm_title, lib["title"])
            # Compare artists: take average fuzzy ratio across all artists
            artist_scores = []
            for pa in p_norm_artists:
                # Match against best library artist
                a_score = max(fuzz.ratio(pa, la) for la in lib["artists"])
                artist_scores.append(a_score)
            if artist_scores:
                artist_score = sum(artist_scores) / len(artist_scores)
            else:
                artist_score = 0

            # Combined score: simple min threshold
            if title_score >= title_thresh and artist_score >= artist_thresh:
                combined_score = (title_score + artist_score) / 2
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = lib["original"]

        if best_match:
            matches.append(((p_title, p_artist_raw), best_match))
        else:
            unmatched_playlist.append((p_title, p_artist_raw))

    return matches, unmatched_playlist


if __name__ == "__main__":
    songs_extracted = extract_unique_songs_json(json_path)
    print(len(songs_extracted), "unique songs extracted from playlists.")
    # songs_library = extract_songs_from_csv(library_path)
    # matches, unmatched = fuzzy_match_songs(list(songs_extracted), list(songs_library))

    # print("Matched tracks:", len(matches))
    # for playlist_song, library_song in matches:
    #     print("Playlist:", playlist_song, "-> Library:", library_song)

    # # print("\nUnmatched playlist tracks:")
    # # for track in unmatched:
    # #     print(track)
