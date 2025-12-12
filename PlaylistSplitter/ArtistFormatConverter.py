import json
import os

# List of artists with commas in their names that should NOT be split
EXCEPTION_ARTISTS = {
    "1, 2, 3",
    "10,000 Maniacs",
    "Anderson, Bruford, Wakeman, Howe",
    "Anderson, Ponty, Clarke",
    "Bang, Bang, Eche!",
    "Beck, Bogert & Appice",
    "Blood, Sweat & Tears",
    "Bloom, de Wilde",
    "Boone, Creek",
    "Boy, Girl",
    "Brother, Sister",
    "City, State",
    "Comma,",
    "Crosby, Stills & Nash",
    "Crosby, Stills, Nash & Young",
    "Dad, Mom, God",
    "Dance, Dance, Dance",
    "Darlings, It's For You",
    "Dave Dee, Dozy, Beaky, Mick & Tich",
    "Dino, Desi & Billy",
    "Does It Offend You, Yeah?",
    "Earth, Wind & Fire",
    "Emerson, Lake & Palmer",
    "Emerson, Lake & Powell",
    "Empire, Empire! (I Was a Lonely Estate)",
    "Fear, and Loathing in Las Vegas",
    "Fight, Fight, Fight",
    "Forward, Russia!",
    "Go, Motion",
    "The Good, The Bad & The Queen",
    "Goodbye, Titan",
    "Hamilton, Joe Frank & Reynolds",
    "Hello, Blue Roses",
    "Hey, Mercedes",
    "Hey, Ocean!",
    "I, A Man",
    "I, Crime",
    "I, Ludicrous",
    "I, Parasite",
    "I, The Mighty",
    "I, Void",
    "Joie, Dead",
    "Kiss, Kiss",
    "Kitty, Daisy & Lewis",
    "Lambert, Hendricks & Bavan",
    "Lambert, Hendricks & Ross",
    "Listen, Listen",
    "Look, Look",
    "Look, Stranger!",
    "Love, Robot",
    "Lucky, Lucky Pigeons",
    "Man, Woman, Child",
    "Matthews, Wright & King",
    "McGuinn, Clark & Hillman",
    "Medeski, Martin & Wood",
    "Medeski, Scofield, Martin & Wood",
    "Me, Mom & Morgentaler",
    "Me, My Head, and I",
    "Nice, Nice",
    "No, No, No",
    "No, Really",
    "Now, Now",
    "Oh, Be Clever",
    "Oh, Flamingo!",
    "Oh, Honey",
    "Oh, My!",
    "Oh, Sleeper",
    "Oh, The Larceny",
    "Oh, Weatherly",
    "Okay, Monday",
    "Peter, Paul and Mary",
    "Phantom, Rocker & Slick",
    "Please, Please",
    "Pop, Etc",
    "Ready, Set, Fall!",
    "Run, Forever",
    "Run, Run, Run",
    "Run, Walk, Chop",
    "Say, Do",
    "Shhh, It's Quiet",
    "So, So, So",
    "Stop, Drop, Rewind",
    "Stop, Look, Listen",
    "Terry, Blair & Anouchka",
    "Tex, Don and Charlie",
    "Tipton, Entwistle & Powell",
    "Tyler, The Creator",
    "Wait, Think Fast",
    "Wait, What?",
    "We, The Kings",
    "Well, Well, Well",
    "West, Bruce & Laing",
    "Why, Because",
    "Yeah, Whatever",
    "You, Me & Apollo",
    "You, Me, and Everyone We Know",
    "You, Me, and The Violence",
}


def convert_artist_format(artist_string):
    """
    Convert artist string from comma-separated to semicolon-separated with quotes.
    Handles exception artists that contain commas in their names.

    Args:
        artist_string: Original artist string (e.g., "Artist1, Artist2" or "Earth, Wind & Fire")

    Returns:
        Formatted artist string (e.g., "'Artist1';'Artist2'" or "'Earth, Wind & Fire'")
    """
    # If the entire string is an exception artist, wrap it in quotes
    if artist_string in EXCEPTION_ARTISTS:
        return f"'{artist_string}'"

    # Check if any exception artist is contained in the string
    # This handles cases where the exception artist is part of a collaboration
    for exception in EXCEPTION_ARTISTS:
        if exception in artist_string:
            # Split by the exception to see if there are other artists
            parts = artist_string.split(exception)
            if len(parts) == 2:
                # Exception artist is in the string with other artists
                artists = []

                # Process before exception
                if parts[0].strip():
                    # Remove trailing comma/whitespace
                    before = parts[0].strip().rstrip(",").strip()
                    if before:
                        artists.append(before)

                # Add exception artist
                artists.append(exception)

                # Process after exception
                if parts[1].strip():
                    # Remove leading comma/whitespace
                    after = parts[1].strip().lstrip(",").strip()
                    if after:
                        artists.append(after)

                # Format with quotes and semicolons
                return ";".join(f"'{artist.strip()}'" for artist in artists)

    # No exception artist found, split by comma
    if "," in artist_string:
        artists = [artist.strip() for artist in artist_string.split(",")]
        return ";".join(f"'{artist}'" for artist in artists if artist)
    else:
        # Single artist, no comma
        return f"'{artist_string}'"


def process_playlist_data(input_file, output_file):
    """
    Process the playlist JSON file and convert artist formats.

    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file
    """
    # Read the input file
    print(f"Reading {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        playlists = json.load(f)

    # Track statistics
    total_tracks = 0
    converted_tracks = 0

    # Process each playlist
    for playlist in playlists:
        tracks = playlist.get("tracks", [])
        for i, track in enumerate(tracks):
            if len(track) >= 2:
                total_tracks += 1
                original_artist = track[1]
                converted_artist = convert_artist_format(original_artist)

                # Update the artist field
                track[1] = converted_artist

                # Show conversion if it changed
                if original_artist != converted_artist:
                    converted_tracks += 1

    # Write the converted data
    print(f"Writing converted data to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(playlists, f, indent=4, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Conversion complete!")
    print(f"Total tracks processed: {total_tracks}")
    print(f"Tracks converted: {converted_tracks}")
    print(f"Output saved to: {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Define file paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")

    input_file = os.path.join(data_dir, "spotify_playlists_data_backup_2025_12_10.json")
    output_file = os.path.join(
        data_dir, "spotify_playlists_data_backup_2025_12_10_converted.json"
    )

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        exit(1)

    # Process the data
    process_playlist_data(input_file, output_file)

    print("\n\nReview the output file. If everything looks good, you can:")
    print(
        f"1. Delete or archive the backup: {os.path.join(data_dir, 'spotify_playlists_data_1_backup_before_conversion.json')}"
    )
    print(
        f"2. Replace the original: rename '{output_file}' to 'spotify_playlists_data_1.json'"
    )
