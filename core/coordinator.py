from agents.data_agent import DataAgent
from agents.target_agent import TargetAgent
from agents.feature_agent import FeatureAgent
from agents.model_agent import ModelAgent
from agents.evaluation_agent import EvaluationAgent
from agents.insight_agent import InsightAgent
from agents.report_agent import ReportAgent

class PipelineCoordinator:
    """Runs the full multi-agent AutoDS pipeline."""

    def __init__(self):
        self.pipeline = [
            DataAgent(),
            TargetAgent(),
            FeatureAgent(),
            ModelAgent(),
            EvaluationAgent(),
            InsightAgent(),
            ReportAgent(),
        ]

    def run(self, df):
        context = {"data": df}
        for agent in self.pipeline:
            context = agent.run(context)
        return context