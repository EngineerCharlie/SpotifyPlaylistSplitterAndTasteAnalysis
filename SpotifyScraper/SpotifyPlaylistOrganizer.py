import SpotipyBootstrap as SpotipyBootstrap
import pandas as pd
import numpy as np
import networkx as nx
import time


# Function to get all tracks in a playlist
def get_playlist_track_popularities(sp, playlist):

    def get_track_key(track):
        track_name = track["name"]
        track_artists = ", ".join(artist["name"] for artist in track["artists"])
        return (track_name, track_artists)

    track_set = set()
    track_popularity_dict, track_name_id_dict, track_id_name_dict = {}, {}, {}

    results = sp.playlist_tracks(playlist)
    track_set.update([get_track_key(item["track"]) for item in results["items"]])
    track_popularity_dict.update(
        {item["track"]["id"]: item["track"]["popularity"] for item in results["items"]}
    )
    track_name_id_dict.update(
        {get_track_key(item["track"]): item["track"]["id"] for item in results["items"]}
    )
    track_id_name_dict.update(
        {item["track"]["id"]: get_track_key(item["track"]) for item in results["items"]}
    )
    while results["next"]:
        results = sp.next(results)
        track_popularity_dict.update(
            {
                item["track"]["id"]: item["track"]["popularity"]
                for item in results["items"]
            }
        )
        track_set.update([get_track_key(item["track"]) for item in results["items"]])
        track_name_id_dict.update(
            {
                get_track_key(item["track"]): item["track"]["id"]
                for item in results["items"]
            }
        )
        track_id_name_dict.update(
            {
                item["track"]["id"]: get_track_key(item["track"])
                for item in results["items"]
            }
        )
    if len(track_set) != track_popularity_dict:
        new_track_popularity_dict = {
            track_name_id_dict[track_key]: track_popularity_dict[
                track_name_id_dict[track_key]
            ]
            for track_key in track_set
        }
        ids_removed = set(track_popularity_dict.keys()) - set(
            new_track_popularity_dict.keys()
        )
        for id in ids_removed:
            print(track_id_name_dict[id])
        track_popularity_dict = new_track_popularity_dict
    if len(track_popularity_dict) == 1:
        raise Exception("Need more than 1  track to sort")
    return track_popularity_dict


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


def update_playlist(sp: SpotipyBootstrap.spotipy.Spotify, playlist_id, old_tracks, new_tracks):
    sp.playlist_remove_all_occurrences_of_items(playlist_id,old_tracks)
    while new_tracks:
        track_slice = []
        try:
            for i in range(50):
                track_slice.append(new_tracks.pop())
        except KeyError:
            pass
        sp.playlist_add_items(playlist_id, track_slice)



def reorder_playlist(playlist_id: str):
    # Fetch tracks for playlist
    track_popularity_dict = get_playlist_track_popularities(
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
    track_ordering = [track_ids[track_id] for track_id in track_ordering]
    end_time = time.time()
    # Calculate and print the elapsed time
    elapsed_time = end_time - start_time
    print(f"New order calculated in {elapsed_time:.4f} seconds")
    print(track_ordering[:-1])


if __name__ == "__main__":
    reorder_playlist("3Ilo6cyMtDAPt332MzqIAG")
    # 300 song playlist 6Id3z1jonSXh0KNwjF2gBG
    # 13 song playlist 3Ilo6cyMtDAPt332MzqIAG
    # 2 song double playlist 5GJrAohQqT6afu6XHIwf3q

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
track_popularity_dict = {
    "1pYPgA8XdHFQS15HPB41MH": 39,
    "5MyQwsO0ktOmdRxg9bmFeW": 23,
    "2fmXnPfzguSp3zKDibCBgv": 48,
    "0nN2D5xwVtLrgUw0TIQ5CI": 43,
    "6jY7UcNWda03nyJ5XiqlYt": 39,
    "5IIybI1oiOCY3DRUrpQ7zA": 0,
    "2zQl59dZMzwhrmeSBEgiXY": 52,
    "6wnziKyjH3rNyzP6H4ziO2": 0,
    "1EWPMNHfdVNJwBpG9BcxXB": 26,
    "1YQWosTIljIvxAgHWTp7KP": 68,
    "771I4XsOUGOeuIdeVh0IsR": 22,
    "2VUo8O3ymKRYNgj97ZG2kM": 50,
    "5xRP5iyVdGglqlY4Vcjhkx": 60,
}

track_audio_features = [
    {
        "danceability": 0.454,
        "energy": 0.26,
        "key": 8,
        "loudness": -13.193,
        "mode": 0,
        "speechiness": 0.0401,
        "acousticness": 0.539,
        "instrumentalness": 0.00078,
        "liveness": 0.0675,
        "valence": 0.598,
        "tempo": 174.322,
        "type": "audio_features",
        "id": "1YQWosTIljIvxAgHWTp7KP",
        "uri": "spotify:track:1YQWosTIljIvxAgHWTp7KP",
        "track_href": "https://api.spotify.com/v1/tracks/1YQWosTIljIvxAgHWTp7KP",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/1YQWosTIljIvxAgHWTp7KP",
        "duration_ms": 324133,
        "time_signature": 5,
    },
    {
        "danceability": 0.584,
        "energy": 0.0789,
        "key": 0,
        "loudness": -12.905,
        "mode": 1,
        "speechiness": 0.051,
        "acousticness": 0.884,
        "instrumentalness": 0.00705,
        "liveness": 0.0876,
        "valence": 0.319,
        "tempo": 70.886,
        "type": "audio_features",
        "id": "5IIybI1oiOCY3DRUrpQ7zA",
        "uri": "spotify:track:5IIybI1oiOCY3DRUrpQ7zA",
        "track_href": "https://api.spotify.com/v1/tracks/5IIybI1oiOCY3DRUrpQ7zA",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/5IIybI1oiOCY3DRUrpQ7zA",
        "duration_ms": 206827,
        "time_signature": 4,
    },
    {
        "danceability": 0.724,
        "energy": 0.414,
        "key": 1,
        "loudness": -11.19,
        "mode": 1,
        "speechiness": 0.0588,
        "acousticness": 0.262,
        "instrumentalness": 0.111,
        "liveness": 0.0785,
        "valence": 0.719,
        "tempo": 146.939,
        "type": "audio_features",
        "id": "2zQl59dZMzwhrmeSBEgiXY",
        "uri": "spotify:track:2zQl59dZMzwhrmeSBEgiXY",
        "track_href": "https://api.spotify.com/v1/tracks/2zQl59dZMzwhrmeSBEgiXY",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/2zQl59dZMzwhrmeSBEgiXY",
        "duration_ms": 388960,
        "time_signature": 4,
    },
    {
        "danceability": 0.439,
        "energy": 0.543,
        "key": 11,
        "loudness": -13.35,
        "mode": 0,
        "speechiness": 0.0975,
        "acousticness": 0.654,
        "instrumentalness": 9.79e-06,
        "liveness": 0.0937,
        "valence": 0.671,
        "tempo": 146.704,
        "type": "audio_features",
        "id": "5xRP5iyVdGglqlY4Vcjhkx",
        "uri": "spotify:track:5xRP5iyVdGglqlY4Vcjhkx",
        "track_href": "https://api.spotify.com/v1/tracks/5xRP5iyVdGglqlY4Vcjhkx",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/5xRP5iyVdGglqlY4Vcjhkx",
        "duration_ms": 622000,
        "time_signature": 4,
    },
    {
        "danceability": 0.734,
        "energy": 0.64,
        "key": 5,
        "loudness": -8.471,
        "mode": 0,
        "speechiness": 0.0661,
        "acousticness": 0.00606,
        "instrumentalness": 0.37,
        "liveness": 0.0602,
        "valence": 0.868,
        "tempo": 103.812,
        "type": "audio_features",
        "id": "2fmXnPfzguSp3zKDibCBgv",
        "uri": "spotify:track:2fmXnPfzguSp3zKDibCBgv",
        "track_href": "https://api.spotify.com/v1/tracks/2fmXnPfzguSp3zKDibCBgv",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/2fmXnPfzguSp3zKDibCBgv",
        "duration_ms": 541827,
        "time_signature": 4,
    },
    {
        "danceability": 0.327,
        "energy": 0.372,
        "key": 3,
        "loudness": -13.696,
        "mode": 1,
        "speechiness": 0.0542,
        "acousticness": 0.865,
        "instrumentalness": 0.835,
        "liveness": 0.153,
        "valence": 0.38,
        "tempo": 66.036,
        "type": "audio_features",
        "id": "1EWPMNHfdVNJwBpG9BcxXB",
        "uri": "spotify:track:1EWPMNHfdVNJwBpG9BcxXB",
        "track_href": "https://api.spotify.com/v1/tracks/1EWPMNHfdVNJwBpG9BcxXB",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/1EWPMNHfdVNJwBpG9BcxXB",
        "duration_ms": 264933,
        "time_signature": 4,
    },
    {
        "danceability": 0.766,
        "energy": 0.381,
        "key": 10,
        "loudness": -14.456,
        "mode": 0,
        "speechiness": 0.0805,
        "acousticness": 0.18,
        "instrumentalness": 0.0844,
        "liveness": 0.48,
        "valence": 0.634,
        "tempo": 98.862,
        "type": "audio_features",
        "id": "0nN2D5xwVtLrgUw0TIQ5CI",
        "uri": "spotify:track:0nN2D5xwVtLrgUw0TIQ5CI",
        "track_href": "https://api.spotify.com/v1/tracks/0nN2D5xwVtLrgUw0TIQ5CI",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/0nN2D5xwVtLrgUw0TIQ5CI",
        "duration_ms": 452573,
        "time_signature": 4,
    },
    {
        "danceability": 0.591,
        "energy": 0.991,
        "key": 6,
        "loudness": -4.148,
        "mode": 1,
        "speechiness": 0.111,
        "acousticness": 0.00261,
        "instrumentalness": 0.756,
        "liveness": 0.0567,
        "valence": 0.505,
        "tempo": 142.995,
        "type": "audio_features",
        "id": "6wnziKyjH3rNyzP6H4ziO2",
        "uri": "spotify:track:6wnziKyjH3rNyzP6H4ziO2",
        "track_href": "https://api.spotify.com/v1/tracks/6wnziKyjH3rNyzP6H4ziO2",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/6wnziKyjH3rNyzP6H4ziO2",
        "duration_ms": 192493,
        "time_signature": 4,
    },
    {
        "danceability": 0.65,
        "energy": 0.496,
        "key": 7,
        "loudness": -13.869,
        "mode": 1,
        "speechiness": 0.115,
        "acousticness": 0.0723,
        "instrumentalness": 0.88,
        "liveness": 0.119,
        "valence": 0.615,
        "tempo": 116.868,
        "type": "audio_features",
        "id": "2VUo8O3ymKRYNgj97ZG2kM",
        "uri": "spotify:track:2VUo8O3ymKRYNgj97ZG2kM",
        "track_href": "https://api.spotify.com/v1/tracks/2VUo8O3ymKRYNgj97ZG2kM",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/2VUo8O3ymKRYNgj97ZG2kM",
        "duration_ms": 119867,
        "time_signature": 4,
    },
    {
        "danceability": 0.743,
        "energy": 0.352,
        "key": 9,
        "loudness": -17.225,
        "mode": 0,
        "speechiness": 0.061,
        "acousticness": 0.146,
        "instrumentalness": 0.104,
        "liveness": 0.0585,
        "valence": 0.722,
        "tempo": 108.785,
        "type": "audio_features",
        "id": "6jY7UcNWda03nyJ5XiqlYt",
        "uri": "spotify:track:6jY7UcNWda03nyJ5XiqlYt",
        "track_href": "https://api.spotify.com/v1/tracks/6jY7UcNWda03nyJ5XiqlYt",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/6jY7UcNWda03nyJ5XiqlYt",
        "duration_ms": 350600,
        "time_signature": 4,
    },
    {
        "danceability": 0.628,
        "energy": 0.429,
        "key": 7,
        "loudness": -8.772,
        "mode": 0,
        "speechiness": 0.0454,
        "acousticness": 0.763,
        "instrumentalness": 0.195,
        "liveness": 0.146,
        "valence": 0.698,
        "tempo": 135.145,
        "type": "audio_features",
        "id": "5MyQwsO0ktOmdRxg9bmFeW",
        "uri": "spotify:track:5MyQwsO0ktOmdRxg9bmFeW",
        "track_href": "https://api.spotify.com/v1/tracks/5MyQwsO0ktOmdRxg9bmFeW",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/5MyQwsO0ktOmdRxg9bmFeW",
        "duration_ms": 400840,
        "time_signature": 4,
    },
    {
        "danceability": 0.597,
        "energy": 0.196,
        "key": 2,
        "loudness": -17.343,
        "mode": 1,
        "speechiness": 0.028,
        "acousticness": 0.843,
        "instrumentalness": 0.847,
        "liveness": 0.103,
        "valence": 0.164,
        "tempo": 109.695,
        "type": "audio_features",
        "id": "771I4XsOUGOeuIdeVh0IsR",
        "uri": "spotify:track:771I4XsOUGOeuIdeVh0IsR",
        "track_href": "https://api.spotify.com/v1/tracks/771I4XsOUGOeuIdeVh0IsR",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/771I4XsOUGOeuIdeVh0IsR",
        "duration_ms": 258751,
        "time_signature": 4,
    },
    {
        "danceability": 0.62,
        "energy": 0.705,
        "key": 8,
        "loudness": -10.179,
        "mode": 1,
        "speechiness": 0.0404,
        "acousticness": 0.151,
        "instrumentalness": 0.0802,
        "liveness": 0.107,
        "valence": 0.907,
        "tempo": 93.018,
        "type": "audio_features",
        "id": "1pYPgA8XdHFQS15HPB41MH",
        "uri": "spotify:track:1pYPgA8XdHFQS15HPB41MH",
        "track_href": "https://api.spotify.com/v1/tracks/1pYPgA8XdHFQS15HPB41MH",
        "analysis_url": "https://api.spotify.com/v1/audio-analysis/1pYPgA8XdHFQS15HPB41MH",
        "duration_ms": 379400,
        "time_signature": 4,
    },
]
