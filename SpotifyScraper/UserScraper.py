import SpotipyBootstrap
import csv
import time
import random

request_delay = 15


# Get current user's playlists created by the user
def get_user_playlist_owners_and_playlists(user_id):
    offset = 0
    limit = 25
    user_playlist_owners = set()
    playlist_ids = set()
    response = SpotipyBootstrap.sp.user_playlists(user_id, offset=offset, limit=limit)
    while len(response["items"]) > 0:
        for playlist in response["items"]:
            playlist_ids.add(playlist["id"])
            user_playlist_owners.add(playlist["owner"]["id"])
        offset += 50
        time.sleep(request_delay)
        if len(response["items"]) < limit:
            break
        response = SpotipyBootstrap.sp.user_playlists(
            user_id, offset=offset, limit=limit
        )
        if offset > 250:
            print("this user has a shitload of playlists")
        if offset >500:
            print("Over 500, sod this breaking the loop")
            break
    return user_playlist_owners, playlist_ids


users_to_explore = set()
explored_users = set()
playlist_ids = set()
new_explored_users = set()
times_errored = 0

try:
    csv_file = "SpotifyScraper/spot_data_users_to_explore.csv"
    with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure row is not empty
                users_to_explore.add(row[0])  # Add each user_id to the set\

    csv_file = "SpotifyScraper/spot_data_explored_user_ids.csv"
    with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure row is not empty
                explored_users.add(row[0])  # Add each user_id to the set

    csv_file = "SpotifyScraper/spot_data_playlist_ids.csv"
    with open(csv_file, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure row is not empty
                playlist_ids.add(row[0])  # Add each user_id to the set
except FileNotFoundError:
    print(f"{csv_file} not found. Terminating program.")
    exit()


def checkpoint():
    csv_file = "SpotifyScraper/spot_data_users_to_explore.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)  # Write header
        writer.writerows([[user_id] for user_id in users_to_explore])  # Write data

    csv_file = "SpotifyScraper/spot_data_explored_user_ids.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)  # Write header
        writer.writerows([[user_id] for user_id in explored_users])  # Write data

    csv_file = "SpotifyScraper/spot_data_playlist_ids.csv"
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)  # Write header
        writer.writerows([[playlist_id] for playlist_id in playlist_ids])  # Write data


num_explored_users = 0
while users_to_explore and num_explored_users < 100000:
    current_user = users_to_explore.pop()
    print(current_user)
    print(len(users_to_explore))
    explored_users.add(current_user)
    try:
        new_users, new_playlists = get_user_playlist_owners_and_playlists(current_user)
        new_users -= explored_users
        playlist_ids.update(new_playlists)
        users_to_explore.update(new_users)
    except Exception as e:
        users_to_explore.add(current_user)
        print(
            f"\n\n_____________________________________________________\n\nERROR: \n{e}"
        )
        if times_errored < 3:
            time.sleep(120)
            times_errored += 1
            pass
        else:
            break
    num_explored_users = len(explored_users)
    if num_explored_users % 25 == 0:

        print(f"\n\n______Checkpoint_____\n{num_explored_users} explored users")
        print(time.ctime())
        checkpoint()

checkpoint()
