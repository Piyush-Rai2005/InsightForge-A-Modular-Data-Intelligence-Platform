import os
import matplotlib.pyplot as plt
import seaborn as sns
from .base_agent import BaseAgent

class FeatureAgent(BaseAgent):
    """Generates correlation heatmap for top 10 features most correlated with target."""

    def __init__(self):
        super().__init__("FeatureAgent")

    def run(self, context):
        df = context["clean_data"]
        target = context["target_column"]
        os.makedirs("outputs", exist_ok=True)

        if target not in df.columns:
            self.log("Target column missing in cleaned data; skipping feature heatmap.")
            return context

        num_df = df.select_dtypes(include=["float", "int"])
        if target not in num_df.columns:
            self.log("Target is non-numeric; correlation heatmap limited to numeric proxy.")
        try:
            corrs = num_df.corr()[target].drop(target).abs().sort_values(ascending=False)
            top_feats = list(corrs.head(10).index)
            cols = [c for c in [target] + top_feats if c in num_df.columns]
            sub_corr = num_df[cols].corr()
        except Exception as e:
            self.log(f"Correlation computation failed: {e}")
            return context

        plt.figure(figsize=(8, 6), dpi=200)
        sns.heatmap(sub_corr, cmap="Blues", linewidths=0.3, linecolor="white", annot=False)
        plt.title("Correlation Heatmap (Top 10 Features)")
        plt.xticks(rotation=45, ha="right", fontsize=7)
        plt.yticks(fontsize=7)
        plt.tight_layout()
        heat_path = "outputs/correlation_heatmap.png"
        plt.savefig(heat_path)
        plt.close()

        context["corr_plot"] = heat_path
        return context