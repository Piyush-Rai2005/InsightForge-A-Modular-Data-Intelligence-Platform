import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    RandomForestRegressor, GradientBoostingRegressor,
)
from sklearn.metrics import r2_score, mean_absolute_error
from .base_agent import BaseAgent

class ModelAgent(BaseAgent):
    """Trains multiple models — auto-selects classification or regression."""

    def __init__(self):
        super().__init__("ModelAgent")

    def run(self, context):
        # Skip ML if TargetAgent determined it's not appropriate
        if context.get("skip_ml"):
            self.log(f"Skipping ML: {context.get('skip_ml_reason', 'No target')}")
            context["model_scores"] = None
            context["best_model_name"] = None
            context["best_model_accuracy"] = None
            return context

        df = context["clean_data"]
        target = context.get("target_column")

        if not target or target not in df.columns or df[target].nunique() < 2:
            self.log("No valid target -- skipping model training.")
            context["model_scores"] = None
            context["best_model_name"] = None
            context["best_model_accuracy"] = None
            return context

        X = df.drop(columns=[target])
        y = df[target]

        MAX_ROWS = 2000
        if len(X) > MAX_ROWS:
            self.log(f"Dataset too large for fast insights. Sampling down from {len(X)} to {MAX_ROWS} rows for model training...")
            X = X.sample(n=MAX_ROWS, random_state=42)
            y = y.loc[X.index]

        # ── Determine task type ─────────────────────────────────────────────
        task_type = context.get("task_type", "classification")
        self.log(f"Training models for: {task_type}")

        try:
            if task_type == "classification":
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42, stratify=y
                )
            else:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        # ── Pick models based on task type ──────────────────────────────────
        if task_type == "regression":
            models = {
                "Linear Regression": LinearRegression(),
                "Ridge Regression": Ridge(alpha=1.0),
                "Random Forest": RandomForestRegressor(n_estimators=50, random_state=42),
                "Gradient Boosting": GradientBoostingRegressor(n_estimators=50, random_state=42),
            }
        else:
            models = {
                "Logistic Regression": LogisticRegression(solver='saga', max_iter=3000, tol=1e-3),
                "Random Forest": RandomForestClassifier(n_estimators=50, random_state=42),
                "Gradient Boosting": GradientBoostingClassifier(n_estimators=50, random_state=42),
            }

        scores = {}
        best_model = None
        best_model_name = None
        best_score = -float("inf")

        for name, model in models.items():
            try:
                model.fit(X_train, y_train)
                if task_type == "regression":
                    score = r2_score(y_test, model.predict(X_test))
                else:
                    score = model.score(X_test, y_test)
                scores[name] = score
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_model_name = name
            except Exception as e:
                self.log(f"Model '{name}' failed: {e}")

        if not scores:
            self.log("All models failed -- skipping.")
            context["model_scores"] = None
            context["best_model_name"] = None
            context["best_model_accuracy"] = None
            return context

        context["model_scores"] = scores
        context["best_model"] = best_model
        context["best_model_name"] = best_model_name
        context["best_model_accuracy"] = best_score
        context["task_type"] = task_type
        context["X_test"] = X_test
        context["y_test"] = y_test

        # ── Leakage detection (classification only) ─────────────────────────
        if task_type == "classification" and best_score > 0.97:
            leakage_warnings = context.get("leakage_warnings", [])
            leakage_warnings.append(
                f"Best model accuracy is {best_score*100:.1f}% -- suspiciously high. "
                f"This likely indicates data leakage: a feature directly encodes the target '{target}'. "
                f"Verify that no input feature is derived from or equivalent to the target."
            )
            context["leakage_warnings"] = leakage_warnings
            self.log(f"LEAKAGE WARNING: {best_model_name} scored {best_score} -- likely data leakage")

        # ── Plotly JSON spec ────────────────────────────────────────────────
        metric_label = "R² Score" if task_type == "regression" else "Accuracy"
        names = list(scores.keys())
        vals = [round(v, 4) for v in scores.values()]
        colors = ["#63d396" if n == best_model_name else "#4a9ed6" for n in names]

        context["model_bar_plotly"] = {
            "data": [{
                "type": "bar",
                "x": names,
                "y": vals,
                "marker": {
                    "color": colors,
                    "line": {"color": "rgba(255,255,255,0.1)", "width": 1},
                },
                "text": [f"{v*100:.1f}%" if task_type == "classification" else f"{v:.3f}" for v in vals],
                "textposition": "outside",
                "textfont": {"color": "#f0f2f5"},
                "hovertemplate": f"%{{x}}: %{{y:.4f}}<extra>{metric_label}</extra>",
            }],
            "layout": {
                "title": {"text": f"Model {metric_label} Comparison", "font": {"color": "#f0f2f5", "size": 16}},
                "paper_bgcolor": "transparent",
                "plot_bgcolor": "transparent",
                "font": {"color": "#a0a0a0"},
                "xaxis": {"gridcolor": "rgba(255,255,255,0.05)"},
                "yaxis": {"title": metric_label, "gridcolor": "rgba(255,255,255,0.05)"},
                "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
            }
        }

        # ── PNG fallback ────────────────────────────────────────────────────
        os.makedirs("outputs", exist_ok=True)
        plt.figure(figsize=(6, 4), dpi=200)
        plt.bar(names, list(scores.values()))
        plt.title(f"Model {metric_label} Comparison")
        plt.ylabel(metric_label)
        if task_type == "classification":
            plt.ylim(0, 1.0)
        plt.xticks(rotation=20)
        plt.tight_layout()
        bar_path = "outputs/model_comparison_bar.png"
        plt.savefig(bar_path)
        plt.close()

        context["model_bar"] = bar_path
        return context