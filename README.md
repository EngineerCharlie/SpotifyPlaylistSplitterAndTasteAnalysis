# SpotifyPlaylistSplitter
Uses a dataset of users, their playlists, and the songs in those playlists, to analyse the subjective "quality" of your music taste. It uses the same data to suggest ways that playlists, particularly large ones, can be split apart and broken down into multiple smaller playlists with a greater focus.
## Spotify api link
*Python*. The spotify api is used predominantly to download a users music library, however some code has been developed to scrape a more up to date user-playlist-song database. 
## Taste analysis
*R* - This looks at the percentiles of "uniqueness" of music taste, as well as popularity of music taste, to come up with a combined figure. Results are questionable.
## Splitting playlists
*R* - This uses graphs, looking at the connections between songs through playlists (and theoretically users), to do a cluster analysis and break apart playlists. For example, a random playlist consisting of Led Zeppelin, Rolling Stones, Beyonce and Taylor Swift will probably be split with almost entirely Zeppelin and Stones in one, and Beyonce and Swift in the other. (This isn't guaranteed though, their could be strong links between unexpected songs).
