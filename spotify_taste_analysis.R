library(ggplot2)
setwd("C:/Users/Charl/Programming/SpotifyPlaylistSplitter")

# Function to compute mean, median, and standard deviation excluding the diagonal
row_stats <- function(row) {
  mean_val <- mean(row)
  median_val <- median(row)
  return(c(mean_val, median_val, sd_val))
}
# Function to compute percentile
compute_percentile_ratio <- function(value) {
  percentile <- sum(user_song_popularity$Ratio <= value['Ratio']) / length(user_song_popularity$Ratio) * 100
  return(percentile)
}
# Function to compute percentile
compute_percentile_interesting <- function(value) {
  percentile <- sum(user_song_popularity$interest_cons <= value['interest_cons']) / length(user_song_popularity$interest_cons) * 100
  return(percentile)
}
# Function to compute percentile
compute_percentile_combined <- function(value) {
  percentile <- sum(user_song_popularity$'Combined Score' <= value['Combined Score']) / length(user_song_popularity$'Combined Score') * 100
  return(percentile)
}


song_matrix <- readRDS("user_song_adj_minsong2.rds")
#adjacency matrix of how songs link users
adjacency_matrix <- t(song_matrix) %*% song_matrix  #user-user sparse adjacency matrix
#adjacency_matrix <- as.matrix(adjacency_matrix)

total_user_songs <- diag(adjacency_matrix)
diag(adjacency_matrix) <- 0

######## Calculates some statistics about user-user adjacency
common_songs <- rowSums(adjacency_matrix)
song_choice_stats <- t(apply(adjacency_matrix, 1, row_stats))
song_choice_ratio <- common_songs / total_user_songs
user_song_popularity <- cbind(total_user_songs, common_songs, song_choice_ratio, song_choice_stats)
colnames(user_song_popularity) <- c("Total songs", "Common songs", "Ratio", "Mean", "Median", "SD")
rownames(user_song_popularity) <- rownames(adjacency_matrix)
user_song_popularity <- as.data.frame(user_song_popularity)

###### Create matrix for users with unusual taste
interesting_users <- rownames(user_song_popularity[user_song_popularity$Ratio <= 10 & user_song_popularity$`Total songs`>100,])
interesting_users <- as.character(interesting_users)  # Convert to character vector for subsetting
adjacency_matrix_subset <- adjacency_matrix[, interesting_users]
interest_cons <- rowSums(adjacency_matrix_subset != 0)
user_song_popularity$interest_cons <- interest_cons

####### Plot Average songs in common
# Compute density estimate
dens <- density(user_song_popularity$Mean)
dens_df <- data.frame(x = dens$x, y = dens$y)
my_position <- user_song_popularity["Charlie",]$Mean
percentile <- sum(user_song_popularity$Mean <= my_position) / length(user_song_popularity$Mean) * 100
percentile <- sprintf("%.1f", percentile)

ggplot(dens_df, aes(x, y)) +
  geom_line(color = "blue", linewidth = 1.5) +
  labs(title = "PDF of  Average Number of Songs in Common",
       x = "Average songs in common", y = "Density") +
  theme_minimal() +
  geom_vline(xintercept = user_song_popularity["Charlie",]$Mean, color = "red", size = 1) +  # Add vertical red line
  annotate("text", x = user_song_popularity["Charlie",]$Mean, y = max(dens_df$y), 
           label = paste("Me @ Percentile: ", percentile, "%"),
           color = "red", vjust = 10, hjust = -0.05) +  # Add text label
  theme(plot.title = element_text(hjust = 0.5))

####### Plot Ratio songs in common
# Compute density estimate
dens <- density(user_song_popularity$Ratio)
dens_df <- data.frame(x = dens$x, y = dens$y)
my_position <- user_song_popularity["Charlie",]$Ratio
percentile <- sum(user_song_popularity$Ratio <= my_position) / length(user_song_popularity$Ratio) * 100
percentile <- sprintf("%.1f", percentile)
percentiles <- apply(user_song_popularity, 1, compute_percentile_ratio)
user_song_popularity$'Ratio Percentile' <- percentiles


ggplot(dens_df, aes(x, y)) +
  geom_line(color = "blue", size = 1.5) +
  labs(title = "PDF of  Ratio of Songs in Common",
       x = "Average (songs in common)/(total songs in playlists)", y = "Density") +
  theme_minimal() +
  geom_vline(xintercept = user_song_popularity["Charlie",]$Ratio, color = "red", size = 1) +  # Add vertical red line
  annotate("text", x = user_song_popularity["Charlie",]$Ratio, y = max(dens_df$y), 
           label = paste("Me @ Percentile: ", percentile, "%"),
           color = "red", vjust = 10, hjust = -0.05) +  # Add text label
  theme(plot.title = element_text(hjust = 0.5))

####### Plot interesting user connections
# Compute density estimate
dens <- density(user_song_popularity$interest_cons)
dens_df <- data.frame(x = dens$x, y = dens$y)
my_position <- user_song_popularity["Charlie",]$interest_cons
percentile <- sum(user_song_popularity$interest_cons <= my_position) / 
  length(user_song_popularity$interest_cons) * 100
percentile <- sprintf("%.1f", percentile)
user_song_popularity$'Interesting Percentile' <- 
  apply(user_song_popularity, 1, compute_percentile_interesting)

ggplot(dens_df, aes(x, y)) +
  geom_line(color = "blue", size = 1.5) +
  labs(title = "PDF of links  to unusual users",
       x = "Links to users with unusual tastes", y = "Density") +
  theme_minimal() +
  geom_vline(xintercept = user_song_popularity["Charlie",]$interest_cons, color = "red", size = 1) +  # Add vertical red line
  annotate("text", x = user_song_popularity["Charlie",]$interest_cons, y = max(dens_df$y), 
           label = paste("Me @ Percentile: ", percentile, "%"),
           color = "red", vjust = 10, hjust = -0.05) +  # Add text label
  theme(plot.title = element_text(hjust = 0.5))

user_song_popularity$'Combined Score' <- 
  (user_song_popularity$'Interesting Percentile'/100)*
  (user_song_popularity$'Ratio Percentile'/100)
user_song_popularity$'Comb score Percentile' <- 
  apply(user_song_popularity, 1, compute_percentile_combined)

user_song_popularity['Charlie',]


####### Plot interesting user connections
# Compute density estimate
dens <- density(user_song_popularity$'Combined Score')
dens_df <- data.frame(x = dens$x, y = dens$y)
my_position <- user_song_popularity["Charlie",]$'Combined Score'
percentile <- sum(user_song_popularity$'Combined Score' <= my_position) /
  length(user_song_popularity$'Combined Score') * 100
percentile <- sprintf("%.1f", percentile)

ggplot(dens_df, aes(x, y)) +
  geom_line(color = "blue", size = 1.5) +
  labs(title = "PDF of combined music taste score",
       x = "Combined broadness + interesting taste score", y = "Density") +
  theme_minimal() +
  geom_vline(xintercept = user_song_popularity["Charlie",]$'Combined Score', color = "red", size = 1) +  # Add vertical red line
  annotate("text", x = user_song_popularity["Charlie",]$'Combined Score', y = max(dens_df$y), 
           label = paste("Me @ Percentile: ", percentile, "%"),
           color = "red", vjust = 10, hjust = -0.05) +  # Add text label
  theme(plot.title = element_text(hjust = 0.5))
