import csv
import json
import time
import SpotipyBootstrap as SpotipyBootstrap

# File paths for the CSV files
PLAYLISTS_TO_SCRAPE_FILE = "SpotifyScraper/spot_data_playlist_ids.csv"
SCRAPED_PLAYLISTS_FILE = "SpotifyScraper/spot_data_playlist_ids_scraped.csv"
OUTPUT_JSON_FILE = "SpotifyScraper/spotify_playlists_data.json"
API_DELAY_BASE = 35  # Time delay in seconds between API requests
api_delay_modified = 45


# Function to read playlist IDs from CSV
def read_csv_to_set(filename):
    playlist_ids = set()
    try:
        with open(filename, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:  # Ensure the row is not empty
                    playlist_ids.add(row[0])
    except FileNotFoundError:
        print(f"{filename} not found. Creating a new one.")
    return playlist_ids


# Function to write playlist IDs to CSV
def add_set_to_csv(filename, data_set):
    with open(filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows([[item] for item in data_set])


def set_api_delay(number_of_tracks_in_response):
    global api_delay_modified
    api_delay_modified = 10 + API_DELAY_BASE * number_of_tracks_in_response / 100


# Function to fetch playlist details from Spotify
def get_playlist_data(sp: SpotipyBootstrap.spotipy.Spotify, playlist_id):
    try:
        playlist_info = sp.playlist(playlist_id)

        print(f"# tracks in playlist: {playlist_info['tracks']['total']}")
        set_api_delay(len(playlist_info["tracks"]["items"]))
        if playlist_info["tracks"]["total"] <= 1:
            return None
        playlist_name = playlist_info["name"]
        user_id = playlist_info["owner"]["id"]
        tracks = []
        while playlist_info:
            set_api_delay(len(playlist_info["tracks"]["items"]))
            for item in playlist_info["tracks"]["items"]:
                track = item["track"]
                track_name = track["name"]
                artist_names = ", ".join(
                    [artist["name"] for artist in track["artists"]]
                )
                tracks.append((track_name, artist_names))
            if playlist_info["tracks"]["next"] is not None:
                time.sleep(api_delay_modified)
                playlist_info["tracks"] = sp.next(playlist_info["tracks"])
                set_api_delay(len(playlist_info["tracks"]["items"]))
            else:
                playlist_info = None
        return {
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "user_id": user_id,
            "tracks": tracks,
        }
    except Exception as e:
        print(f"Error fetching data for playlist {playlist_id}: {e}")
        return None


# Main program
def main():
    # Initialize the Spotify client
    sp = SpotipyBootstrap.sp

    # Read playlist IDs to scrape and already scraped
    playlist_ids_to_scrape = read_csv_to_set(PLAYLISTS_TO_SCRAPE_FILE)
    scraped_playlist_ids = read_csv_to_set(SCRAPED_PLAYLISTS_FILE)

    # Loop over the playlists to scrape
    for playlist_id in playlist_ids_to_scrape:
        if playlist_id in scraped_playlist_ids:
            print(f"Playlist {playlist_id} already scraped. Skipping.")
            continue

        # Fetch the playlist data
        print(f"Fetching data for playlist {playlist_id}, {time.ctime()}...")
        playlist_info = get_playlist_data(sp, playlist_id)

        if playlist_info:
            # Append the playlist ID to the scraped playlist CSV
            scraped_playlist_ids.add(playlist_id)
            add_set_to_csv(SCRAPED_PLAYLISTS_FILE, [playlist_id])

            # Save the playlist data to the JSON file
            with open(OUTPUT_JSON_FILE, mode="a", encoding="utf-8") as json_file:
                json_file.write(",\n")
                json.dump(playlist_info, json_file, indent=4)

        # Wait for a specified delay between API calls
        print(f"Waiting for {api_delay_modified} seconds...")
        time.sleep(api_delay_modified)
    print("Scraping process completed!")
    with open(OUTPUT_JSON_FILE, mode="a", encoding="utf-8") as json_file:
        json_file.write("\n]", json_file)


if __name__ == "__main__":
    main()
