# Sample data frame
# Assuming 'playlist' has columns 'playlist_id' and 'song_id'
playlist <- data.frame(
  playlist_id = c(1, 1, 2, 2, 3),
  song_id = c("song1", "song2", "song1", "song3", "song2")
)

# Convert to factors to get unique integer identifiers
playlist$user_id <- as.factor(playlist$user_id)
playlist$song <- as.factor(playlist$song)

# Get the numeric representations
users <- as.integer(playlist$user_id)
songs <- as.integer(playlist$song)

# Create the sparse matrix
sparse_adj_matrix <- sparseMatrix(
  i = songs,
  j = users,
  x = 1,  # value to be inserted (1 indicates the presence of the song in the playlist)
  dims = c(length(levels(playlist$song)),length(levels(playlist$user_id)))
)

# Assign row and column names
rownames(sparse_adj_matrix) <- levels(playlist$song)
colnames(sparse_adj_matrix) <- levels(playlist$user_id)

saveRDS(sparse_adj_matrix, "user_song_adj_minsong2.rds")
user_song_adj <- readRDS("user_song_adj_minsong2.rds")
