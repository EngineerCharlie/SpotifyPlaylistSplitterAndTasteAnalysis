library(ggplot2)
library(igraph)
library(readr)
library(dplyr)
library(tidyr)
library(Matrix)
library(png)
library(networkD3)
setwd("C:/Users/Charl/Programming/SpotifyPlaylistSplitter")
song_matrix <- readRDS("playlist_song_adj_minsong2.rds")
get_charlies_playlists <- function() {
  # Read the data
  playlist <- read_delim("Charlies_playlists.csv", delim = ",", escape_double = TRUE)
  return(playlist)
}
get_largest_playlist <- function(name) {
  playlists <- my_playlists[my_playlists$song == name, "playlist_name"]
  largest_playlist <- names(which.min(table(playlists)))
  return(largest_playlist)
}
#### Keep only the rows where a song to be analysed is present
my_playlists <- get_charlies_playlists()
#my_playlists <- my_playlists[my_playlists$playlist_name == "Millennial guitar music Charlie",]
my_playlist_names <- unique(my_playlists$playlist_name)
my_songs <- unique(my_playlists$song)
row_indices <- which(rownames(song_matrix) %in% my_songs)
song_matrix <- song_matrix[row_indices, ]
#### Remove all the playlists which are now empty
columns_to_keep <- which(colSums(song_matrix) > 1)
song_matrix <- song_matrix[, columns_to_keep]

adjacency_matrix <- song_matrix %*% t(song_matrix)
#small_matrix_size <- 100
#adjacency_matrix <- adjacency_matrix[1:small_matrix_size, 1:small_matrix_size]

g <- graph_from_adjacency_matrix(adjacency_matrix,mode = c("undirected"), weighted=TRUE,diag=FALSE)
edge_density(g)
transitivity(g, type="global")
diameter(g)
g_d = distances(g, weights = NA)
mean_finite_distances <- mean(g_d[is.finite(g_d)])

l <- layout_with_fr(g)
palette <- colorRampPalette(c("lightgreen", "green"))
edge_colors <- palette(100)[cut(E(g)$weight, breaks = 100)]
img <- readPNG("black.png")

# Assign the largest playlist to each node
V(g)$largest_playlist <- sapply(V(g)$name, get_largest_playlist)

# Define unique colors and shapes
unique_playlists <- unique(my_playlists$playlist_name)
colors <- c("#FF0000", "#FF7F00", "#FFFF00", "#B2B200", "#4C4C00", "#0000FF", "#4C0099", "#B200B2", "#00B2B2", "#00994C", "#7F7F7F")
colors <- rep(colors, length.out = length(unique_playlists))
shapes <- c("circle","sphere","square")
shapes <- rep(shapes, length.out = length(unique_playlists))

# Create a mapping from playlist to color and shape
playlist_to_color_shape <- data.frame(
  playlist_name = unique_playlists,
  color = colors,
  shape = shapes
)

# Assign colors and shapes to each node based on the largest playlist
V(g)$color <- sapply(V(g)$largest_playlist, function(x) playlist_to_color_shape[playlist_to_color_shape$playlist_name == x, "color"])
V(g)$shape <- sapply(V(g)$largest_playlist, function(x) playlist_to_color_shape[playlist_to_color_shape$playlist_name == x, "shape"])
V(g)$size <- sapply(V(g)$shape, function(x) ifelse(x == "square", 2, 2.5))


# Set up the plot area
plot(g, vertex.label = NA,vertex.frame.color=NA,edge.width = NA,type="n", rescale=T, layout=l, vertex.color=NA)  # Create an empty plot
rasterImage(img, -1.5, -1.5, 1.5, 1.5)
# Set the file name, resolution, and dimensions
plot(g, 
     vertex.label = NA,
     #vertex.size= 1,
     vertex.frame.color=adjustcolor("white",alpha.f=0),
     edge.width = 0.5,
     edge.color = adjustcolor(edge_colors, alpha.f = 0.01),#edge_colors,
     edge.curved=0,
     rescale=T,
     layout=l,
     add=T
)

ceb_louvain <- cluster_louvain(g)
plot(ceb_louvain, g, vertex.label = NA,vertex.frame.color=adjustcolor("white",alpha.f=0),edge.width = 0.01,type="n", rescale=T, layout=l, vertex.size=1)  # Create an empty plot
rasterImage(img, -1.5, -1.5, 1.5, 1.5)
plot(ceb_louvain,
     g, 
     vertex.label = NA,
     vertex.size=2,#ifelse(V(g)$type, 2, 5),
     vertex.frame.color=NA,#"white",
     edge.width = 0.1,
     edge.color = NA,
     edge.curved=0.1,
     layout=l,
     rescale=T,
     add=T
)

#### Sankey diagram:
community_membership <- data.frame(song = V(g)$name, playlist = membership(ceb_louvain))

playlist_membership = unique(my_playlists$song)
playlist_membership = data.frame(song = playlist_membership, playlist = sapply(playlist_membership, get_largest_playlist))
playlist_membership$playlist <- substr(playlist_membership$playlist, 1, nchar(playlist_membership$playlist) - 8)

merged_df <- merge(playlist_membership, community_membership, by = "song")
nodes <- data.frame(name = unique(c(merged_df$playlist.x, merged_df$playlist.y)))

# Create links
links <- merged_df %>%
  mutate(source = match(playlist.x, nodes$name) - 1,
         target = match(playlist.y, nodes$name) - 1,
         value = 1) %>%
  select(source, target, value)
# Plot the Sankey diagram with custom CSS
sankeyNetwork(
  Links = links, Nodes = nodes, Source = "source", Target = "target",
  Value = "value", NodeID = "name", units = "Songs",
  nodeWidth = 15, fontSize = 0, fontFamily = "sans-serif",
   margin = list(left = 10, right = 50, top = 20, bottom = 20),
)

source_target_counts <- merged_df %>%
  group_by(playlist.x, playlist.y) %>%
  summarise(count = n(), .groups = 'drop')
source_totals <- source_target_counts %>%
  group_by(playlist.x) %>%
  summarise(total = sum(count), .groups = 'drop')
source_target_percentage <- source_target_counts %>%
  left_join(source_totals, by = "playlist.x") %>%
  mutate(percentage = count / total * 100)
max_percentage_per_source <- source_target_percentage %>%
  group_by(playlist.x) %>%
  summarise(max_percentage = max(percentage), .groups = 'drop')
max_percentage_per_source <- max_percentage_per_source %>%
  rename(source_playlist = playlist.x)

community_membership$artist <- sapply(strsplit(community_membership$song, " - "), `[`, 1)
