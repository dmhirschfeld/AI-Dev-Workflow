"""
Voting Gate System
Handles quality gates with parallel voting and threshold evaluation
"""

import yaml
import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime

from core.agents import AgentFactory, AgentExecutor, AgentResponse


@dataclass
class Vote:
    """Individual vote from a voter"""
    voter_id: str
    voter_role: str
    vote: Literal["approve", "reject"]
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    concerns: list[str]
    suggestions: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GateResult:
    """Result of a voting gate"""
    gate_id: str
    gate_name: str
    passed: bool
    votes: list[Vote]
    approve_count: int
    reject_count: int
    threshold: int
    retry_count: int
    aggregated_feedback: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class GateConfig:
    """Configuration for a voting gate"""
    id: str
    name: str
    gate_type: Literal["major", "minor", "single"]
    trigger: str
    threshold: int
    max_retries: int
    voters: list[str]
    on_pass: str
    on_fail: str
    feedback_required: bool = True
    approver: str | None = None  # For single gates
    criteria: str | None = None  # For single gates


class VotingGateSystem:
    """Manages voting gates and execution"""
    
    def __init__(
        self,
        gates_config_path: str = "config/gates.yaml",
        agents_config_path: str = "agents/definitions.yaml"
    ):
        self.gates: dict[str, GateConfig] = {}
        self.factory = AgentFactory(agents_config_path)
        self.executor = AgentExecutor(self.factory)
        self._load_gates(gates_config_path)
    
    def _load_gates(self, config_path: str):
        """Load gate configurations from YAML"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        for gate_data in config.get("gates", []):
            gate = GateConfig(
                id=gate_data["id"],
                name=gate_data["name"],
                gate_type=gate_data["type"],
                trigger=gate_data["trigger"],
                threshold=gate_data.get("threshold", 1),
                max_retries=gate_data.get("max_retries", 3),
                voters=gate_data.get("voters", []),
                on_pass=gate_data["on_pass"],
                on_fail=gate_data["on_fail"],
                feedback_required=gate_data.get("feedback_required", True),
                approver=gate_data.get("approver"),
                criteria=gate_data.get("criteria")
            )
            self.gates[gate.id] = gate
    
    def get_gate(self, gate_id: str) -> GateConfig | None:
        """Get gate configuration by ID"""
        return self.gates.get(gate_id)
    
    async def run_gate(
        self,
        gate_id: str,
        artifact: str,
        context: str = "",
        retry_count: int = 0
    ) -> GateResult:
        """Run a voting gate and return results"""
        gate = self.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate {gate_id} not found")
        
        if gate.gate_type == "single":
            return await self._run_single_gate(gate, artifact, context, retry_count)
        else:
            return await self._run_voting_gate(gate, artifact, context, retry_count)
    
    async def _run_voting_gate(
        self,
        gate: GateConfig,
        artifact: str,
        context: str,
        retry_count: int
    ) -> GateResult:
        """Run a multi-voter gate"""
        
        # Create voting task for each voter
        vote_prompt = self._create_vote_prompt(gate, artifact, context)
        
        # Execute all voters in parallel
        voter_tasks = [
            (voter_id, vote_prompt, context)
            for voter_id in gate.voters
        ]
        
        responses = await self.executor.execute_parallel(voter_tasks)
        
        # Parse votes from responses
        votes = []
        for response in responses:
            if response.success:
                vote = self._parse_vote_response(response)
                if vote:
                    votes.append(vote)
        
        # Count votes
        approve_count = sum(1 for v in votes if v.vote == "approve")
        reject_count = sum(1 for v in votes if v.vote == "reject")
        passed = approve_count >= gate.threshold
        
        # Aggregate feedback
        aggregated_feedback = self._aggregate_feedback(votes)
        
        return GateResult(
            gate_id=gate.id,
            gate_name=gate.name,
            passed=passed,
            votes=votes,
            approve_count=approve_count,
            reject_count=reject_count,
            threshold=gate.threshold,
            retry_count=retry_count,
            aggregated_feedback=aggregated_feedback
        )
    
    async def _run_single_gate(
        self,
        gate: GateConfig,
        artifact: str,
        context: str,
        retry_count: int
    ) -> GateResult:
        """Run a single-approver gate"""
        
        approve_prompt = f"""Review the following artifact for approval.

## Approval Criteria
{gate.criteria}

## Artifact
{artifact}

## Your Task
Evaluate if this artifact meets the criteria. Respond in JSON format:
{{
    "vote": "approve" or "reject",
    "confidence": "high", "medium", or "low",
    "reasoning": "Your explanation",
    "concerns": ["list", "of", "concerns"],
    "suggestions": ["improvement", "suggestions"]
}}
"""
        
        response = await self.executor.execute(
            gate.approver,
            approve_prompt,
            context
        )
        
        votes = []
        if response.success:
            vote = self._parse_vote_response(response)
            if vote:
                votes.append(vote)
        
        passed = len(votes) > 0 and votes[0].vote == "approve"
        
        return GateResult(
            gate_id=gate.id,
            gate_name=gate.name,
            passed=passed,
            votes=votes,
            approve_count=1 if passed else 0,
            reject_count=0 if passed else 1,
            threshold=1,
            retry_count=retry_count,
            aggregated_feedback=self._aggregate_feedback(votes)
        )
    
    def _create_vote_prompt(
        self,
        gate: GateConfig,
        artifact: str,
        context: str
    ) -> str:
        """Create the voting prompt for voters"""
        return f"""You are participating in a quality gate review: {gate.name}

## Your Task
Evaluate the following artifact from your specific perspective. 

## Gate Trigger
{gate.trigger}

## Artifact to Review
{artifact}

## Additional Context
{context if context else "No additional context provided."}

## Response Format
Respond ONLY with valid JSON in this exact format:
{{
    "vote": "approve" or "reject",
    "confidence": "high", "medium", or "low",
    "reasoning": "Brief explanation of your decision",
    "concerns": ["list", "of", "specific", "concerns"],
    "suggestions": ["actionable", "improvement", "suggestions"]
}}

Focus on your specific evaluation perspective. Be constructive in feedback.
"""
    
    def _parse_vote_response(self, response: AgentResponse) -> Vote | None:
        """Parse a vote from an agent response"""
        try:
            # Try to extract JSON from response
            content = response.content.strip()
            
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            return Vote(
                voter_id=response.agent_id,
                voter_role=response.role,
                vote=data.get("vote", "reject"),
                confidence=data.get("confidence", "low"),
                reasoning=data.get("reasoning", ""),
                concerns=data.get("concerns", []),
                suggestions=data.get("suggestions", [])
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse vote from {response.agent_id}: {e}")
            return None
    
    def _aggregate_feedback(self, votes: list[Vote]) -> str:
        """Aggregate feedback from all votes"""
        if not votes:
            return "No votes recorded."
        
        sections = []
        
        # Summary
        approve = sum(1 for v in votes if v.vote == "approve")
        reject = len(votes) - approve
        sections.append(f"## Vote Summary\n- Approved: {approve}\n- Rejected: {reject}")
        
        # Concerns (from rejections)
        all_concerns = []
        for vote in votes:
            if vote.concerns:
                for concern in vote.concerns:
                    all_concerns.append(f"- [{vote.voter_role}] {concern}")
        
        if all_concerns:
            sections.append("## Concerns\n" + "\n".join(all_concerns))
        
        # Suggestions
        all_suggestions = []
        for vote in votes:
            if vote.suggestions:
                for suggestion in vote.suggestions:
                    all_suggestions.append(f"- [{vote.voter_role}] {suggestion}")
        
        if all_suggestions:
            sections.append("## Suggestions\n" + "\n".join(all_suggestions))
        
        # Individual reasoning
        reasoning_section = "## Individual Assessments\n"
        for vote in votes:
            status = "✅" if vote.vote == "approve" else "❌"
            reasoning_section += f"\n### {status} {vote.voter_role} ({vote.confidence} confidence)\n{vote.reasoning}\n"
        
        sections.append(reasoning_section)
        
        return "\n\n".join(sections)


class GateManager:
    """High-level manager for running gates with retry logic"""
    
    def __init__(self, gate_system: VotingGateSystem):
        self.gate_system = gate_system
        self.results_history: list[GateResult] = []
    
    async def run_with_retry(
        self,
        gate_id: str,
        artifact: str,
        context: str = "",
        on_fail_callback=None
    ) -> tuple[bool, GateResult, list[GateResult]]:
        """
        Run a gate with automatic retry on failure.
        Returns (final_passed, final_result, all_attempts)
        """
        gate = self.gate_system.get_gate(gate_id)
        if not gate:
            raise ValueError(f"Gate {gate_id} not found")
        
        attempts = []
        current_artifact = artifact
        
        for retry in range(gate.max_retries + 1):
            result = await self.gate_system.run_gate(
                gate_id,
                current_artifact,
                context,
                retry_count=retry
            )
            attempts.append(result)
            self.results_history.append(result)
            
            if result.passed:
                return True, result, attempts
            
            # If not passed and we have retries left, get revised artifact
            if retry < gate.max_retries and on_fail_callback:
                current_artifact = await on_fail_callback(
                    current_artifact,
                    result.aggregated_feedback
                )
        
        # All retries exhausted
        return False, attempts[-1], attempts


# Convenience function for running a gate
def run_gate_sync(
    gate_id: str,
    artifact: str,
    context: str = "",
    gates_config: str = "config/gates.yaml",
    agents_config: str = "agents/definitions.yaml"
) -> GateResult:
    """Run a gate synchronously"""
    system = VotingGateSystem(gates_config, agents_config)
    return asyncio.run(system.run_gate(gate_id, artifact, context))


if __name__ == "__main__":
    # Example usage
    system = VotingGateSystem()
    
    print("Available Gates:")
    for gate_id, gate in system.gates.items():
        print(f"  - {gate_id}: {gate.name} ({gate.gate_type}, threshold: {gate.threshold})")
