import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from .base_agent import BaseAgent
import json


class SegmentationAgent(BaseAgent):
    """
    Performs behavioral clustering and customer segmentation.
    
    Features:
    - Automated K-Means and DBSCAN clustering
    - Silhouette & Davies-Bouldin scoring for optimal k selection
    - PCA-based 2D visualization
    - Cluster profiling (statistics per segment)
    - Integration ready for LLM-based persona generation
    """

    def __init__(self, n_clusters_range=(2, 10), algorithm="kmeans", eps=0.5, 
                 min_samples=5, random_state=42, scaling=True):
        """
        Initialize SegmentationAgent.
        
        Args:
            n_clusters_range: Tuple (min, max) for K-Means testing
            algorithm: "kmeans" or "dbscan"
            eps: DBSCAN epsilon parameter
            min_samples: DBSCAN min_samples parameter
            random_state: Random seed for reproducibility
            scaling: Whether to scale features (recommended)
        """
        super().__init__("SegmentationAgent")
        self.n_clusters_range = n_clusters_range
        self.algorithm = algorithm
        self.eps = eps
        self.min_samples = min_samples
        self.random_state = random_state
        self.scaling = scaling
        self.scaler = StandardScaler() if scaling else None
        self.pca = None
        self.model = None
        self.segmentation_data = {}


    def _select_numeric_features(self, df):
        """Select only numeric columns for clustering."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            raise ValueError("No numeric columns found for clustering")
        return df[numeric_cols].copy()

    def _scale_features(self, df):
        """Scale features using StandardScaler."""
        scaled_values = self.scaler.fit_transform(df)
        scaled_df = pd.DataFrame(scaled_values, columns=df.columns, index=df.index)
        return scaled_df

    def _kmeans_clustering(self, df):
        """
        Perform K-Means clustering with automatic k selection.
        
        Uses silhouette score and Davies-Bouldin index to find optimal k.
        """
        min_k, max_k = self.n_clusters_range
        silhouette_scores = []
        davies_bouldin_scores = []
        calinski_scores = []
        models = []

        for k in range(min_k, max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            labels = kmeans.fit_predict(df)

            silhouette = silhouette_score(df, labels)
            davies_bouldin = davies_bouldin_score(df, labels)
            calinski = calinski_harabasz_score(df, labels)

            silhouette_scores.append(silhouette)
            davies_bouldin_scores.append(davies_bouldin)
            calinski_scores.append(calinski)
            models.append(kmeans)

            self.log(f"k={k}: Silhouette={silhouette:.3f}, Davies-Bouldin={davies_bouldin:.3f}")

        # Optimal k: highest silhouette score
        optimal_idx = np.argmax(silhouette_scores)
        optimal_k = min_k + optimal_idx
        optimal_model = models[optimal_idx]

        self.model = optimal_model
        labels = optimal_model.labels_

        return {
            "n_clusters": optimal_k,
            "labels": labels,
            "silhouette_score": float(silhouette_scores[optimal_idx]),
            "davies_bouldin_score": float(davies_bouldin_scores[optimal_idx]),
            "calinski_harabasz_score": float(calinski_scores[optimal_idx]),
            "silhouette_scores_by_k": [float(s) for s in silhouette_scores],
            "davies_bouldin_scores_by_k": [float(s) for s in davies_bouldin_scores],
        }

    def _dbscan_clustering(self, df):
        """
        Perform DBSCAN clustering.
        
        Note: eps and min_samples are pre-configured.
        """
        dbscan = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = dbscan.fit_predict(df)

        # Calculate silhouette score (excluding noise points labeled as -1)
        unique_labels = set(labels)
        if len(unique_labels) > 1 and -1 not in unique_labels:
            silhouette = silhouette_score(df, labels)
        else:
            silhouette = None

        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(labels).count(-1)

        self.log(f"DBSCAN: {n_clusters} clusters found, {n_noise} noise points")

        self.model = dbscan
        return {
            "n_clusters": n_clusters,
            "labels": labels,
            "silhouette_score": float(silhouette) if silhouette else None,
            "n_noise_points": int(n_noise),
        }

    def _generate_pca_visualization(self, df):
        """
        Reduce to 2D using PCA for visualization.
        
        Returns:
            Dict with PCA coordinates and explained variance
        """
        pca = PCA(n_components=2)
        pca_coords = pca.fit_transform(df)

        self.pca = pca

        return {
            "coordinates": pca_coords.tolist(),
            "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
            "total_variance_explained": float(sum(pca.explained_variance_ratio_)),
        }

    def _profile_clusters(self, original_df, labels):
        """
        Generate cluster profiles: statistics for each cluster.
        
        Returns:
            Dict with per-cluster statistics
        """
        profiles = {}

        for cluster_id in np.unique(labels):
            mask = labels == cluster_id
            cluster_data = original_df[mask]

            profile = {
                "cluster_id": int(cluster_id),
                "size": int(mask.sum()),
                "percentage": float((mask.sum() / len(original_df)) * 100),
                "features": {},
            }

            # Numeric statistics
            for col in cluster_data.select_dtypes(include=[np.number]).columns:
                col_data = cluster_data[col]
                profile["features"][col] = {
                    "mean": float(col_data.mean()),
                    "median": float(col_data.median()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "q25": float(col_data.quantile(0.25)),
                    "q75": float(col_data.quantile(0.75)),
                }

            profiles[f"cluster_{cluster_id}"] = profile

        return profiles

    def _prepare_persona_input(self, cluster_profiles):
        """
        Format cluster profiles for LLM persona generation.
        
        Returns:
            Dict formatted for LLM consumption
        """
        persona_input = {
            "clusters": [],
            "summary": f"Generated {len(cluster_profiles)} customer segments",
        }

        for cluster_key, profile in cluster_profiles.items():
            cluster_summary = {
                "cluster_id": profile["cluster_id"],
                "size": profile["size"],
                "size_percentage": profile["percentage"],
                "characteristics": self._summarize_features(profile["features"]),
            }
            persona_input["clusters"].append(cluster_summary)

        return persona_input

    def _summarize_features(self, features):
        """
        Create human-readable feature summary for LLM.
        
        Returns:
            List of feature descriptions
        """
        summaries = []
        for feature_name, stats in features.items():
            mean = stats["mean"]
            summary = {
                "feature": feature_name,
                "mean": round(mean, 2),
                "range": f"{stats['min']:.2f} - {stats['max']:.2f}",
                "distribution": "tight" if stats["std"] < (stats["max"] - stats["min"]) * 0.1 
                               else "moderate" if stats["std"] < (stats["max"] - stats["min"]) * 0.25
                               else "wide",
            }
            summaries.append(summary)
        return summaries

    def get_cluster_assignments(self):
        """Return DataFrame with original data and cluster assignments."""
        if self.model is None:
            raise ValueError("Must run clustering first")
        return self.segmentation_data.get("labels")

    def get_visualization_data(self):
        """Return PCA coordinates and labels for visualization."""
        if self.pca is None:
            raise ValueError("Must run clustering first")

        return {
            "pca_coords": self.segmentation_data["pca_data"]["coordinates"],
            "labels": self.segmentation_data["labels"].tolist(),
            "n_clusters": self.segmentation_data["n_clusters"],
            "variance_explained": self.segmentation_data["pca_data"]["total_variance_explained"],
        }

    def get_cluster_summary(self):
        """Return summary statistics for all clusters."""
        return {
            "algorithm": self.segmentation_data["algorithm"],
            "n_clusters": self.segmentation_data["n_clusters"],
            "silhouette_score": self.segmentation_data.get("silhouette_score"),
            "davies_bouldin_score": self.segmentation_data.get("davies_bouldin_score"),
            "profiles": self.segmentation_data["cluster_profiles"],
        }
    
    def run(self, context):
        """
        Execute behavioral clustering pipeline.
        
        Args:
            context: Dict with "data" and optionally "clean_data"
            
        Returns:
            context: Updated with segmentation results
        """
        # Use clean data if available, else raw data
        df = context.get("clean_data", context.get("data")).copy()
        self.log(f"Starting segmentation with {len(df)} records, {len(df.columns)} features")

        # Step 1: Select numeric features for clustering
        numeric_df = self._select_numeric_features(df)
        self.log(f"Selected {len(numeric_df.columns)} numeric features for clustering")

        # Step 2: Scale features
        if self.scaling:
            scaled_df = self._scale_features(numeric_df)
        else:
            scaled_df = numeric_df

        # Step 3: Perform clustering
        if self.algorithm.lower() == "kmeans":
            segmentation_result = self._kmeans_clustering(scaled_df)
        elif self.algorithm.lower() == "dbscan":
            segmentation_result = self._dbscan_clustering(scaled_df)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        # Step 4: Generate PCA for visualization
        pca_result = self._generate_pca_visualization(scaled_df)

        # Step 5: Profile clusters
        cluster_profiles = self._profile_clusters(df, segmentation_result["labels"])

        # Step 6: Prepare data for persona generation (for LLM)
        persona_input = self._prepare_persona_input(cluster_profiles)

        # Store results in context
        self.segmentation_data = {
            "algorithm": self.algorithm,
            "n_clusters": segmentation_result["n_clusters"],
            "labels": segmentation_result["labels"],
            "silhouette_score": segmentation_result.get("silhouette_score"),
            "davies_bouldin_score": segmentation_result.get("davies_bouldin_score"),
            "calinski_harabasz_score": segmentation_result.get("calinski_harabasz_score"),
            "cluster_profiles": cluster_profiles,
            "pca_data": pca_result,
            "persona_input": persona_input,
            "original_features": numeric_df.columns.tolist(),
            "n_records": len(df),
        }

        context["segmentation_result"] = self.segmentation_data
        context["customer_segments"] = segmentation_result["labels"]

        self.log(f"Segmentation complete: {segmentation_result['n_clusters']} clusters identified")
        return context