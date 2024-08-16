library(readr)
library(dplyr)
setwd("C:/Users/Charl/Documents/GitHub/SpotifyPlaylistSplitter")
# Sample data frame
# Assuming 'playlist' has columns 'playlist_id' and 'song_id'
playlist <- data.frame(
  playlist_id = c(1, 1, 2, 2, 3),
  song_id = c("song1", "song2", "song1", "song3", "song2")
)


playlist <- read_delim("spotify_playlist.csv", delim = ",", escape_double = TRUE)

# Select the first n rows
n = 0
if (n > 0){
  playlist <- playlist[1:n,]
}

#################  DATA CLEANING ####################
# Fix the column names
colnames(playlist) <- gsub(' "trackname"', 'track_name', colnames(playlist))
colnames(playlist) <- gsub(' "artistname"', 'artist_name', colnames(playlist))
colnames(playlist) <- gsub(' "playlistname"', 'playlist_name', colnames(playlist))


min_song_occurences = 2
playlist <- get_playlist_data(rows_to_scrape) %>%
  mutate(song = paste(artist_name, track_name, sep = " - ")) %>%
  select(user_id,playlist_name,song) %>%
  unique() %>%
  group_by(song) %>%
  filter(n() >= min_song_occurences) %>% #Remove all songs occuring only once, since they cannot be analysed
  ungroup()

# Convert to factors to get unique integer identifiers
playlist$user_id <- as.factor(playlist$user_id)
playlist$song <- as.factor(playlist$song)
playlist$playlist_name <- as.factor(playlist$playlist_name)

# Get the numeric representations
users <- as.integer(playlist$user_id)
songs <- as.integer(playlist$song)
playlists <- as.integer(playlist$playlist_name)
# Create the sparse matrix
sparse_adj_matrix <- sparseMatrix(
  i = songs,
  j = users,
  x = 1,  # value to be inserted (1 indicates the presence of the song in the playlist)
  dims = c(length(levels(playlist$song)),length(levels(playlist$user_id)))
)
sparse_adj_matrix <- sparseMatrix(
  i = songs,
  j = playlists,
  x = 1,  # value to be inserted (1 indicates the presence of the song in the playlist)
  dims = c(length(levels(playlist$song)),length(levels(playlist$playlist_name)))
)

# Assign row and column names
rownames(sparse_adj_matrix) <- levels(playlist$song)
colnames(sparse_adj_matrix) <- levels(playlist$user_id)
colnames(sparse_adj_matrix) <- levels(playlist$playlist_name)

saveRDS(sparse_adj_matrix, "user_song_adj_minsong2.rds")
user_song_adj <- readRDS("user_song_adj_minsong2.rds")


saveRDS(sparse_adj_matrix, "playlist_song_adj_minsong2.rds")
user_song_adj <- readRDS("user_song_adj_minsong2.rds")