from typing import Any


import numpy as np
import pandas as pd
import polars as pl
from .base_agent import BaseAgent


class HealthAgent(BaseAgent):
    """Assesses data quality and provides comprehensive health insights."""

    def __init__(self):
        super().__init__("HealthAgent")
        self.health_report = {}

    def check_completeness(self, df):
        """
        Analyze missing values across the dataset.
        
        Returns:
            Dict with completeness metrics
        """
        # Convert to polars if pandas
        if isinstance(df, pd.DataFrame):
            df = pl.from_pandas(df)
        
        completeness = {
            "total_cells": df.height * df.width,
            "missing_cells": int(df.null_count().select(pl.all().sum()).item()),
            "columns": {},
        }

        completeness["overall_completeness"] = (
            (completeness["total_cells"] - completeness["missing_cells"])
            / completeness["total_cells"]
            * 100
        )

        # 🔥 Compute once
        missing_counts_df = df.null_count()
        
        for col in df.columns:
            missing_count =missing_counts_df[col][0]
            missing_pct = (missing_count / df.height) * 100

            completeness["columns"][col] = {
                "missing_count": int(missing_count),
                "missing_percentage": round(missing_pct, 2),
                "completeness_percentage": round(100 - missing_pct, 2),
            }

        completeness["overall_completeness"] = round(
            completeness["overall_completeness"], 2
        )
        
        return completeness

    def check_duplicates(self, df):
        """
        Detect duplicate rows and columns.
        
        Returns:
            Dict with duplicate detection results
        """
        # Convert if pandas
        if isinstance(df, pd.DataFrame):
            df = pl.from_pandas(df)
            
        # 🔥 compute once instead of repeating
        duplicated_rows_series = df.duplicated()
        duplicate_rows_count = int(duplicated_rows_series.sum())

        duplicates = {
            "total_rows": df.height,
            "duplicate_rows": duplicate_rows_count,
            "duplicate_rows_percentage": round(
                (duplicate_rows_count / df.height) * 100, 2
            ),
            "duplicate_columns": [],
        }
            
        # 🔥 minor optimization: avoid repeated column access
        cols = df.columns

        # Check for duplicate columns (exact same values)
        for i, col1 in enumerate(cols):
            col1_data = df[col1]   # cache column
            for col2 in cols[i + 1 :]:
                if col1_data.series_equal(df[col2]):
                    duplicates["duplicate_columns"].append((col1, col2))

        duplicates["has_duplicates"] = (
            duplicates["duplicate_rows"] > 0
            or len(duplicates["duplicate_columns"]) > 0
        )

        return duplicates

    def check_consistency(self, df):
        """
        Identify data type inconsistencies and suspicious patterns.
        
        Returns:
            Dict with consistency check results
        """
        consistency = {
            "data_types": {},
            "inconsistencies": [],
            "outlier_alerts": [],
        }

        for col in df.columns:
            consistency["data_types"][col] = str(df[col].dtype)

            # Check for negative values in price-like columns
            if self.is_numeric_column(df[col]):
                if any(
                    keyword in col.lower()
                    for keyword in ["price", "cost", "amount", "salary"]
                ):
                    if (df[col] < 0).any():
                        consistency["inconsistencies"].append(
                            f"Column '{col}' contains negative values "
                            "(expected to be non-negative)"
                        )

                # Detect outliers using IQR method
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outlier_count = (
                    (df[col] < lower_bound) | (df[col] > upper_bound)
                ).sum()

                if outlier_count > 0:
                    outlier_pct = (outlier_count / len(df)) * 100
                    if outlier_pct > 5:  # Alert if >5% outliers
                        consistency["outlier_alerts"].append(
                            {
                                "column": col,
                                "outlier_count": int(outlier_count),
                                "outlier_percentage": round(outlier_pct, 2),
                            }
                        )

            # Check for mixed types in object columns
            if df[col].dtype == "object":
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    type_counts = non_null.apply(type).value_counts()
                    if len(type_counts) > 1:
                        consistency["inconsistencies"].append(
                            f"Column '{col}' has mixed data types: "
                            f"{dict(type_counts)}"
                        )

        return consistency

    def calculate_trust_score(self, completeness, duplicates, consistency):
        """
        Calculate overall trust score (0-100) based on quality metrics.
        
        Scoring breakdown:
        - Completeness: 40 points (0.4 weight)
        - Duplicates: 30 points (0.3 weight)
        - Consistency: 30 points (0.3 weight)
        
        Args:
            completeness: Completeness metrics dict
            duplicates: Duplicates metrics dict
            consistency: Consistency metrics dict
            
        Returns:
            int: Trust score from 0-100
        """
        # Completeness score (0-40 points)
        completeness_score = (
            completeness["overall_completeness"] / 100 * 40
        )

        # Duplicates score (0-30 points)
        # Penalize based on duplicate percentage
        duplicate_pct = duplicates["duplicate_rows_percentage"]
        duplicates_score = max(0, 30 - (duplicate_pct * 0.3))

        # Consistency score (0-30 points)
        # Penalize for inconsistencies
        inconsistency_count = len(consistency["inconsistencies"])
        outlier_alert_count = len(consistency["outlier_alerts"])
        penalties = (inconsistency_count * 2) + (outlier_alert_count * 1.5)
        consistency_score = max(0, 30 - penalties)

        trust_score = (
            completeness_score + duplicates_score + consistency_score
        )

        return int(trust_score)

    def is_numeric_column(self, col):
        """Check if a column is numeric."""
        return pd.api.types.is_numeric_dtype(col)

    def generate_summary(self, completeness, duplicates, consistency, trust_score):
        """
        Generate a human-readable summary of data health.
        
        Args:
            completeness: Completeness metrics
            duplicates: Duplicates metrics
            consistency: Consistency metrics
            trust_score: Overall trust score
            
        Returns:
            Dict with summary insights
        """
        summary = {
            "trust_level": self.get_trust_level(trust_score),
            "key_insights": [],
            "recommendations": [],
        }

        # Completeness insights
        if completeness["overall_completeness"] < 80:
            summary["key_insights"].append(
                f"⚠️  Data completeness is {completeness['overall_completeness']}%. "
                "Significant missing values detected."
            )
            summary["recommendations"].append(
                "Consider imputation or removing columns with >20% missing values."
            )
        else:
            summary["key_insights"].append(
                f"✅ Data completeness is strong at "
                f"{completeness['overall_completeness']}%."
            )

        # Duplicates insights
        if duplicates["has_duplicates"]:
            summary["key_insights"].append(
                f"⚠️  Found {duplicates['duplicate_rows']} duplicate rows "
                f"({duplicates['duplicate_rows_percentage']}%)."
            )
            summary["recommendations"].append(
                "Remove or investigate duplicate records to avoid biased analysis."
            )
        else:
            summary["key_insights"].append("✅ No duplicate rows detected.")

        # Consistency insights
        if consistency["inconsistencies"]:
            summary["key_insights"].append(
                f"⚠️  {len(consistency['inconsistencies'])} data consistency issues found."
            )
            for issue in consistency["inconsistencies"][:3]:  # Show top 3
                summary["recommendations"].append(f"Review: {issue}")
        else:
            summary["key_insights"].append("✅ Data types are consistent.")

        if consistency["outlier_alerts"]:
            summary["key_insights"].append(
                f"⚠️  {len(consistency['outlier_alerts'])} columns have "
                "significant outliers (>5%)."
            )
            summary["recommendations"].append(
                "Investigate outliers—they may be valid extremes or data errors."
            )

        return summary

    def get_trust_level(self, score):
        """Convert numeric score to qualitative trust level."""
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        else:
            return "Poor"
        
    def run(self, context):
        """
        Analyze data quality and generate a comprehensive health report.
        
        Args:
            context: Dictionary containing 'data' key with the dataframe
            
        Returns:
            Updated context with 'health_report' and 'trust_score'
        """
        df = context["data"].copy()
        self.log("Analyzing data quality and health...")

        # Run all quality checks
        completeness = self.check_completeness(df)
        duplicates = self.check_duplicates(df)
        consistency = self.check_consistency(df)
        
        # Calculate trust score
        trust_score = self.calculate_trust_score(
            completeness, duplicates, consistency
        )

        # Compile comprehensive report
        self.health_report = {
            "completeness": completeness,
            "duplicates": duplicates,
            "consistency": consistency,
            "trust_score": trust_score,
            "summary": self.generate_summary(
                completeness, duplicates, consistency, trust_score
            ),
        }

        context["health_report"] = self.health_report
        context["trust_score"] = trust_score
        
        self.log(f"Data health analysis complete. Trust Score: {trust_score}/100")
        return context