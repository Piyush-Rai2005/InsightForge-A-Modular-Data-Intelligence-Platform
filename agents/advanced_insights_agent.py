from typing import Any, Dict
import numpy as np
import pandas as pd
import polars as pl
from .base_agent import BaseAgent


class AdvancedInsightsAgent(BaseAgent):
    """Generates advanced business intelligence, temporal trends, anomalies, and what-if scenarios."""

    def __init__(self):
        super().__init__("AdvancedInsightsAgent")
        self.insights_report = {}

    def analyze_temporal_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Identify time-series patterns, growth trajectories, and trends.
        """
        temporal_insights = {
            "has_time_series": False,
            "date_column": None,
            "growth_metrics": {},
            "trends": []
        }

        # Identify potential datetime columns
        datetime_cols = df.select_dtypes(include=['datetime64', 'datetimetz']).columns.tolist()
        
        # Fallback: check if any object column looks like a date (simplified check)
        if not datetime_cols:
            for col in df.select_dtypes(include=['object']).columns:
                if 'date' in col.lower() or 'time' in col.lower():
                    try:
                        df[col] = pd.to_datetime(df[col])
                        datetime_cols.append(col)
                        break
                    except (ValueError, TypeError):
                        continue

        if not datetime_cols:
            return temporal_insights

        temporal_insights["has_time_series"] = True
        date_col = datetime_cols[0]
        temporal_insights["date_column"] = date_col

        # Sort by date for accurate time-series analysis
        df_sorted = df.sort_values(by=date_col).set_index(date_col)
        numeric_cols = df_sorted.select_dtypes(include=[np.number]).columns

        if len(numeric_cols) > 0:
            target_metric = numeric_cols[0] # Pick the first numeric col as default metric
            
            # Resample by month to calculate Month-over-Month (MoM) growth
            monthly_data = df_sorted[target_metric].resample('ME').sum()
            if len(monthly_data) > 1:
                mom_growth = monthly_data.pct_change().dropna() * 100
                latest_growth = mom_growth.iloc[-1]
                
                temporal_insights["growth_metrics"]["latest_mom_growth"] = round(latest_growth, 2)
                
                if latest_growth > 0:
                    temporal_insights["trends"].append(
                        f"Positive growth trajectory: {target_metric} grew by {latest_growth:.1f}% in the most recent month."
                    )
                else:
                    temporal_insights["trends"].append(
                        f"Trend Reversal Alert: {target_metric} declined by {abs(latest_growth):.1f}% in the most recent month."
                    )

        return temporal_insights

    def detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect statistical outliers (3 standard deviations) and contextual anomalies.
        """
        anomaly_insights = {
            "total_outliers_found": 0,
            "column_anomalies": {},
            "top_alerts": []
        }

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            # Calculate Z-scores for 3 standard deviations rule
            mean = df[col].mean()
            std = df[col].std()
            
            if std == 0 or pd.isna(std):
                continue
                
            z_scores = (df[col] - mean) / std
            outliers = df[np.abs(z_scores) > 3]
            outlier_count = len(outliers)

            if outlier_count > 0:
                anomaly_insights["total_outliers_found"] += outlier_count
                anomaly_insights["column_anomalies"][col] = outlier_count
                
                # Contextual alert generation
                max_val = outliers[col].max()
                anomaly_insights["top_alerts"].append(
                    f"Statistical Outlier in '{col}': {outlier_count} instances exceeded normal thresholds (e.g., extreme value of {max_val:.2f})."
                )

        # Sort alerts to keep the top 5 most severe
        anomaly_insights["top_alerts"] = anomaly_insights["top_alerts"][:5]

        return anomaly_insights

    def sensitivity_analysis(self, df: pd.DataFrame, target_col: str = None) -> Dict[str, Any]:
        """
        Perform What-If scenario simulations and user-friendly feature importance.
        """
        sensitivity_insights = {
            "target_analyzed": target_col,
            "top_drivers": [],
            "simulations": []
        }

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not target_col or target_col not in numeric_cols:
            if len(numeric_cols) > 0:
                target_col = numeric_cols[-1] # Default to last numeric column
                sensitivity_insights["target_analyzed"] = target_col
            else:
                return sensitivity_insights

        numeric_cols.remove(target_col)
        
        if not numeric_cols:
            return sensitivity_insights

        # Calculate feature importance via correlation
        correlations = df[numeric_cols].corrwith(df[target_col]).dropna()
        top_features = correlations.abs().sort_values(ascending=False).head(3)

        for feature, abs_corr in top_features.items():
            actual_corr = correlations[feature]
            direction = "increases" if actual_corr > 0 else "decreases"
            
            # User-friendly feature importance
            sensitivity_insights["top_drivers"].append(
                f"'{feature}' (Impact Strength: {abs_corr:.2f})"
            )

            # Scenario Simulation (What-if)
            # Basic linear estimation: 10% change in feature
            feature_mean = df[feature].mean()
            target_mean = df[target_col].mean()
            
            if feature_mean != 0 and target_mean != 0:
                estimated_impact_pct = (actual_corr * 10) # Simplified linear elasticity
                sensitivity_insights["simulations"].append(
                    f"What-If: If you increase '{feature}' by 10%, projected '{target_col}' {direction} by approximately {abs(estimated_impact_pct):.1f}%."
                )

        return sensitivity_insights

    def generate_summary(self, temporal, anomalies, sensitivity) -> Dict[str, list]:
        """
        Generate a human-readable executive summary of the advanced insights.
        """
        summary = {
            "executive_summary": [],
            "action_items": []
        }

        # Temporal Summary
        if temporal.get("trends"):
            summary["executive_summary"].extend(temporal["trends"])

        # Anomaly Summary
        if anomalies.get("total_outliers_found", 0) > 0:
            summary["executive_summary"].append(
                f"Detected {anomalies['total_outliers_found']} critical anomalies requiring attention."
            )
            summary["action_items"].extend(anomalies["top_alerts"][:3])

        # Sensitivity Summary
        if sensitivity.get("top_drivers"):
            drivers_str = ", ".join([d.split("'")[1] for d in sensitivity["top_drivers"]])
            summary["executive_summary"].append(
                f"The 3 biggest factors driving '{sensitivity['target_analyzed']}' are: {drivers_str}."
            )
            summary["action_items"].extend(sensitivity["simulations"][:2])

        return summary

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the advanced insights pipeline.
        """
        df_raw = context.get("data")
        
        # Convert to pandas for complex statistical and time-series operations
        if isinstance(df_raw, pl.DataFrame):
            df = df_raw.to_pandas()
        else:
            df = df_raw.copy()

        self.log("Generating advanced business intelligence insights...")

        # Determine target column from context if provided by a previous agent
        target_col = context.get("target_column", None)

        # Run insight modules
        temporal = self.analyze_temporal_trends(df)
        anomalies = self.detect_anomalies(df)
        sensitivity = self.sensitivity_analysis(df, target_col)

        # Compile comprehensive report
        self.insights_report = {
            "temporal_intelligence": temporal,
            "anomaly_detection": anomalies,
            "sensitivity_analysis": sensitivity,
            "summary": self.generate_summary(temporal, anomalies, sensitivity)
        }

        context["advanced_insights"] = self.insights_report
        
        self.log("Advanced insights generation complete.")
        return context