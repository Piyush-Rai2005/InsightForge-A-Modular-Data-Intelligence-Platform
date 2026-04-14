# HealthAgent - Data Quality Assessment

A modular, production-ready agent for comprehensive data quality evaluation. The `HealthAgent` provides actionable insights about data health before analysis, helping you identify issues early and make informed decisions about data processing.

---

## 📋 Features

### 1. **Completeness Metrics**
   - Tracks missing values across the entire dataset
   - Provides per-column missing value breakdown
   - Calculates overall completeness percentage
   - Identifies columns with critical data gaps

### 2. **Duplicate Detection**
   - Detects duplicate rows in the dataset
   - Identifies duplicate columns (exact matches)
   - Reports duplicate frequency and impact percentage
   - Alerts when duplicates may skew analysis

### 3. **Data Consistency Checks**
   - Validates data types across columns
   - Detects inconsistent/mixed data types in object columns
   - Identifies logically inconsistent values (e.g., negative prices)
   - Outlier detection using the Interquartile Range (IQR) method
   - Highlights columns with >5% outliers for investigation

### 4. **Trust Score (0-100)**
   - **Completeness (40%)**: Based on overall missing value percentage
   - **Duplicates (30%)**: Penalized by duplicate row percentage
   - **Consistency (30%)**: Penalized by inconsistencies and outliers
   - Qualitative trust levels: Excellent (≥80), Good (≥60), Fair (≥40), Poor (<40)

### 5. **Actionable Recommendations**
   - Summary insights with visual indicators (✅ / ⚠️)
   - Specific recommendations for data improvement
   - Prioritized alerts for critical issues

---

## 🚀 Quick Start

### Installation
```python
from health_agent import HealthAgent
import pandas as pd
```

### Basic Usage
```python
# Load your data
df = pd.read_csv("data.csv")

# Initialize HealthAgent
health_agent = HealthAgent()

# Run analysis
context = {"data": df}
result = health_agent.run(context)

# Access results
health_report = result["health_report"]
trust_score = result["trust_score"]

print(f"Trust Score: {trust_score}/100")
print(f"Trust Level: {health_report['summary']['trust_level']}")
```

---

## 📊 Output Structure

### Health Report Dictionary
```python
health_report = {
    "completeness": {
        "total_cells": int,
        "missing_cells": int,
        "overall_completeness": float,  # 0-100%
        "columns": {
            "column_name": {
                "missing_count": int,
                "missing_percentage": float,
                "completeness_percentage": float
            },
            ...
        }
    },
    "duplicates": {
        "total_rows": int,
        "duplicate_rows": int,
        "duplicate_rows_percentage": float,
        "duplicate_columns": [tuple, ...],  # (col1, col2) pairs
        "has_duplicates": bool
    },
    "consistency": {
        "data_types": {
            "column_name": "dtype",
            ...
        },
        "inconsistencies": [str, ...],  # List of detected issues
        "outlier_alerts": [
            {
                "column": str,
                "outlier_count": int,
                "outlier_percentage": float
            },
            ...
        ]
    },
    "trust_score": int,  # 0-100
    "summary": {
        "trust_level": str,  # "Excellent" | "Good" | "Fair" | "Poor"
        "key_insights": [str, ...],
        "recommendations": [str, ...]
    }
}
```

---

## 🔍 Detailed Breakdown

### Completeness Metrics
- **Overall Completeness**: Percentage of non-missing cells across the dataset
- **Per-Column Breakdown**: Missing value count and percentage for each column
- **Threshold Alert**: Columns with >20% missing values are flagged in recommendations

**Example Output:**
```
Overall Completeness: 92.5%
Columns:
  • age: 3 missing (3.75%)
  • salary: 2 missing (2.5%)
```

### Duplicate Detection
- **Duplicate Rows**: Exact row matches identified via pandas `duplicated()`
- **Duplicate Columns**: Columns with identical values flagged
- **Impact Percentage**: Calculated as (duplicate_rows / total_rows) × 100

**Example Output:**
```
Duplicate Rows: 15 (5.2%)
Duplicate Columns: [('revenue', 'total_income')]
```

### Data Consistency Checks
- **Data Type Validation**: Verifies that each column has a consistent dtype
- **Domain-Specific Checks**: Flags negative values in columns named "price", "cost", "amount", "salary"
- **Outlier Detection**: Uses IQR method (1.5 × IQR rule)
  - Lower Bound = Q1 - 1.5 × IQR
  - Upper Bound = Q3 + 1.5 × IQR
  - Alerts triggered when >5% of values are outliers

**Example Output:**
```
Inconsistencies:
  ⚠️  Column 'price' contains negative values (expected to be non-negative)
  ⚠️  Column 'status' has mixed data types: {str: 180, int: 20}

Outlier Alerts:
  ⚠️  salary: 24 outliers (8.3%)
```

### Trust Score Calculation
```
Trust Score = 
  (Completeness % ÷ 100) × 40 +
  max(0, 30 - duplicate% × 0.3) +
  max(0, 30 - inconsistencies × 2 - outliers × 1.5)
```

| Score Range | Level      | Interpretation                          |
|-------------|------------|----------------------------------------|
| 80–100     | Excellent  | Data is clean and ready for analysis   |
| 60–79      | Good       | Minor issues; proceed with caution     |
| 40–59      | Fair       | Multiple issues; address before use    |
| 0–39       | Poor       | Critical issues; extensive cleaning needed |

---

## 🔧 API Reference

### `HealthAgent()`

**Methods:**

#### `run(context)`
Main method to execute data quality analysis.

**Parameters:**
- `context` (dict): Dictionary with key `"data"` containing a pandas DataFrame

**Returns:**
- `dict`: Updated context with `"health_report"` and `"trust_score"` keys

**Example:**
```python
context = {"data": df}
result = health_agent.run(context)
health_report = result["health_report"]
trust_score = result["trust_score"]
```

---

#### `check_completeness(df)`
Analyzes missing values across the dataset.

**Returns:**
- `dict`: Completeness metrics with per-column breakdown

---

#### `check_duplicates(df)`
Detects duplicate rows and columns.

**Returns:**
- `dict`: Duplicate detection results

---

#### `check_consistency(df)`
Validates data types and detects inconsistencies.

**Returns:**
- `dict`: Data type info, inconsistencies, and outlier alerts

---

#### `calculate_trust_score(completeness, duplicates, consistency)`
Computes the overall trust score (0–100).

**Parameters:**
- `completeness` (dict): Completeness metrics
- `duplicates` (dict): Duplicate detection results
- `consistency` (dict): Consistency check results

**Returns:**
- `int`: Trust score (0–100)

---

## 📈 Integration with DataAgent

Use `HealthAgent` **before** `DataAgent` in your pipeline to assess data quality:

```python
from health_agent import HealthAgent
from data_agent import DataAgent
import pandas as pd

# Load data
df = pd.read_csv("raw_data.csv")
context = {"data": df}

# Step 1: Health Assessment
health_agent = HealthAgent()
context = health_agent.run(context)

# Step 2: Decide whether to proceed
if context["trust_score"] >= 60:
    # Data quality is acceptable
    data_agent = DataAgent()
    context = data_agent.run(context)
    
    print("✅ Data processed successfully")
else:
    # Data has critical issues
    print("❌ Data quality issues detected:")
    for rec in context["health_report"]["summary"]["recommendations"]:
        print(f"   • {rec}")
    
    # Optional: Proceed anyway with warnings
    # data_agent = DataAgent()
    # context = data_agent.run(context)
```

---

## 🛠️ Customization

### Extending HealthAgent
Create a custom subclass for domain-specific checks:

```python
class MedicalDataHealthAgent(HealthAgent):
    """HealthAgent tailored for medical datasets."""
    
    def check_consistency(self, df):
        consistency = super().check_consistency(df)
        
        # Add medical-specific checks
        if "blood_pressure" in df.columns:
            bp = df["blood_pressure"]
            if (bp > 300).any() or (bp < 60).any():
                consistency["inconsistencies"].append(
                    "Unrealistic blood pressure values detected"
                )
        
        return consistency
```

### Custom Trust Score Weights
Override `calculate_trust_score()` to adjust weighting:

```python
class CustomHealthAgent(HealthAgent):
    def calculate_trust_score(self, completeness, duplicates, consistency):
        # Weight completeness more heavily
        completeness_score = completeness["overall_completeness"] / 100 * 50
        duplicates_score = max(0, 25 - duplicates["duplicate_rows_percentage"] * 0.3)
        consistency_score = max(0, 25 - len(consistency["inconsistencies"]) * 2)
        
        return int(completeness_score + duplicates_score + consistency_score)
```

---

## 📝 Example Outputs

### Example 1: High-Quality Data
```
Trust Score: 94/100
Trust Level: Excellent

✅ Data completeness is strong at 99.2%.
✅ No duplicate rows detected.
✅ Data types are consistent.

Recommendations:
  None - data is ready for analysis!
```

### Example 2: Data with Issues
```
Trust Score: 52/100
Trust Level: Fair

⚠️  Data completeness is 78.5%. Significant missing values detected.
⚠️  Found 12 duplicate rows (4.1%).
⚠️  3 data consistency issues found.
⚠️  2 columns have significant outliers (>5%).

Recommendations:
  1. Consider imputation or removing columns with >20% missing values.
  2. Remove or investigate duplicate records to avoid biased analysis.
  3. Review: Column 'price' contains negative values (expected to be non-negative)
  4. Investigate outliers—they may be valid extremes or data errors.
```

---

## 🎯 Use Cases

1. **Pre-Analysis Audit**: Run before exploratory data analysis (EDA)
2. **Data Intake Validation**: Validate incoming datasets from external sources
3. **Pipeline Monitoring**: Track data quality across multiple processing stages
4. **Stakeholder Communication**: Generate reports for non-technical stakeholders
5. **Automated Data Quality Gates**: Block low-quality data from entering pipelines

---

## 📦 Dependencies

- `numpy`
- `pandas`
- `.base_agent` (from your agent framework)

---

## 📄 License & Attribution

Part of a modular data processing agent framework. Designed to work alongside `DataAgent` and other processing agents.

---

## ❓ FAQ

**Q: Should I use HealthAgent before or after DataAgent?**
A: Always use HealthAgent **before** DataAgent. This allows you to understand your data's initial state and make informed decisions about preprocessing.

**Q: What does a "fair" trust score mean?**
A: A fair score (40–59) indicates multiple quality issues that should be addressed. Review the recommendations and inconsistencies before proceeding.

**Q: Can I customize which checks are performed?**
A: Yes, extend the class and override the `run()` method or specific check methods like `check_consistency()`.

**Q: How are outliers detected?**
A: Using the IQR (Interquartile Range) method: values outside [Q1 - 1.5×IQR, Q3 + 1.5×IQR] are flagged if >5% of values are affected.

**Q: Does HealthAgent modify the original data?**
A: No, it only analyzes and reports. Use DataAgent for preprocessing and cleaning.

---

## 🤝 Contributing & Feedback

For improvements or domain-specific extensions, consider:
1. Subclassing for domain-specific rules
2. Adjusting trust score weights
3. Adding custom inconsistency checks

---