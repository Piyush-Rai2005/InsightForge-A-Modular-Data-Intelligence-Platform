
from agents.health_agent import HealthAgent
from agents.data_agent import DataAgent
from agents.schema_insight_agent import SchemaInsightAgent
from agents.target_agent import TargetAgent
from agents.feature_agent import FeatureAgent
from agents.model_agent import ModelAgent
from agents.evaluation_agent import EvaluationAgent
from agents.insight_agent import InsightAgent
from agents.advanced_insights_agent import AdvancedInsightsAgent
from agents.report_agent import ReportAgent

class PipelineCoordinator:
    """Runs the full multi-agent pipeline.

    Pipeline flow:
    1. HealthAgent        -> data quality check
    2. DataAgent          -> clean & preprocess
    3. SchemaInsightAgent -> detect column semantics, generate business charts
    4. TargetAgent        -> evaluate if ML is appropriate (may set skip_ml=True)
    5. FeatureAgent       -> feature engineering (skipped if skip_ml)
    6. ModelAgent         -> train models (skipped if skip_ml)
    7. EvaluationAgent    -> evaluate models (skipped if skip_ml)
    8. InsightAgent       -> generate business narrative (adapts to ML/EDA mode)
    9. AdvancedInsightsAgent -> anomaly detection, trends
    10. ReportAgent       -> generate PDF report
    """

    def __init__(self):
        self.pipeline = [
            HealthAgent(),
            DataAgent(),
            SchemaInsightAgent(),   # schema-driven charts & business questions
            TargetAgent(),
            FeatureAgent(),
            ModelAgent(),
            EvaluationAgent(),
            InsightAgent(),
            AdvancedInsightsAgent(),
            ReportAgent(),
        ]

    def run(self, df, on_step=None):
        context = {"data": df}
        total = len(self.pipeline)

        for i, agent in enumerate(self.pipeline):
            agent_name = agent.__class__.__name__

            if on_step:
                on_step(agent_name, i, total)

            try:
                context = agent.run(context)
            except Exception as e:
                print(f"  {agent_name} failed: {e}")
                # Continue pipeline even if a non-critical agent fails
                if agent_name in ("HealthAgent", "AdvancedInsightsAgent", "SchemaInsightAgent"):
                    continue
                raise

        if on_step:
            on_step("Done", total, total)

        return context
