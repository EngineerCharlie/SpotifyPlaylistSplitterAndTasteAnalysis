import json, os, csv, re
from rapidfuzz import fuzz
from collections import defaultdict

base_dir = os.path.dirname(__file__)  # .../SpotifyPlaylistSplitter/PlaylistSplitter
filename = "spotify_playlists_data_1.json"
filename = "spotify_playlists_data_backup_2025_12_10.json"
library_path = os.path.join(base_dir, "..", "data", "library.csv")
unmatched_path = os.path.join(base_dir, "..", "data", "unmatched_songs_1.csv")
json_path = os.path.join(base_dir, "..", "data", filename)

json_path = os.path.abspath(json_path)


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
    s = title.lower()
    s = re.sub(r"\(feat[^\)]*\)", "", s)
    s = re.sub(r"\(ft[^\)]*\)", "", s)
    s = re.sub(r"\(live.*?\)", "", s)
    s = re.sub(r"\(remaster(ed)?\)", "", s)
    s = re.sub(r"\(.*?mix.*?\)", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_artist(a: str) -> str:
    s = a.lower().strip()
    if s.startswith("the "):
        s = s[4:]
    s = s.replace(".", " ")
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def split_artists(s: str):
    parts = re.split(r",|;|&|feat\.|ft\.", s, flags=re.I)
    out = {normalize_artist(p) for p in parts if normalize_artist(p)}
    return out


def preprocess_tracks(songs):
    processed = []
    index_by_title = defaultdict(list)
    index_by_artist = defaultdict(list)

    for title, artist_raw in songs:
        norm_title = normalize_title(title)
        artist_set = split_artists(artist_raw)
        if not artist_set:
            continue

        item = {
            "title": title,
            "artists_raw": artist_raw,
            "norm_title": norm_title,
            "artist_set": artist_set,
        }
        processed.append(item)

        index_by_title[norm_title].append(item)
        for a in artist_set:
            index_by_artist[a].append(item)

    return processed, index_by_title, index_by_artist


# ----------------------
# Fuzzy matching function
# ----------------------


def match_songs_cascaded(library, database, threshold_title=85, threshold_artist=85):
    # ---------- Preprocessing ----------
    lib, lib_by_title, lib_by_artist = preprocess_tracks(library)
    ext, db_by_title, db_by_artist = preprocess_tracks(database)

    matched = []
    unmatched = set((t["title"], t["artists_raw"]) for t in lib)

    # Helper to record a match
    def record(lib_item, db_item, artist_score, title_score):
        matched.append(
            (
                lib_item["title"],
                lib_item["artists_raw"],
                db_item["title"],
                db_item["artists_raw"],
                round(artist_score, 2),
                round(title_score, 2),
                round(artist_score + title_score, 2),
            )
        )
        unmatched.discard((lib_item["title"], lib_item["artists_raw"]))

    # -------------------------------------------------------------------
    # STAGE 1 — HARD 1:1 MATCH: normalized title AND exact artist sets
    # -------------------------------------------------------------------
    for lib_item in lib:
        if (lib_item["title"], lib_item["artists_raw"]) not in unmatched:
            continue

        candidates = db_by_title.get(lib_item["norm_title"], [])
        for db_item in candidates:
            if lib_item["artist_set"] == db_item["artist_set"]:
                record(lib_item, db_item, 100, 100)
                break
    print(f"After Stage 1, matched: {len(matched)}, unmatched: {len(unmatched)}")

    # -------------------------------------------------------------------
    # STAGE 2 — HARD ARTIST MATCH + FUZZY TITLE
    # -------------------------------------------------------------------
    for lib_item in lib:
        if (lib_item["title"], lib_item["artists_raw"]) not in unmatched:
            continue

        # exact artist-set match
        artist_string = " ".join(sorted(lib_item["artist_set"]))

        for a in lib_item["artist_set"]:
            for db_item in db_by_artist.get(a, []):
                if db_item["artist_set"] == lib_item["artist_set"]:
                    title_score = fuzz.token_sort_ratio(
                        lib_item["norm_title"], db_item["norm_title"]
                    )
                    if title_score >= threshold_title:
                        record(lib_item, db_item, 100, title_score)
                        break
    print(f"After Stage 2, matched: {len(matched)}, unmatched: {len(unmatched)}")

    # -------------------------------------------------------------------
    # STAGE 3 — HARD TITLE MATCH + FUZZY ARTIST
    # -------------------------------------------------------------------
    for lib_item in lib:
        if (lib_item["title"], lib_item["artists_raw"]) not in unmatched:
            continue

        candidates = db_by_title.get(lib_item["norm_title"], [])
        for db_item in candidates:
            artist_score = fuzz.token_sort_ratio(
                " ".join(lib_item["artist_set"]), " ".join(db_item["artist_set"])
            )
            if artist_score >= threshold_artist:
                record(lib_item, db_item, artist_score, 100)
                break
    print(f"After Stage 3, matched: {len(matched)}, unmatched: {len(unmatched)}")

    # ----------------------------
    # STAGE 4 — FULL FUZZY (ARTIST + TITLE) - REAL FUZZY
    # ----------------------------

    # Prepare artist key list and a cheap blocking index to reduce comparisons
    db_artist_keys = list(db_by_artist.keys())
    db_artist_index = defaultdict(list)
    for k in db_artist_keys:
        if not k:
            continue
        key = (k[0], len(k) // 3)  # first char + length bucket
        db_artist_index[key].append(k)
    DEBUG = True  # overall stage debug
    DEBUG_VERBOSE = False  # enable only if you want per-key noisy logs
    DEBUG_EVERY = 1  # progress indicator frequency


    # Main full-fuzzy loop
    for num, lib_item in enumerate(lib):
        # Progress summary
        if DEBUG and (num % DEBUG_EVERY == 0):
            print(
                f"[Stage 4] Processing {num+1}/{len(lib)} "
                f"(matched={len(matched)}, unmatched={len(unmatched)})"
            )

        if (lib_item["title"], lib_item["artists_raw"]) not in unmatched:
            continue

        best = None

        lib_artist_str = " ".join(sorted(lib_item["artist_set"]))

        # Cheap block first
        block_key = (
            lib_artist_str[0] if lib_artist_str else "",
            len(lib_artist_str) // 3,
        )
        candidate_artist_keys = db_artist_index.get(block_key, None)

        # If block produced nothing, use full list
        block_used = candidate_artist_keys is not None and len(candidate_artist_keys) > 0
        if not block_used:
            candidate_artist_keys = db_artist_keys

        if DEBUG:
            print(
                f"[Stage 4] '{lib_item['title']}' by '{lib_item['artists_raw']}' | "
                f"block_used={block_used} | candidate_keys={len(candidate_artist_keys)}"
            )

        # Count how many artist keys survive fuzzy artist threshold
        artist_candidates = 0

        # Evaluate fuzzy artist matches among candidate artist keys
        for artist_key in candidate_artist_keys:
            artist_score = fuzz.token_set_ratio(lib_artist_str, artist_key)

            if DEBUG_VERBOSE:
                print(f"    artist_key='{artist_key}' => artist_score={artist_score}")

            if artist_score < threshold_artist:
                continue

            artist_candidates += 1

            # For any artist_key that passes, scan db items under key
            for db_item in db_by_artist.get(artist_key, []):
                title_score = fuzz.token_set_ratio(
                    lib_item["norm_title"], db_item["norm_title"]
                )

                if DEBUG_VERBOSE:
                    print(
                        f"        db_item='{db_item['title']}' => title_score={title_score}"
                    )

                if title_score < threshold_title:
                    continue

                total = artist_score + title_score
                if best is None or total > best["total"]:
                    best = {
                        "lib_item": lib_item,
                        "db_item": db_item,
                        "artist_score": round(artist_score, 2),
                        "title_score": round(title_score, 2),
                        "total": total,
                    }

        if DEBUG:
            print(
                f"[Stage 4] Artist candidates after threshold: {artist_candidates} "
                f"(block_used={block_used})"
            )

        # If nothing matched, global fallback
        if best is None:
            if DEBUG:
                print("[Stage 4] No match from block. Running global fallback scan.")

            for artist_key in db_artist_keys:
                artist_score = fuzz.token_set_ratio(lib_artist_str, artist_key)
                if artist_score < threshold_artist:
                    continue

                for db_item in db_by_artist.get(artist_key, []):
                    title_score = fuzz.token_set_ratio(
                        lib_item["norm_title"], db_item["norm_title"]
                    )
                    if title_score < threshold_title:
                        continue

                    total = artist_score + title_score
                    if best is None or total > best["total"]:
                        best = {
                            "lib_item": lib_item,
                            "db_item": db_item,
                            "artist_score": round(artist_score, 2),
                            "title_score": round(title_score, 2),
                            "total": total,
                        }

        # Record best if found
        if best:
            if DEBUG:
                print(
                    f"[Stage 4] MATCH FOUND: "
                    f"{best['lib_item']['title']}  →  {best['db_item']['title']} "
                    f"(artist={best['artist_score']}, title={best['title_score']})"
                )

            record(
                best["lib_item"],
                best["db_item"],
                best["artist_score"],
                best["title_score"],
            )
        else:
            if DEBUG:
                print(
                    f"[Stage 4] NO MATCH FOUND for {lib_item['title']} / {lib_item['artists_raw']}"
                )

    return matched, list(unmatched)


if __name__ == "__main__":
    # songs_library = extract_songs_from_csv(library_path)
    songs_library = extract_unmatched_songs_csv(unmatched_path)
    print(len(songs_library), "unique songs extracted from library.")

    songs_db = extract_unique_songs_json(json_path)
    print(len(songs_db), "unique songs extracted from playlists.")
    matches, unmatched = match_songs_cascaded(
        list(songs_library),
        list(songs_db),
        threshold_title=85,
        threshold_artist=85,
    )
    matched_path = os.path.join(base_dir, "..", "data", "matched_songs.csv")
    print("Matched tracks:", len(matches))

    with open(matched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "library_title",
                "library_artist",
                "database_title",
                "database_artist",
                "artist_score",
                "title_score",
            ]
        )

        for m in matches:
            print(m)
            writer.writerow([m[0], m[1], m[2], m[3], m[4], m[5]])

    # Unmatched writer remains the same
    unmatched_path = os.path.join(base_dir, "..", "data", "unmatched_songs.csv")

    with open(unmatched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["library_title", "library_artist"])
        for title, artist in unmatched:
            writer.writerow([title, artist])

    # print(f"Exported unmatched songs to: {unmatched_path}")
    # print(f"Exported matched songs to: {matched_path}")
