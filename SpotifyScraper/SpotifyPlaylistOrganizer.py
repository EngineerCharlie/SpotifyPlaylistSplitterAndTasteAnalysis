import SpotipyBootstrap as SpotipyBootstrap
import pandas as pd
import numpy as np
import networkx as nx
import time


def get_playlist_track_popularities(sp, playlist):

    def get_track_key(track):
        track_name = track["name"]
        track_artists = ", ".join(artist["name"] for artist in track["artists"])
        return (track_name, track_artists)

    track_set = set()
    track_popularity_dict = {}
    track_name_id_dict = {}
    track_id_name_dict = {}
    track_id_list = []

    results = sp.playlist_tracks(playlist)

    while results:
        for item in results["items"]:
            track = item["track"]
            track_key = get_track_key(track)
            track_id = track["id"]

            track_set.add(track_key)
            track_popularity_dict[track_id] = track["popularity"]
            track_name_id_dict[track_key] = track_id
            track_id_name_dict[track_id] = track_key
            track_id_list.append(track_id)
        results = sp.next(results) if results["next"] else None

    # Remove duplicates from the popularity dictionary
    if len(track_set) != len(track_popularity_dict):
        new_track_popularity_dict = {
            track_name_id_dict[track_key]: track_popularity_dict[
                track_name_id_dict[track_key]
            ]
            for track_key in track_set
        }

        # Identify and print removed tracks
        ids_removed = set(track_popularity_dict.keys()) - set(
            new_track_popularity_dict.keys()
        )
        for track_id in ids_removed:
            track_name, track_artists = track_id_name_dict[track_id]
            print(f"Removing track: {track_name} by {track_artists}")

        track_popularity_dict = new_track_popularity_dict

    if len(track_popularity_dict) == 1:
        raise Exception("Need more than 1 track to sort")

    return track_popularity_dict, track_id_list


def get_track_audio_features(
    sp: SpotipyBootstrap.spotipy.Spotify, track_popularity_dict: dict
):
    track_audio_features = []
    track_ids = []
    track_popularity = []

    while track_popularity_dict:
        # Pop up to 100 track IDs and their popularity from the dictionary
        track_slice = list(track_popularity_dict.keys())[:95]
        popularity_slice = [
            track_popularity_dict.pop(track_id) for track_id in track_slice
        ]

        # Fetch the audio features for these tracks
        result = sp.audio_features(track_slice)

        # Filter out any None results (which can happen if a track ID is invalid)
        valid_results = [
            (track, track_slice[i])
            for i, track in enumerate(result)
            if track is not None
        ]

        # Append the audio features, track IDs, and popularity to their respective lists
        track_audio_features.extend([track for track, track_id in valid_results])
        track_ids.extend([track_id for track, track_id in valid_results])
        track_popularity.extend(
            [popularity_slice[i] for i in range(len(valid_results))]
        )
    # Convert the list of dictionaries to a DataFrame
    df = pd.DataFrame(track_audio_features)

    # Add track IDs as the index
    df.index = track_ids

    # Add popularity as a new column
    df["popularity"] = track_popularity

    return df


def song_matching(track_audio_features: pd.DataFrame):
    track_ids = track_audio_features.index
    num_tracks = len(track_ids)
    WEIGHTING = {
        "danceability_dif": 6,
        "energy_dif": 20,
        "key_dif": 4,
        "loudness_dif": 10,
        "speechiness_dif": 4,
        "acousticness_dif": 10,
        "instrumentalness_dif": 5,
        "liveness_dif": 2,
        "valence_dif": 13,
        "tempo_dif": 7,
    }
    # Convert track features to NumPy arrays
    features_array = track_audio_features.drop(
        columns=[
            "popularity",
            "type",
            "id",
            "uri",
            "track_href",
            "analysis_url",
            "duration_ms",
            "time_signature",
            "key",
            "mode",
        ]
    ).values
    keys_array = track_audio_features[["key", "mode"]].values
    tempos_array = track_audio_features["tempo"].values
    # Initialize the matching matrix
    matching_matrix = np.zeros((num_tracks, num_tracks))

    # Compute differences
    for i in range(num_tracks):
        track_a_features = features_array[i]
        track_a_key = keys_array[i]
        track_a_tempo = tempos_array[i]

        # Broadcasting to compute differences
        features_diff = np.abs(features_array - track_a_features)
        keys_diff = np.array(
            [
                musical_key_compare(track_a_key, track_b_key)
                for track_b_key in keys_array
            ]
        )
        tempos_diff = np.array(
            [
                tempo_proportional_dif(track_a_tempo, track_b_tempo)
                for track_b_tempo in tempos_array
            ]
        )

        # Weighted differences
        weighted_differences = (
            WEIGHTING["danceability_dif"] * features_diff[:, 0]
            + WEIGHTING["energy_dif"] * features_diff[:, 1]
            + WEIGHTING["key_dif"] * keys_diff
            + WEIGHTING["loudness_dif"] * features_diff[:, 2]
            + WEIGHTING["speechiness_dif"] * features_diff[:, 3]
            + WEIGHTING["acousticness_dif"] * features_diff[:, 4]
            + WEIGHTING["instrumentalness_dif"] * features_diff[:, 5]
            + WEIGHTING["liveness_dif"] * features_diff[:, 6]
            + WEIGHTING["valence_dif"] * features_diff[:, 7]
            + WEIGHTING["tempo_dif"] * tempos_diff
        )
        # Update the matrix
        matching_matrix[i, :] = weighted_differences
        matching_matrix[:, i] = weighted_differences  # Symmetric matrix

    np.fill_diagonal(matching_matrix, np.inf)
    # Convert to DataFrame
    matching_df = pd.DataFrame(matching_matrix, index=track_ids, columns=track_ids)
    return matching_df


def musical_key_compare(track_a, track_b):
    # Unpack key and mode for both tracks
    key1, mode1 = track_a[0], track_a[1]
    key2, mode2 = track_b[0], track_b[1]

    # Check if modes are the same (Major or Minor)
    if key1 == -1 or key2 == -1:
        return 0.9
    if mode1 == mode2:
        # Calculate direct key difference
        key_difference = (key1 - key2) % 12
        if key_difference == 0:  # Same key
            return 0
        elif key_difference == 5 or key_difference == 7:  # Perfect 5th relationship
            return 0.1
        elif (
            key_difference == 2 or key_difference == 10
        ):  # Two steps in either direction
            return 0.4
        else:  # Three or more steps difference
            return 1.0

    # Check if modes are different (Major to Minor or vice versa)
    elif mode1 != mode2:
        key_difference = (key1 - key2) % 12
        # Check if the current track is major and the comparison track is minor (and vice versa)
        if (mode1 == 1 and (key1 - 3) % 12 == key2) or (
            mode1 == 0 and (key2 - 3) % 12 == key1
        ):
            return 0.1  # Major to relative minor (or vice versa)
        else:
            return 1.0

    return 1.0  # Default case if no conditions are met


def tempo_proportional_dif(track_a_tempo, track_b_tempo):
    # List of possible multiples and divisions by powers of 2
    multiples = [1, 2, 4, 8]
    min_tempo = min(track_a_tempo, track_b_tempo)
    max_tempo = max(track_a_tempo, track_b_tempo)

    # The smallest difference is the best match
    return (
        3
        * min(abs(max_tempo - (min_tempo * multiple)) for multiple in multiples)
        / max_tempo
    )


def solve_tsp(distance_matrix: pd.DataFrame):
    try:
        G = nx.from_numpy_array(distance_matrix)
        # Solve TSP using NetworkX's approximation algorithm
        tsp_path = nx.approximation.christofides(G)
        return tsp_path  # , tsp_length
    except nx.exception.NetworkXError as e:
        print(e)
        print(G)
        print(distance_matrix)


def update_playlist(
    sp: SpotipyBootstrap.spotipy.Spotify, playlist_id, old_tracks, new_tracks
):
    assert len(new_tracks) != 0
    while old_tracks:
        track_slice = []
        try:
            for i in range(50):
                track_slice.append(old_tracks.pop())

        except IndexError:
            pass
        sp.playlist_remove_all_occurrences_of_items(playlist_id, track_slice)
    while new_tracks:
        track_slice = []
        for i in range(min(50, len(new_tracks))):
            track_slice.append(new_tracks.pop())
        sp.playlist_add_items(playlist_id, track_slice)


def reorder_playlist(playlist_id: str):
    # Fetch tracks for playlist
    track_popularity_dict, original_tracks = get_playlist_track_popularities(
        SpotipyBootstrap.sp, playlist_id
    )
    audio_features_matrix = get_track_audio_features(
        SpotipyBootstrap.sp, track_popularity_dict
    )
    start_time = time.time()
    track_matching_matrix = song_matching(audio_features_matrix)
    track_ids = track_matching_matrix.index
    track_matching_matrix = track_matching_matrix.to_numpy()
    track_ordering = solve_tsp(track_matching_matrix)
    track_ordering = [track_ids[track_id] for track_id in track_ordering[:-1]]
    end_time = time.time()
    # Calculate and print the elapsed time
    elapsed_time = end_time - start_time
    print(f"New order calculated in {elapsed_time:.4f} seconds")
    print(track_ordering)
    playlist_backup_id = SpotipyBootstrap.sp.user_playlist_create(
        SpotipyBootstrap.SpotifySecrets.SPOTIFY_USERNAME, "backup"
    )["id"]
    update_playlist(SpotipyBootstrap.sp, playlist_backup_id, [], original_tracks.copy())
    update_playlist(SpotipyBootstrap.sp, playlist_id, original_tracks, track_ordering)
    SpotipyBootstrap.sp.user_playlist_unfollow(
        SpotipyBootstrap.SpotifySecrets.SPOTIFY_USERNAME, playlist_backup_id
    )


if __name__ == "__main__":
    reorder_playlist("3O4xCt4hBP0uDoQS5C1izu")
    # 300 song playlist 6Id3z1jonSXh0KNwjF2gBG
    # 13 song playlist 3Ilo6cyMtDAPt332MzqIAG
    # 3 song double playlist 5GJrAohQqT6afu6XHIwf3q
