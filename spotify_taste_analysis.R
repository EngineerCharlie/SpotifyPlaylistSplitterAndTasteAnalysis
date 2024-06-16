library(ggplot2)
setwd("C:/Users/Charl/Programming/SpotifyPlaylistSplitter")

# Function to compute mean, median, and standard deviation excluding the diagonal
row_stats <- function(row) {
  mean_val <- mean(row)
  median_val <- median(row)
  return(c(mean_val, median_val))
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
colnames(user_song_popularity) <- c("Total songs", "Common songs", "Ratio", "Mean", "Median")
rownames(user_song_popularity) <- rownames(adjacency_matrix)
user_song_popularity <- as.data.frame(user_song_popularity)

###### Create matrix for users with unusual taste
interesting_users <- rownames(user_song_popularity[user_song_popularity$Ratio <= 10 & user_song_popularity$`Total songs`>100,])
interesting_users <- as.character(interesting_users)  # Convert to character vector for subsetting
adjacency_matrix_subset <- adjacency_matrix[, interesting_users]
interest_cons <- rowSums(adjacency_matrix_subset)/user_song_popularity$'Total songs'
user_song_popularity$interest_cons <- interest_cons

####### Plot mean songs in common
# Compute density estimate
my_position <- user_song_popularity["Charlie",]$Mean
percentile <- sum(user_song_popularity$Mean <= my_position) / length(user_song_popularity$Mean) * 100
percentile <- sprintf("%.1f", percentile)

ggplot(user_song_popularity, aes(x = Mean)) +
  geom_histogram(binwidth = 1, fill = "lightgreen", color = "black", alpha = 0.7) +
  labs(title = "",#Histogram of Mean Number of Common Songs",
       x ="",# "Mean Number of Common Songs",
       y ="")+# "Frequency") +
  theme_minimal() +
  coord_cartesian(xlim = c(0, 30)) + 
  theme(
    plot.background = element_rect(fill = "black"),
    panel.background = element_rect(fill = "black"),
    plot.title = element_text(hjust = 0.5),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    axis.line = element_line(color = "white"),
    text = element_text(color = "white"),
    axis.text = element_text(color = 'white')
  )



####### Plot Ratio songs in common
my_position <- user_song_popularity["Charlie",]$Ratio
percentile <- sum(user_song_popularity$Ratio <= my_position) / length(user_song_popularity$Ratio) * 100
percentile <- sprintf("%.1f", percentile)
percentiles <- apply(user_song_popularity, 1, compute_percentile_ratio)
user_song_popularity$'Ratio Percentile' <- percentiles

ggplot(user_song_popularity, aes(x = Ratio)) +
  geom_histogram(binwidth = 10, fill = "lightgreen", color = "black", alpha = 0.7) +
  labs(title = "",#Histogram of Mean Number of Common Songs",
       x ="",# "Mean Number of Common Songs",
       y ="")+# "Frequency") +
  theme_minimal() +
  coord_cartesian(xlim = c(0, 800)) + 
  theme(
    plot.background = element_rect(fill = "black"),
    panel.background = element_rect(fill = "black"),
    plot.title = element_text(hjust = 0.5),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    axis.line = element_line(color = "white"),
    text = element_text(color = "white"),
    axis.text = element_text(color = 'white')
  )




####### Plot interesting user connections
# Compute density estimate
my_position <- user_song_popularity["Charlie",]$interest_cons
percentile <- sum(user_song_popularity$interest_cons <= my_position) / 
  length(user_song_popularity$interest_cons) * 100
percentile <- sprintf("%.1f", percentile)
user_song_popularity$'Interesting Percentile' <- 
  apply(user_song_popularity, 1, compute_percentile_interesting)

ggplot(user_song_popularity, aes(x = interest_cons)) +
  geom_histogram(binwidth = 0.01, fill = "lightgreen", color = "black", alpha = 0.7) +
  labs(title = "",#Histogram of Mean Number of Common Songs",
       x ="",# "Mean Number of Common Songs",
       y ="")+# "Frequency") +
  theme_minimal() +
  coord_cartesian(xlim = c(0, 1.05)) + 
  theme(
    plot.background = element_rect(fill = "black"),
    panel.background = element_rect(fill = "black"),
    plot.title = element_text(hjust = 0.5),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    axis.line = element_line(color = "white"),
    text = element_text(color = "white"),
    axis.text = element_text(color = 'white')
  )

user_song_popularity$'Combined Score' <- 
  (user_song_popularity$'Interesting Percentile'/100)*
  (user_song_popularity$'Ratio Percentile'/100)
user_song_popularity$'Comb score Percentile' <- 
  apply(user_song_popularity, 1, compute_percentile_combined)

user_song_popularity['Charlie',]


####### Plot interesting user connections
# Compute density estimate
my_position <- user_song_popularity["Charlie",]$'Combined Score'
percentile <- sum(user_song_popularity$'Combined Score' <= my_position) /
  length(user_song_popularity$'Combined Score') * 100
percentile <- sprintf("%.1f", percentile)

ggplot(user_song_popularity, aes(x = `Combined Score`)) +
  geom_histogram(binwidth = 0.02, fill = "lightgreen", color = "black", alpha = 0.7) +
  labs(title = "", # Histogram of Mean Number of Common Songs",
       x = "",    # "Mean Number of Common Songs",
       y = "") +  # "Frequency") +
  theme_minimal() +
  coord_cartesian(xlim = c(0, 1)) +
  theme(
    plot.background = element_rect(fill = "black"),
    panel.background = element_rect(fill = "black"),
    plot.title = element_text(hjust = 0.5),
    panel.grid.major = element_blank(),
    panel.grid.minor = element_blank(),
    axis.line = element_line(color = "white"),
    text = element_text(color = "white"),
    axis.text = element_text(color = 'white')
  )
