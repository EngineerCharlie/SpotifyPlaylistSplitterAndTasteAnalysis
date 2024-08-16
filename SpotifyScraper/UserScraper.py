import SpotipyBootstrap
import SpotifySecrets
import csv
import time


# Get current user's playlists created by the user
def get_user_playlist_owners_and_playlists(user_id):
    offset = 0
    limit = 50
    user_playlist_owners = set()
    playlist_ids = set()
    response = SpotipyBootstrap.sp.user_playlists(user_id, offset=offset, limit=limit)
    while len(response["items"]) > 0:
        for playlist in response["items"]:
            playlist_ids.add(playlist["id"])
            user_playlist_owners.add(playlist["owner"]["id"])
        offset += 50
        response = SpotipyBootstrap.sp.user_playlists(
            user_id, offset=offset, limit=limit
        )
    return user_playlist_owners, playlist_ids


users_to_explore = set()
explored_users = set()
playlist_ids = set()
times_errored = 0

csv_file = "SpotifyScraper/spot_data_users_to_explore.csv"
try:
    with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure row is not empty
                users_to_explore.add(row[0])  # Add each user_id to the set
except FileNotFoundError:
    print(f"{csv_file} not found. Terminating program.")
    exit()

while users_to_explore and len(explored_users) < 100000:
    current_user = users_to_explore.pop()
    print(current_user)
    print(len(users_to_explore))
    explored_users.add(current_user)
    try:
        new_users, new_playlists = get_user_playlist_owners_and_playlists(current_user)
    except Exception as e:
        users_to_explore.add(current_user)
        print(
            "\n\n_____________________________________________________\n\nERROR: \n{e}"
        )
        if times_errored < 3:
            time.sleep(5)
            times_errored += 1
            pass
        else:
            break
    new_users -= explored_users
    playlist_ids.update(new_playlists)
    users_to_explore.update(new_users)

with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)  # Write header
    writer.writerows([[user_id] for user_id in users_to_explore])  # Write data

csv_file = "SpotifyScraper/spot_data_explored_user_ids.csv"
with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)  # Write header
    writer.writerows([[user_id] for user_id in explored_users])  # Write data

csv_file = "SpotifyScraper/spot_data_playlist_ids.csv"
with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)  # Write header
    writer.writerows([[playlist_id] for playlist_id in playlist_ids])  # Write data
