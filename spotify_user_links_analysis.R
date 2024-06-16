######## #################### #################### #################### #################### ############
######## Analysing matrix of songs and users
######## #################### #################### #################### #################### ############

library(ggplot2)
library(igraph)
library(readr)
library(dplyr)
library(tidyr)
library(Matrix)
library(png)

song_matrix <- readRDS("user_song_adj_minsong2.rds")
#adjacency matrix of how songs link users
adjacency_matrix <- t(song_matrix) %*% song_matrix  #user-user sparse adjacency matrix
#adjacency_matrix <- as.matrix(adjacency_matrix)
diag(adjacency_matrix) <- 0
small_matrix_size <- 400
row_index <- max(match("Charlie", rownames(adjacency_matrix)),small_matrix_size+1)

adjacency_matrix <- adjacency_matrix[c(1:small_matrix_size, row_index), c(1:small_matrix_size, row_index)]
adjacency_matrix <- as.matrix(adjacency_matrix)
g <- graph_from_adjacency_matrix(adjacency_matrix,mode = c("undirected"), weighted=TRUE,diag=FALSE)

#### Some graph statistics
edge_density(g, loops=F)
median(degree(g))
centr_degree(g, mode="in", normalized=T)$centralization
transitivity(g,"global")
diameter(g, directed=F)
g_d = distances(g, weights = NA)
mean_finite_distances <- mean(g_d[is.finite(g_d)])

#### Plotting the graph
l <- layout_with_kk(g)
l2  = sqrt(rowSums(l*l))
#sort(l2, decreasing = T)
l[5.8 < l2 & l2 < 7,] <- l[5.8 < l2 & l2 < 7,] *0.9
l[l2 > 10,] <- l[l2 > 10,] * 0.2
l[l2 > 3,] <- l[l2 > 3,]*.75
l <- norm_coords(l, ymin=-1, ymax=1, xmin=-1, xmax=1)
# Define a color palette
palette <- colorRampPalette(c("lightgreen", "green"))
# Map edge weights to colors
edge_colors <- palette(100)[cut(E(g)$weight, breaks = 100)]

img <- readPNG("black.png")

# Set up the plot area
plot(g, vertex.label = NA,vertex.size=0,edge.width = 0,type="n", rescale=F, layout=l)  # Create an empty plot

# Add the image to the plot area
rasterImage(img, -1.5, -1.5, 1.5, 1.5)


plot(g, 
     vertex.label = NA,
     vertex.size= ifelse(V(g)$name == "Charlie", 3, 1),
     vertex.color=ifelse(V(g)$name == "Charlie", adjustcolor("red",alpha.f=1),adjustcolor("white",alpha.f=1)),
     vertex.frame.color=adjustcolor("white",alpha.f=0),
     edge.width = 0.5,# (E(g)$weight**0.5)/5,
     edge.color = adjustcolor(edge_colors, alpha.f = 0.01),#edge_colors,
     edge.curved=0,
     rescale=F,
     layout=l,
     vertex.shape = ifelse(V(g)$name == "Charlie", "square", "circle"),
     add=T
)