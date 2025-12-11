import json, os, csv, re
from rapidfuzz import fuzz
from collections import defaultdict

base_dir = os.path.dirname(__file__)  # .../SpotifyPlaylistSplitter/PlaylistSplitter
filename = "spotify_playlists_data_1.json"
filename = "spotify_playlists_data_backup_2025_12_10.json"
json_path = os.path.join(base_dir, "..", "data", filename)
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


# ----------------------
# Normalization functions
# ----------------------


def normalize_title(title: str) -> str:
    """Normalize titles for better fuzzy matching."""
    s = title.lower()
    # Remove common versioning info
    s = re.sub(r"\(feat[^\)]*\)", "", s)
    s = re.sub(r"\(ft[^\)]*\)", "", s)
    s = re.sub(r"\(live.*?\)", "", s)
    s = re.sub(r"\(remaster(ed)?\)", "", s)
    s = re.sub(r"\(.*?mix.*?\)", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_artist(artist: str) -> str:
    """Normalize a single artist name."""
    s = artist.lower().strip()
    # Remove leading 'the '
    if s.startswith("the "):
        s = s[4:]
    # Remove periods
    s = s.replace(".", " ")
    # Remove any other non-alphanumeric characters
    s = re.sub(r"[^\w\s]", "", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def split_artists(artist_raw: str):
    """Split artist field into a set of normalized artist names."""
    # Split by commas, semicolons, &, feat.
    parts = re.split(r",|;|&|feat\.|ft\.", artist_raw, flags=re.I)
    return {normalize_artist(a) for a in parts if normalize_artist(a)}


# ----------------------
# Fuzzy matching function
# ----------------------


def fuzzy_match_songs(
    songs_extracted,
    songs_library,
    artist_weight=0.6,
    title_weight=0.4,
    threshold=80,
    artist_threshold=80,
    title_threshold=80,
    top_n=1,  # number of top matches to return per library track
):
    """
    Improved fuzzy matching between extracted songs and a library.

    Returns:
        matches: list of tuples (library_title, library_artist, extracted_title, extracted_artist, artist_score, title_score, combined_score)
        unmatched: list of (library_title, library_artist)
    """
    # Preprocess extracted songs
    extracted_tracks = []
    tracks_by_artist = defaultdict(list)

    for title, artist_raw in songs_extracted:
        norm_title = normalize_title(title)
        artist_set = split_artists(artist_raw)
        if not artist_set:
            continue
        extracted_tracks.append(
            {
                "title": title,
                "artists": artist_raw,
                "norm_title": norm_title,
                "artist_set": artist_set,
            }
        )
        for a in artist_set:
            tracks_by_artist[a].append(extracted_tracks[-1])

    matches = []
    unmatched = []

    for num, (lib_title, lib_artist_raw) in enumerate(songs_library):
        if num % 25 == 0:
            print("Processing ", num + 1, "for library track:", lib_title)
        norm_lib_title = normalize_title(lib_title)
        lib_artist_set = split_artists(lib_artist_raw)
        if not lib_artist_set:
            unmatched.append((lib_title, lib_artist_raw))
            continue

        # Candidate tracks: any extracted track sharing at least one artist
        candidate_tracks = []
        for a in lib_artist_set:
            candidate_tracks.extend(tracks_by_artist.get(a, []))

        if not candidate_tracks:
            unmatched.append((lib_title, lib_artist_raw))
            continue

        # Compute scores
        scored_candidates = []
        for track in candidate_tracks:
            # Title score
            title_score = fuzz.token_sort_ratio(norm_lib_title, track["norm_title"])
            # Artist score
            artist_score = max(
                fuzz.token_sort_ratio(
                    " ".join(lib_artist_set), " ".join(track["artist_set"])
                ),
                fuzz.token_sort_ratio(
                    ",".join(lib_artist_set), ",".join(track["artist_set"])
                ),
            )

            # Fallbacks using token_set_ratio if below threshold
            if artist_score < artist_threshold:
                artist_score = max(
                    fuzz.token_set_ratio(
                        " ".join(lib_artist_set), " ".join(track["artist_set"])
                    ),
                    fuzz.token_set_ratio(
                        ",".join(lib_artist_set), ",".join(track["artist_set"])
                    ),
                )
            if artist_score < artist_threshold:
                # Fallback: token overlap
                lib_tokens = set(" ".join(lib_artist_set).split())
                track_tokens = set(" ".join(track["artist_set"]).split())
                overlap = len(lib_tokens & track_tokens) / max(len(lib_tokens), 1) * 100
                artist_score = max(artist_score, overlap)
            if title_score < title_threshold:
                title_score = fuzz.token_set_ratio(norm_lib_title, track["norm_title"])

            combined_score = artist_weight * artist_score + title_weight * title_score
            scored_candidates.append(
                {
                    "track": track,
                    "artist_score": artist_score,
                    "title_score": title_score,
                    "combined_score": combined_score,
                }
            )

        # Keep top N matches above threshold
        scored_candidates = [
            c
            for c in scored_candidates
            if c["combined_score"] >= threshold
            and c["artist_score"] >= artist_threshold
            and c["title_score"] >= title_threshold
        ]
        if not scored_candidates:
            unmatched.append((lib_title, lib_artist_raw))
            continue

        scored_candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        for c in scored_candidates[:top_n]:
            matches.append(
                (
                    lib_title,
                    lib_artist_raw,
                    c["track"]["title"],
                    c["track"]["artists"],
                    round(c["artist_score"], 2),
                    round(c["title_score"], 2),
                    round(c["combined_score"], 2),
                )
            )

    return matches, unmatched


if __name__ == "__main__":
    # songs_library = extract_songs_from_csv(library_path)
    songs_library = extract_unmatched_songs_csv(unmatched_path)
    print(len(songs_library), "unique songs extracted from library.")

    songs_extracted = extract_unique_songs_json(json_path)
    print(len(songs_extracted), "unique songs extracted from playlists.")
    matches, unmatched = fuzzy_match_songs(
        list(songs_extracted), list(songs_library), 0.6, 0.4, 80, 80, 80
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
            combined_score,
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
