import json, os, csv, re
from rapidfuzz import fuzz
from collections import defaultdict

base_dir = os.path.dirname(__file__)  # .../SpotifyPlaylistSplitter/PlaylistSplitter
filename = "spotify_playlists_data_1.json"
filename = "spotify_playlists_data_backup_2025_12_10.json"
json_path = os.path.join(base_dir, "..", "SpotifyScraper", filename)
json_path = os.path.abspath(json_path)
library_path = os.path.join(base_dir, "..", "data", "library.csv")
unmatched_path = os.path.join(base_dir, "..", "data", "unmatched_songs_1.csv")


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


def extract_unmatched_songs_csv(csv_path: str):
    """
    Extracts unique songs from unmatched_songs.csv structured like:

    library_title,library_artist

    Returns a set of (title, artist_string).
    """

    unique_songs = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            title = row.get("library_title", "").strip()
            artist_field = row.get("library_artist", "").strip()

            if not title or not artist_field:
                print("Skipping empty row:", title, artist_field)
                continue

            # Artists are comma-separated in unmatched_songs.csv
            artists = [a.strip() for a in artist_field.split(",") if a.strip()]
            artist_string = ",".join(artists)

            record = (title, artist_string)

            if record not in unique_songs:
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
    songs_extracted, songs_library, artist_thresh=80, title_thresh=80
):

    # ------------------------------------------------------------
    # PREPROCESS EXTRACTED SONGS
    # ------------------------------------------------------------
    extracted_tracks = []
    unique_artists = set()

    for title, artist_raw in songs_extracted:
        norm_title = normalize_text(title)
        norm_artists = tuple(
            sorted(
                [
                    na
                    for na in (
                        normalize_text(a.strip()) for a in re.split(r"[;,]", artist_raw)
                    )
                    if na  # filter empty normalized strings
                ]
            )
        )

        extracted_tracks.append(
            {
                "title": title,
                "artists": artist_raw,
                "norm_title": norm_title,
                "norm_artists": norm_artists,
            }
        )

        for a in norm_artists:
            if a:  # skip empty normalized artist
                unique_artists.add(a)

    unique_artists = list(unique_artists)
    print(f"Unique extracted artists: {len(unique_artists)}")

    # ------------------------------------------------------------
    # BUILD TRACKS BY ARTIST (PRIMARY SPEEDUP)
    # ------------------------------------------------------------
    tracks_by_artist = defaultdict(list)
    for track in extracted_tracks:
        for a in track["norm_artists"]:
            tracks_by_artist[a].append(track)

    # ------------------------------------------------------------
    # BUILD APPROX ARTIST INDEX FOR FAST-PASS BLOCKING
    # ------------------------------------------------------------
    artist_index = defaultdict(list)
    for a in unique_artists:
        if not a:
            continue  # skip empty
        key = (a[0], len(a) // 3)
        artist_index[key].append(a)

    # ------------------------------------------------------------
    # PRE-NORMALIZE LIBRARY SONGS
    # ------------------------------------------------------------
    library_norm = []
    for title, artist_raw in songs_library:
        nt = normalize_text(title)
        na = tuple(sorted([normalize_text(a.strip()) for a in artist_raw.split(",")]))
        library_norm.append(
            {
                "orig_title": title,
                "orig_artists": artist_raw,
                "norm_title": nt,
                "norm_artist_str": " ".join(na),
            }
        )

    matches = []
    unmatched = []

    # ------------------------------------------------------------
    # MAIN MATCHING LOOP
    # ------------------------------------------------------------
    for i, lib in enumerate(library_norm):
        if i % 25 == 0:
            print(f"Processing track {i}...")

        lib_artist_str = lib["norm_artist_str"]
        key = (lib_artist_str[0], len(lib_artist_str) // 3)

        # FAST PASS
        approx_candidates = artist_index.get(key, [])

        candidate_artists = []
        for ex_artist in approx_candidates:
            score = fuzz.token_sort_ratio(lib_artist_str, ex_artist)
            if score >= artist_thresh:
                candidate_artists.append((ex_artist, score))

        # SLOW FALLBACK ON FAIL → FULL SCAN
        if not candidate_artists:
            for ex_artist in unique_artists:
                score = fuzz.token_sort_ratio(lib_artist_str, ex_artist)
                if score >= artist_thresh:
                    candidate_artists.append((ex_artist, score))

        if not candidate_artists:
            unmatched.append((lib["orig_title"], lib["orig_artists"]))
            continue

        # ------------------------------------------------------------
        # TRACKS FROM CANDIDATE ARTISTS (FAST NOW)
        # ------------------------------------------------------------
        candidate_tracks = []
        for a, _ in candidate_artists:
            candidate_tracks.extend(tracks_by_artist[a])

        if not candidate_tracks:
            unmatched.append((lib["orig_title"], lib["orig_artists"]))
            continue

        # ------------------------------------------------------------
        # TITLE MATCHING
        # ------------------------------------------------------------
        best_match = None
        best_score = 0
        lib_title_norm = lib["norm_title"]

        for track in candidate_tracks:
            title_score = fuzz.token_sort_ratio(lib_title_norm, track["norm_title"])
            if title_score < title_thresh:
                continue

            artist_score = max(
                fuzz.token_sort_ratio(lib_artist_str, a) for a in track["norm_artists"]
            )

            combined = artist_score * title_score

            if combined > best_score:
                best_score = combined
                best_match = (
                    lib["orig_title"],
                    lib["orig_artists"],
                    track["title"],
                    track["artists"],
                    artist_score,
                    title_score,
                )

        if best_match:
            matches.append(best_match)
        else:
            unmatched.append((lib["orig_title"], lib["orig_artists"]))

    return matches, unmatched


if __name__ == "__main__":
    songs_extracted = extract_unique_songs_json(json_path)
    print(len(songs_extracted), "unique songs extracted from playlists.")
    # songs_library = extract_songs_from_csv(library_path)
    songs_library = extract_unmatched_songs_csv(unmatched_path)
    print(len(songs_library), "unique songs extracted from library.")
    matches, unmatched = fuzzy_match_songs(
        list(songs_extracted), list(songs_library), 80, 80
    )
    matched_path = os.path.join(base_dir, "..", "data", "matched_songs.csv")
    print("Matched tracks:", len(matches))
    with open(matched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "library_title",
                "library_artist",
                "extracted_title",
                "extracted_artist",
                "artist_score",
                "title_score",
            ]
        )

        for (
            lib_title,
            lib_artists,
            ext_title,
            ext_artists,
            artist_score,
            title_score,
        ) in matches:
            writer.writerow(
                [
                    lib_title,
                    lib_artists,
                    ext_title,
                    ext_artists,
                    artist_score,
                    title_score,
                ]
            )
    unmatched_path = os.path.join(base_dir, "..", "data", "unmatched_songs.csv")
    with open(unmatched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["library_title", "library_artist"])
        for title, artist in unmatched:
            writer.writerow([title, artist])

    # print(f"Exported unmatched songs to: {unmatched_path}")
    # print(f"Exported matched songs to: {matched_path}")
