"""
Voting Integration with Context Graph

Extends the voting system to capture decision traces automatically.
Every vote becomes a queryable precedent for future decisions.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.context_graph import (
    ContextGraph,
    DecisionTrace,
    DecisionInput,
    PrecedentMatch,
    ConflictResolution,
    get_context_graph,
    find_precedents,
)


@dataclass
class EnhancedVote:
    """Vote with full reasoning captured for context graph"""
    voter_id: str
    voter_role: str
    vote: str  # approve, reject, abstain
    score: float  # 0-1 confidence
    reasoning: str  # Full reasoning text
    concerns: List[str]  # Specific concerns raised
    suggestions: List[str]  # Improvement suggestions
    precedents_considered: List[str]  # Trace IDs of precedents voter considered
    

@dataclass
class EnhancedGateResult:
    """Gate result with context graph integration"""
    gate_name: str
    passed: bool
    votes: List[EnhancedVote]
    consensus_reasoning: str
    decision_summary: str
    conditions: List[str]
    trace_id: Optional[str] = None  # Reference to context graph trace


class ContextAwareVoting:
    """
    Voting system that captures full reasoning to context graph.
    
    For each voting gate:
    1. Fetches relevant precedents before voting
    2. Includes precedents in voter context
    3. Captures complete vote reasoning
    4. Stores decision trace for future reference
    """
    
    def __init__(self, project_id: str, context_graph: Optional[ContextGraph] = None):
        self.project_id = project_id
        self.graph = context_graph or get_context_graph()
    
    def get_precedents_for_gate(
        self,
        gate_name: str,
        context: str,
        artifact_summary: str,
    ) -> List[PrecedentMatch]:
        """
        Get relevant precedents before running a voting gate.
        
        Args:
            gate_name: Name of the gate (requirements, architecture, code, etc.)
            context: Description of what's being reviewed
            artifact_summary: Summary of the artifact under review
            
        Returns:
            List of relevant precedents to include in voter context
        """
        # Map gate names to decision types
        gate_to_type = {
            "requirements_gate": "requirements",
            "architecture_gate": "architecture",
            "code_gate": "code_review",
            "test_gate": "testing",
            "security_gate": "security",
            "release_gate": "release",
        }
        
        decision_type = gate_to_type.get(gate_name, gate_name)
        
        # Build search context
        search_context = f"{context}\n{artifact_summary}"
        
        # Find precedents, preferring successful ones
        precedents = self.graph.find_precedents(
            context=search_context,
            decision_type=decision_type,
            limit=5,
            min_outcome_score=-0.5,  # Exclude total failures
            exclude_project=self.project_id,  # Don't cite own project
        )
        
        return precedents
    
    def format_precedents_for_context(self, precedents: List[PrecedentMatch]) -> str:
        """Format precedents for inclusion in voter prompt"""
        return self.graph.synthesize_precedents(precedents)
    
    def capture_gate_decision(
        self,
        gate_name: str,
        context: str,
        artifact_summary: str,
        votes: List[EnhancedVote],
        passed: bool,
        consensus_reasoning: str,
        decision_summary: str,
        conditions: List[str],
        precedents_used: List[PrecedentMatch],
        feature_id: Optional[str] = None,
        parent_trace: Optional[str] = None,
    ) -> DecisionTrace:
        """
        Capture a gate decision to the context graph.
        
        This creates a full decision trace that can be queried as precedent
        for future similar decisions.
        """
        # Build inputs
        inputs = [
            DecisionInput(
                type="artifact",
                source=gate_name,
                content_hash=str(hash(artifact_summary))[:12],
                summary=artifact_summary[:200],
            )
        ]
        
        # Add votes as inputs
        for vote in votes:
            inputs.append(DecisionInput(
                type="vote",
                source=vote.voter_id,
                content_hash=str(hash(vote.reasoning))[:12],
                summary=f"{vote.voter_role}: {vote.vote} ({vote.score:.0%})",
            ))
        
        # Build conflict resolutions from vote disagreements
        conflicts = self._extract_conflicts(votes)
        
        # Map gate name to decision type
        gate_to_type = {
            "requirements_gate": "requirements",
            "architecture_gate": "architecture", 
            "code_gate": "code_review",
            "test_gate": "testing",
            "security_gate": "security",
            "release_gate": "release",
        }
        decision_type = gate_to_type.get(gate_name, gate_name)
        
        # Determine decision string
        if passed and not conditions:
            decision = "approved"
        elif passed and conditions:
            decision = "approved_with_conditions"
        else:
            decision = "rejected"
        
        # Extract tags from context
        tags = self._extract_tags(context, artifact_summary)
        
        # Capture to context graph
        trace = self.graph.capture_decision(
            project_id=self.project_id,
            feature_id=feature_id,
            context=context,
            decision_type=decision_type,
            inputs=inputs,
            reasoning=consensus_reasoning,
            decision=decision,
            decision_summary=decision_summary,
            actor=gate_name,
            actor_type="voting_gate",
            precedents_matched=[asdict(p) for p in precedents_used],
            conflicts_resolved=conflicts,
            conditions=conditions,
            tags=tags,
            parent_trace=parent_trace,
        )
        
        return trace
    
    def _extract_conflicts(self, votes: List[EnhancedVote]) -> List[Dict]:
        """Extract conflicts from disagreeing votes"""
        conflicts = []
        
        # Group by vote outcome
        approvals = [v for v in votes if v.vote == "approve"]
        rejections = [v for v in votes if v.vote == "reject"]
        
        # If mixed votes, there was a conflict
        if approvals and rejections:
            conflict = ConflictResolution(
                issue="Voter disagreement on approval",
                options=["approve", "reject"],
                resolution="approve" if len(approvals) > len(rejections) else "reject",
                reasoning=f"{len(approvals)} voted approve, {len(rejections)} voted reject. " +
                         f"Concerns raised: {'; '.join(c for v in rejections for c in v.concerns[:2])}",
                precedents_cited=[p for v in votes for p in v.precedents_considered],
            )
            conflicts.append(asdict(conflict))
        
        # Check for specific concern patterns
        all_concerns = [c for v in votes for c in v.concerns]
        concern_counts = {}
        for c in all_concerns:
            concern_counts[c] = concern_counts.get(c, 0) + 1
        
        # Add conflicts for concerns raised by multiple voters
        for concern, count in concern_counts.items():
            if count >= 2:
                conflict = ConflictResolution(
                    issue=concern,
                    options=["address now", "defer", "accept risk"],
                    resolution="flagged for review",
                    reasoning=f"Raised by {count} voters",
                    precedents_cited=[],
                )
                conflicts.append(asdict(conflict))
        
        return conflicts
    
    def _extract_tags(self, context: str, artifact_summary: str) -> List[str]:
        """Extract relevant tags for indexing"""
        tags = []
        
        text = f"{context} {artifact_summary}".lower()
        
        # Domain tags
        domain_keywords = {
            "healthcare": ["hipaa", "health", "medical", "patient", "clinical"],
            "finance": ["payment", "stripe", "billing", "invoice", "financial"],
            "auth": ["authentication", "oauth", "login", "jwt", "session"],
            "security": ["security", "vulnerability", "encryption", "ssl", "cors"],
            "database": ["database", "sql", "postgres", "mongodb", "schema"],
            "api": ["api", "endpoint", "rest", "graphql", "webhook"],
            "frontend": ["react", "vue", "component", "ui", "css"],
            "infrastructure": ["deploy", "docker", "kubernetes", "cloud", "ci/cd"],
        }
        
        for tag, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def record_gate_outcome(
        self,
        trace_id: str,
        outcome: str,
        score: float,
        notes: str = ""
    ):
        """
        Record the outcome of a gate decision after deployment/testing.
        
        Call this when you know whether the decision led to success or failure.
        
        Args:
            trace_id: The trace ID from capture_gate_decision
            outcome: success, partial_success, failure
            score: -1.0 to 1.0 outcome score
            notes: What happened
        """
        self.graph.record_outcome(trace_id, outcome, score, notes)


def create_voter_prompt_with_precedents(
    base_prompt: str,
    precedents: List[PrecedentMatch],
    artifact: str,
) -> str:
    """
    Enhance a voter prompt with relevant precedents.
    
    This gives voters access to institutional memory when making decisions.
    """
    precedent_text = ""
    if precedents:
        precedent_text = f"""
## Relevant Precedents from Past Projects

The following similar decisions were made in past projects. Consider these when evaluating:

"""
        for i, p in enumerate(precedents, 1):
            outcome_indicator = "✅" if p.outcome_score > 0.5 else "⚠️" if p.outcome_score >= 0 else "❌"
            precedent_text += f"""
### Precedent {i}: {p.project}
- **Similarity:** {p.similarity:.0%}
- **Context:** {p.context}
- **Decision:** {p.decision}
- **Outcome:** {outcome_indicator} {p.outcome} (score: {p.outcome_score:+.1f})
"""
        
        precedent_text += """
Use these precedents to inform your decision, but evaluate the current artifact on its own merits.
If you reference a precedent in your reasoning, note which one.
"""
    
    return f"""{base_prompt}

{precedent_text}

## Artifact to Review

{artifact}

## Your Response

Provide your vote with full reasoning. Include:
1. Your vote (approve/reject/abstain)
2. Confidence score (0-100%)
3. Detailed reasoning
4. Any concerns
5. Suggestions for improvement
6. Which precedents (if any) informed your decision
"""


def parse_enhanced_vote(voter_id: str, voter_role: str, response: str) -> EnhancedVote:
    """
    Parse a voter response into an EnhancedVote.
    
    Extracts structured information from the voter's reasoning.
    """
    response_lower = response.lower()
    
    # Determine vote
    if "reject" in response_lower[:200]:
        vote = "reject"
    elif "abstain" in response_lower[:200]:
        vote = "abstain"
    else:
        vote = "approve"
    
    # Extract score (look for percentages or fractions)
    import re
    score_match = re.search(r'(\d+)\s*%', response)
    if score_match:
        score = int(score_match.group(1)) / 100
    else:
        score = 0.8 if vote == "approve" else 0.3
    
    # Extract concerns (look for bullet points or numbered items after "concern")
    concerns = []
    concern_section = re.search(r'concern[s]?[:\s]*(.*?)(?=suggestion|$)', response_lower, re.DOTALL)
    if concern_section:
        concern_items = re.findall(r'[-•*]\s*(.+?)(?=[-•*]|$)', concern_section.group(1))
        concerns = [c.strip()[:100] for c in concern_items if c.strip()][:5]
    
    # Extract suggestions
    suggestions = []
    suggestion_section = re.search(r'suggestion[s]?[:\s]*(.*?)(?=precedent|$)', response_lower, re.DOTALL)
    if suggestion_section:
        suggestion_items = re.findall(r'[-•*]\s*(.+?)(?=[-•*]|$)', suggestion_section.group(1))
        suggestions = [s.strip()[:100] for s in suggestion_items if s.strip()][:5]
    
    # Extract precedent references
    precedents = []
    precedent_refs = re.findall(r'precedent\s*(\d+)', response_lower)
    precedents = [f"precedent_{p}" for p in precedent_refs]
    
    return EnhancedVote(
        voter_id=voter_id,
        voter_role=voter_role,
        vote=vote,
        score=min(1.0, max(0.0, score)),
        reasoning=response,
        concerns=concerns,
        suggestions=suggestions,
        precedents_considered=precedents,
    )
