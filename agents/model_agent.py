import os
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from .base_agent import BaseAgent

class ModelAgent(BaseAgent):
    """Trains multiple models and creates comparison bar chart."""

    def __init__(self):
        super().__init__("ModelAgent")

    def run(self, context):
        df = context["clean_data"]
        target = context["target_column"]

        if target not in df.columns or df[target].nunique() < 2:
            self.log("❗ Only one target class detected or target missing — skipping model training.")
            context["model_scores"] = None
            context["best_model_name"] = None
            context["best_model_accuracy"] = None
            return context

        X = df.drop(columns=[target])
        y = df[target]

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        models = {
            "Logistic Regression": LogisticRegression(max_iter=2000),
            "Random Forest": RandomForestClassifier(),
            "Gradient Boosting": GradientBoostingClassifier(),
        }

        scores = {}
        best_model = None
        best_model_name = None
        best_score = -1.0

        for name, model in models.items():
            model.fit(X_train, y_train)
            score = model.score(X_test, y_test)
            scores[name] = score
            if score > best_score:
                best_score = score
                best_model = model
                best_model_name = name

        context["model_scores"] = scores
        context["best_model"] = best_model
        context["best_model_name"] = best_model_name
        context["best_model_accuracy"] = best_score
        context["X_test"] = X_test
        context["y_test"] = y_test

        os.makedirs("outputs", exist_ok=True)
        plt.figure(figsize=(6, 4), dpi=200)
        names = list(scores.keys())
        vals = list(scores.values())
        plt.bar(names, vals)
        plt.title("Model Accuracy Comparison")
        plt.ylabel("Accuracy")
        plt.ylim(0, 1.0)
        plt.xticks(rotation=20)
        plt.tight_layout()
        bar_path = "outputs/model_comparison_bar.png"
        plt.savefig(bar_path)
        plt.close()

        context["model_bar"] = bar_path
        return context