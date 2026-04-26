"""Helpers for timing the end-to-end processing pipeline on sample inputs."""

import time
from app.agents.orchestrator_agent import OrchestratorAgent
import logging

logger = logging.getLogger(__name__)

class EvaluationService:
    """Run a sample through the orchestrator and report timing + success state."""

    def __init__(self, orchestrator: OrchestratorAgent):
        self.orchestrator = orchestrator

    def evaluate_sample(self, transcript: str, expected_summary: str = None) -> dict:
        """Runs the orchestrator on a sample and returns performance metrics."""
        start_time = time.time()
        
        try:
            meeting_id = self.orchestrator.process_new_meeting(transcript, title="Evaluation Sample")
            processing_time = time.time() - start_time
            
            return {
                "success": True,
                "meeting_id": meeting_id,
                "processing_time_seconds": round(processing_time, 2),
                "error": None
            }
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {
                "success": False,
                "processing_time_seconds": round(time.time() - start_time, 2),
                "error": str(e)
            }
