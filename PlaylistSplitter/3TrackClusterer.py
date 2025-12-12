import os
import json
import numpy as np
import networkx as nx
from scipy.sparse import lil_matrix, csr_matrix
from sklearn.cluster import SpectralClustering, AgglomerativeClustering

try:
    import community as community_louvain  # python-louvain
except ImportError as exc:  # pragma: no cover - optional dependency
    community_louvain = None
    _louvain_import_error = exc
from collections import defaultdict
import csv

base_dir = os.path.dirname(__file__)
filtered_path = os.path.join(base_dir, "..", "data", "filtered_playlists.json")


def load_filtered_playlists(json_path: str):
    """Load the filtered playlists JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cooccurrence_matrix(playlists):
    """
    Build a sparse co-occurrence matrix where matrix[i][j] represents
    the number of playlists that contain both song i and song j.

    Returns:
        - adjacency_matrix: sparse matrix of co-occurrences
        - song_to_idx: dict mapping (title, artist) to matrix index
        - idx_to_song: dict mapping matrix index to (title, artist)
    """

    # First pass: index all unique songs
    song_to_idx = {}
    idx_to_song = {}
    idx = 0

    for playlist in playlists:
        tracks = playlist.get("tracks", [])
        for track in tracks:
            if isinstance(track, list) and len(track) == 2:
                song_tuple = tuple(track)
                if song_tuple not in song_to_idx:
                    song_to_idx[song_tuple] = idx
                    idx_to_song[idx] = song_tuple
                    idx += 1

    n_songs = len(song_to_idx)
    print(f"Found {n_songs} unique songs in filtered playlists")

    # Build sparse adjacency matrix
    adjacency = lil_matrix((n_songs, n_songs), dtype=np.int32)

    # Second pass: count co-occurrences
    for i, playlist in enumerate(playlists):
        tracks = playlist.get("tracks", [])
        song_indices = [
            song_to_idx[tuple(track)]
            for track in tracks
            if isinstance(track, list) and len(track) == 2
        ]

        # For each pair of songs in this playlist, increment their co-occurrence
        for i_idx in range(len(song_indices)):
            for j_idx in range(i_idx, len(song_indices)):
                song_i = song_indices[i_idx]
                song_j = song_indices[j_idx]
                adjacency[song_i, song_j] += 1
                if song_i != song_j:
                    adjacency[song_j, song_i] += 1

        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{len(playlists)} playlists...")

    # Convert to CSR format for efficient operations
    adjacency_csr = adjacency.tocsr()

    # Print statistics
    total_edges = adjacency_csr.nnz
    print(f"\nAdjacency matrix statistics:")
    print(f"  Shape: {adjacency_csr.shape}")
    print(f"  Non-zero entries: {total_edges}")
    print(f"  Density: {total_edges / (n_songs * n_songs) * 100:.4f}%")

    return adjacency_csr, song_to_idx, idx_to_song


def _recluster_oversized(
    adjacency_matrix,
    cluster_labels,
    max_cluster_size,
    method,
    resolution,
    recluster_resolution,
    n_clusters,
    depth,
):
    """
    Recursively re-cluster clusters that exceed max_cluster_size.

    Args:
        adjacency_matrix: full sparse adjacency matrix
        cluster_labels: current cluster assignments
        max_cluster_size: threshold for re-clustering
        method: clustering method to use
        resolution: Louvain resolution parameter
        n_clusters: number of clusters for spectral/agglomerative
        depth: current recursion depth

    Returns:
        Updated cluster_labels with oversized clusters split
    """

    indent = "  " * (depth + 1)
    unique, counts = np.unique(cluster_labels, return_counts=True)
    oversized = unique[counts > max_cluster_size]

    if len(oversized) == 0:
        return cluster_labels

    # Create a mapping for new cluster IDs
    new_cluster_id_counter = cluster_labels.max() + 1
    new_cluster_labels = cluster_labels.copy()

    for oversized_cluster_id in oversized:
        cluster_indices = np.where(cluster_labels == oversized_cluster_id)[0]
        cluster_size = len(cluster_indices)

        print(
            f"{indent}Re-clustering oversized cluster {oversized_cluster_id} (size: {cluster_size})"
        )

        # Extract sub-matrix for this cluster
        cluster_adjacency = adjacency_matrix[cluster_indices][:, cluster_indices]

        # Determine number of sub-clusters
        # Aim for clusters of roughly max_cluster_size
        sub_n_clusters = max(
            2, (cluster_size + max_cluster_size - 1) // max_cluster_size
        )

        # Recursively cluster the oversized cluster
        sub_labels = cluster_tracks(
            cluster_adjacency,
            n_clusters=sub_n_clusters,
            method=method,
            resolution=resolution,
            recluster_resolution=recluster_resolution,
            max_cluster_size=max_cluster_size,
            depth=depth + 1,
        )

        # Map sub-cluster labels back to original indices and assign new IDs
        for local_idx, global_idx in enumerate(cluster_indices):
            sub_cluster_id = sub_labels[local_idx]
            # Create unique global cluster IDs
            new_global_cluster_id = new_cluster_id_counter + sub_cluster_id
            new_cluster_labels[global_idx] = new_global_cluster_id

        new_cluster_id_counter += sub_labels.max() + 1

    # Print final distribution
    unique, counts = np.unique(new_cluster_labels, return_counts=True)
    print(f"\n{indent}After re-clustering:")
    print(f"{indent}  Clusters created: {len(unique)}")
    print(f"{indent}  Min cluster size: {counts.min()}")
    print(f"{indent}  Max cluster size: {counts.max()}")
    print(f"{indent}  Mean cluster size: {counts.mean():.1f}")

    return new_cluster_labels


def _merge_undersized(adjacency_matrix, cluster_labels, min_cluster_size, depth):
    """
    Merge clusters that are smaller than min_cluster_size with their nearest neighbors.

    Args:
        adjacency_matrix: full sparse adjacency matrix
        cluster_labels: current cluster assignments
        min_cluster_size: threshold for merging
        depth: current recursion depth

    Returns:
        Updated cluster_labels with undersized clusters merged
    """

    indent = "  " * (depth + 1)
    unique, counts = np.unique(cluster_labels, return_counts=True)
    undersized = unique[counts < min_cluster_size]

    if len(undersized) == 0:
        return cluster_labels

    print(
        f"{indent}Found {len(undersized)} clusters smaller than min size of {min_cluster_size}. Merging..."
    )
    new_cluster_labels = cluster_labels.copy()

    for undersized_cluster_id in undersized:
        cluster_indices = np.where(cluster_labels == undersized_cluster_id)[0]
        cluster_size = len(cluster_indices)

        # Find the cluster with the most connections to this one
        best_neighbor_cluster = None
        best_connection_count = 0

        for other_cluster_id in unique:
            if other_cluster_id == undersized_cluster_id:
                continue

            other_indices = np.where(cluster_labels == other_cluster_id)[0]
            # Count connections between this cluster and the other cluster
            connection_count = adjacency_matrix[cluster_indices][:, other_indices].sum()

            if connection_count > best_connection_count:
                best_connection_count = connection_count
                best_neighbor_cluster = other_cluster_id

        if best_neighbor_cluster is not None:
            print(
                f"{indent}  Merging cluster {undersized_cluster_id} (size: {cluster_size}) with cluster {best_neighbor_cluster}"
            )
            new_cluster_labels[cluster_indices] = best_neighbor_cluster
        else:
            print(
                f"{indent}  Could not find neighbor for cluster {undersized_cluster_id}, keeping as is"
            )

    return new_cluster_labels


def _renumber_clusters_contiguous(cluster_labels):
    """
    Renumber clusters to be contiguous starting from 1.

    Args:
        cluster_labels: current cluster assignments

    Returns:
        Renumbered cluster_labels
    """

    unique_clusters = np.unique(cluster_labels)
    mapping = {old_id: new_id for new_id, old_id in enumerate(unique_clusters, start=1)}
    renumbered = np.array([mapping[label] for label in cluster_labels])
    return renumbered


def cluster_tracks(
    adjacency_matrix,
    n_clusters=50,
    method="spectral",
    resolution=1.0,
    recluster_resolution=0.5,
    max_cluster_size=None,
    min_cluster_size=None,
    depth=0,
):
    """
    Cluster tracks based on the co-occurrence adjacency matrix.

    Args:
        adjacency_matrix: sparse matrix of co-occurrences
        n_clusters: number of clusters to create
        method: clustering method ('spectral', 'agglomerative', or 'louvain')
        resolution: Louvain resolution parameter (higher -> more clusters)
        max_cluster_size: if set, re-cluster any cluster larger than this size
        min_cluster_size: if set, merge any cluster smaller than this size with nearest neighbor
        depth: recursion depth (for logging purposes)

    Returns:
        cluster_labels: array of cluster assignments for each song
    """

    indent = "  " * depth
    print(f"{indent}Clustering tracks using {method} clustering...")
    if method != "louvain":
        print(f"{indent}Target clusters: {n_clusters}")
    else:
        print(f"{indent}Louvain resolution: {resolution}")

    if method == "spectral":
        # Spectral clustering works well with similarity/adjacency matrices
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            assign_labels="kmeans",
            random_state=42,
            n_jobs=-1,
        )

        # Convert to dense affinity matrix (normalized by row max for stability)
        # For very large matrices, this might need to be done differently
        affinity = adjacency_matrix.toarray()
        row_sums = affinity.sum(axis=1)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        affinity = affinity / row_sums[:, np.newaxis]

        cluster_labels = clustering.fit_predict(affinity)

    elif method == "agglomerative":
        # Agglomerative clustering with connectivity
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters, linkage="average", connectivity=adjacency_matrix
        )
        cluster_labels = clustering.fit_predict(adjacency_matrix.toarray())

    elif method == "louvain":
        if community_louvain is None:
            raise ImportError(
                "python-louvain is required for method='louvain'. "
                "Install with: pip install python-louvain"
            ) from _louvain_import_error

        # Build an undirected weighted NetworkX graph
        coo = adjacency_matrix.tocoo()
        G = nx.Graph()
        for u, v, w in zip(coo.row, coo.col, coo.data):
            if u == v:
                continue
            if w <= 0:
                continue
            # add_edge merges parallel edges by summing weight; set directly
            G.add_edge(u, v, weight=float(w))

        # Run Louvain community detection
        partition = community_louvain.best_partition(
            G, weight="weight", resolution=resolution, random_state=42
        )
        cluster_labels = np.array(
            [partition.get(i, -1) for i in range(adjacency_matrix.shape[0])]
        )

    else:
        raise ValueError(f"Unknown clustering method: {method}")

    # Print cluster distribution
    unique, counts = np.unique(cluster_labels, return_counts=True)
    print(f"{indent}Cluster distribution:")
    print(f"{indent}  Clusters created: {len(unique)}")
    print(f"{indent}  Min cluster size: {counts.min()}")
    print(f"{indent}  Max cluster size: {counts.max()}")
    print(f"{indent}  Mean cluster size: {counts.mean():.1f}")

    # Check if any clusters exceed max_cluster_size and re-cluster if needed
    if max_cluster_size is not None and counts.max() > max_cluster_size:
        print(
            f"\n{indent}Found clusters exceeding max size of {max_cluster_size}. Re-clustering oversized clusters..."
        )
        cluster_labels = _recluster_oversized(
            adjacency_matrix,
            cluster_labels,
            max_cluster_size,
            method,
            resolution,
            recluster_resolution,
            n_clusters,
            depth,
        )

    # Check if any clusters are below min_cluster_size and merge if needed (only at top level, depth=0)
    if min_cluster_size is not None and depth == 0:
        cluster_labels = _merge_undersized(
            adjacency_matrix, cluster_labels, min_cluster_size, depth
        )

    # Renumber clusters to be contiguous from 1 (only at top level, depth=0)
    if depth == 0:
        print(f"\n{indent}Renumbering clusters to be contiguous from 1...")
        cluster_labels = _renumber_clusters_contiguous(cluster_labels)
        unique, counts = np.unique(cluster_labels, return_counts=True)
        print(f"{indent}Final cluster distribution:")
        print(f"{indent}  Clusters created: {len(unique)}")
        print(f"{indent}  Min cluster size: {counts.min()}")
        print(f"{indent}  Max cluster size: {counts.max()}")
        print(f"{indent}  Mean cluster size: {counts.mean():.1f}")

    return cluster_labels


def save_clusters(cluster_labels, idx_to_song, output_path):
    """
    Save the clustering results to a CSV file.

    CSV format: song_title, song_artist, cluster_id
    """

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["song_title", "song_artist", "cluster_id"])

        for idx in range(len(cluster_labels)):
            title, artist = idx_to_song[idx]
            cluster_id = cluster_labels[idx]
            writer.writerow([title, artist, cluster_id])

    print(f"\nClusters saved to: {output_path}")


def analyze_cluster(
    cluster_id, cluster_labels, idx_to_song, adjacency_matrix, top_n=10
):
    """
    Analyze a specific cluster by showing the most connected songs.
    """

    # Get indices of songs in this cluster
    cluster_indices = np.where(cluster_labels == cluster_id)[0]

    print(f"\n=== Cluster {cluster_id} ({len(cluster_indices)} songs) ===")

    # Calculate total connections for each song in the cluster
    song_connections = []
    for idx in cluster_indices:
        # Sum of connections to other songs in the same cluster
        connections = adjacency_matrix[idx, cluster_indices].sum()
        song_connections.append((idx, connections, idx_to_song[idx]))

    # Sort by number of connections
    song_connections.sort(key=lambda x: x[1], reverse=True)

    # Print top connected songs
    print(f"\nTop {min(top_n, len(song_connections))} most connected songs:")
    for i, (idx, connections, (title, artist)) in enumerate(song_connections[:top_n]):
        print(f"  {i+1}. {title} - {artist} ({int(connections)} connections)")


if __name__ == "__main__":
    # Load filtered playlists
    print("Loading filtered playlists...")
    playlists = load_filtered_playlists(filtered_path)
    print(f"Loaded {len(playlists)} playlists\n")

    # Build co-occurrence matrix
    print("Building co-occurrence matrix...")
    adjacency_matrix, song_to_idx, idx_to_song = build_cooccurrence_matrix(playlists)

    # Cluster tracks (use Louvain by default; set method/n_clusters as needed)
    method = "louvain"
    n_clusters = 50  # Used only for spectral/agglomerative
    max_cluster_size = 200  # Re-cluster any cluster larger than this
    min_cluster_size = 10  # Merge any cluster smaller than this with nearest neighbor
    cluster_labels = cluster_tracks(
        adjacency_matrix,
        n_clusters=n_clusters,
        method=method,
        resolution=2,
        recluster_resolution=0.7,
        max_cluster_size=max_cluster_size,
        min_cluster_size=min_cluster_size,
    )

    # Save results
    output_path = os.path.join(base_dir, "..", "data", "song_clusters.csv")
    save_clusters(cluster_labels, idx_to_song, output_path)

    # Analyze a few example clusters
    print("\n" + "=" * 60)
    print("Sample cluster analysis:")
    print("=" * 60)
    unique_clusters = np.unique(cluster_labels)
    for cluster_id in unique_clusters[: min(3, len(unique_clusters))]:
        analyze_cluster(cluster_id, cluster_labels, idx_to_song, adjacency_matrix)
