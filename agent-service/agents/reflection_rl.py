"""RL-inspired self-reflection for analytics agent.

Implements reflection-as-reward: critic evaluation becomes training signal
for planner policy. No gradient updates — uses trajectory-based learning.

Key concepts from RL self-reflection papers:
1. Reward signal: Critic pass/fail + structured feedback
2. Value estimation: Track success rates per (intent, pipeline) pair
3. Policy update: Bias planner toward high-value agent sequences
4. Trajectory memory: Store failed attempts to avoid repetition
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import json
import hashlib
from utils.agent_logger import get_logger

logger = get_logger("reflection_rl")


@dataclass
class TrajectoryRecord:
    """Records a single execution trajectory for learning."""
    query_hash: str
    intent: str
    pipeline: List[str]
    success: bool
    reward: float
    critic_feedback: str = ""
    data_error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)


class ReflectionRLMemory:
    """Stores trajectories and computes value estimates for policy learning.

    Implements experience replay buffer from RL — planner queries this
    to bias action selection toward historically successful sequences.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.trajectories: List[TrajectoryRecord] = []
        self._index: Dict[str, List[int]] = {}  # query_hash → trajectory indices

    def add(self, record: TrajectoryRecord) -> None:
        """Add trajectory to memory."""
        idx = len(self.trajectories)
        self.trajectories.append(record)

        # Index by query hash for retrieval
        if record.query_hash not in self._index:
            self._index[record.query_hash] = []
        self._index[record.query_hash].append(idx)

        # Trim if exceeded
        if len(self.trajectories) > self.max_size:
            self.trajectories = self.trajectories[-self.max_size:]
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild index after trimming."""
        self._index = {}
        for i, traj in enumerate(self.trajectories):
            if traj.query_hash not in self._index:
                self._index[traj.query_hash] = []
            self._index[traj.query_hash].append(i)

    def get_similar_queries(self, query: str, top_k: int = 5) -> List[TrajectoryRecord]:
        """Find similar historical queries by hash prefix."""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        indices = self._index.get(query_hash, [])
        return [self.trajectories[i] for i in indices[-top_k:]]

    def get_value_estimate(self, intent: str, pipeline: List[str]) -> float:
        """Estimate expected reward for (intent, pipeline) pair.

        Returns average reward for similar trajectories.
        Higher value = more likely to succeed.
        """
        matching = [
            t for t in self.trajectories
            if t.intent == intent and t.pipeline == pipeline
        ]
        if not matching:
            return 0.0  # No prior experience
        return sum(t.reward for t in matching) / len(matching)

    def get_best_pipeline(self, intent: str) -> Optional[List[str]]:
        """Find highest-value pipeline for given intent."""
        intent_trajectories = [t for t in self.trajectories if t.intent == intent]
        if not intent_trajectories:
            return None

        # Group by pipeline, compute avg reward
        pipeline_rewards: Dict[tuple, List[float]] = {}
        for t in intent_trajectories:
            key = tuple(t.pipeline)
            if key not in pipeline_rewards:
                pipeline_rewards[key] = []
            pipeline_rewards[key].append(t.reward)

        # Pick pipeline with highest average reward
        best_pipeline = max(pipeline_rewards.keys(), key=lambda k: sum(pipeline_rewards[k]) / len(pipeline_rewards[k]))
        return list(best_pipeline)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory for state passing."""
        return {
            "trajectory_count": len(self.trajectories),
            "recent_trajectories": [
                {
                    "query_hash": t.query_hash,
                    "intent": t.intent,
                    "pipeline": t.pipeline,
                    "success": t.success,
                    "reward": t.reward,
                }
                for t in self.trajectories[-10:]  # Last 10 for context
            ]
        }


# Singleton memory instance shared across queries
_rl_memory: Optional[ReflectionRLMemory] = None


def get_rl_memory() -> ReflectionRLMemory:
    """Get or create RL memory singleton."""
    global _rl_memory
    if _rl_memory is None:
        _rl_memory = ReflectionRLMemory()
    return _rl_memory


def compute_reward(
    critic_passed: bool,
    critic_feedback: str,
    data_error: Optional[str] = None,
    replan_count: int = 0,
) -> float:
    """Compute reward signal from reflection outcome.

    Reward structure:
    - +1.0: Critic pass on first try
    - +0.5: Critic pass after replan
    - -0.5: Critic fail (but valid attempt)
    - -1.0: Data discovery error (unavailable table/column)
    - -0.2: Per replan iteration (penalize inefficiency)
    """
    if data_error:
        return -1.0  # Data unavailable — not agent's fault but still failed

    if not critic_passed:
        return -0.5 - (0.2 * replan_count)  # Fail + inefficiency penalty

    # Success cases
    if replan_count == 0:
        return 1.0  # Perfect
    return 0.5 - (0.2 * (replan_count - 1))  # Success but took extra steps


def record_trajectory(
    query: str,
    intent: str,
    pipeline: List[str],
    critic_passed: bool,
    critic_feedback: str,
    data_error: Optional[str] = None,
    replan_count: int = 0,
    planner_steps: Optional[List[Dict[str, Any]]] = None,
) -> TrajectoryRecord:
    """Record completed trajectory for RL learning."""
    query_hash = hashlib.md5(query.encode()).hexdigest()
    reward = compute_reward(critic_passed, critic_feedback, data_error, replan_count)

    record = TrajectoryRecord(
        query_hash=query_hash,
        intent=intent,
        pipeline=pipeline,
        success=critic_passed,
        reward=reward,
        critic_feedback=critic_feedback,
        data_error=data_error,
        steps=planner_steps or [],
    )

    memory = get_rl_memory()
    memory.add(record)

    logger.info(
        "recorded trajectory: query_hash=%s intent=%s pipeline=%s reward=%.2f success=%s",
        query_hash, intent, pipeline, reward, critic_passed,
    )

    return record


def get_policy_suggestion(query: str, intent: str) -> Optional[Dict[str, Any]]:
    """Query RL memory for policy suggestion.

    Returns suggested pipeline based on historical success rates.
    """
    memory = get_rl_memory()

    # First: check if similar queries succeeded with specific pipeline
    similar = memory.get_similar_queries(query, top_k=3)
    successful = [t for t in similar if t.success]
    if successful:
        # Return most recent successful pipeline
        return {
            "source": "similar_query",
            "pipeline": successful[-1].pipeline,
            "confidence": 0.8,
        }

    # Second: use value estimate for intent
    best_pipeline = memory.get_best_pipeline(intent)
    if best_pipeline:
        value = memory.get_value_estimate(intent, best_pipeline)
        return {
            "source": "value_estimate",
            "pipeline": best_pipeline,
            "confidence": min(0.5 + (value * 0.3), 0.9),  # Scale confidence by value
        }

    return None
