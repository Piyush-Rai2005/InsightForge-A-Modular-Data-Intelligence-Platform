import os
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score
from .base_agent import BaseAgent

class EvaluationAgent(BaseAgent):
    """Creates target distribution, confusion matrix and ROC curve (if binary)."""

    def __init__(self):
        super().__init__("EvaluationAgent")

    def run(self, context):
        if context.get("skip_ml") or context.get("model_scores") is None:
            self.log("Skipping evaluation -- ML was skipped or no trained models.")
            return context

        os.makedirs("outputs", exist_ok=True)

        best_model = context["best_model"]
        X_test = context["X_test"]
        y_test = context["y_test"]
        task_type = context.get("task_type", "classification")
        preds = best_model.predict(X_test)

        # 1. Target distribution
        plt.figure(figsize=(4, 3), dpi=200)
        if task_type == "regression":
            sns.histplot(x=y_test, kde=True, color="#4a9ed6")
        else:
            sns.countplot(x=y_test)
        plt.title("Target Distribution")
        plt.tight_layout()
        target_path = "outputs/target_distribution.png"
        plt.savefig(target_path)
        plt.close()

        # 2. Performance Plot (Confusion Matrix OR Predicted vs Actual)
        plt.figure(figsize=(4, 3), dpi=200)
        if task_type == "regression":
            # Scatter plot for regression
            sns.scatterplot(x=y_test, y=preds, alpha=0.5, color="#4a9ed6")
            # Ideal y=x line
            min_val = min(y_test.min(), preds.min())
            max_val = max(y_test.max(), preds.max())
            plt.plot([min_val, max_val], [min_val, max_val], 'k--', color="grey", alpha=0.7)
            plt.title("Predicted vs Actual")
            plt.xlabel("Actual Value")
            plt.ylabel("Predicted Value")
            cm_path = "outputs/predicted_vs_actual.png"
        else:
            # Confusion matrix for classification
            cm = confusion_matrix(y_test, preds)
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
            plt.title("Confusion Matrix")
            plt.ylabel("True Label")
            plt.xlabel("Predicted Label")
            cm_path = "outputs/confusion_matrix.png"
        
        plt.tight_layout()
        plt.savefig(cm_path)
        plt.close()

        # 3. ROC curve (only if classification, binary, and model has predict_proba)
        roc_path = None
        if task_type == "classification" and hasattr(best_model, "predict_proba") and y_test.nunique() == 2:
            probs = best_model.predict_proba(X_test)[:, 1]
            fpr, tpr, _ = roc_curve(y_test, probs)
            auc = roc_auc_score(y_test, probs)

            plt.figure(figsize=(4, 3), dpi=200)
            try:
                auc_str = f"{float(auc):.2f}"
            except (ValueError, TypeError):
                auc_str = str(auc)
            plt.plot(fpr, tpr, label=f"AUC = {auc_str}")
            plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
            plt.title("ROC Curve")
            plt.xlabel("False Positive Rate")
            plt.ylabel("True Positive Rate")
            plt.legend()
            plt.tight_layout()
            roc_path = "outputs/roc_curve.png"
            plt.savefig(roc_path)
            plt.close()

        context["target_plot"] = target_path
        context["conf_matrix"] = cm_path
        context["roc_curve"] = roc_path
        return context