"""
Context Graph Module

Captures decision traces and provides precedent lookup for institutional reasoning.
Implements the "Event Clock" pattern - storing WHY decisions were made, not just WHAT.

Key concepts:
- Decision Trace: A complete record of a decision including inputs, reasoning, precedents, outcome
- Precedent: Past decisions that can inform current decisions
- Context Node: A point in the graph representing an entity (project, feature, decision)
- Relationship: How nodes connect (led_to, similar_to, caused, resolved_by)
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import yaml

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


@dataclass
class DecisionInput:
    """An input that influenced a decision"""
    type: str  # requirement, policy, code, precedent, context
    source: str  # file path, system name, or description
    content_hash: str  # for deduplication
    summary: str  # brief description


@dataclass
class PrecedentMatch:
    """A matched precedent from the graph"""
    trace_id: str
    project: str
    similarity: float
    context: str
    decision: str
    outcome: str
    outcome_score: float  # -1 to 1 (failure to success)


@dataclass
class ConflictResolution:
    """How a conflict was resolved"""
    issue: str
    options: List[str]
    resolution: str
    reasoning: str
    precedents_cited: List[str]


@dataclass 
class DecisionTrace:
    """Complete record of a decision"""
    trace_id: str
    timestamp: str
    project_id: str
    feature_id: Optional[str]
    
    # What was being decided
    context: str  # "Architecture review for payment integration"
    decision_type: str  # architecture, security, code_review, requirements, etc.
    
    # Inputs that informed the decision
    inputs: List[Dict]  # List of DecisionInput as dicts
    
    # Precedents considered
    precedents_matched: List[Dict]  # List of PrecedentMatch as dicts
    precedents_rejected: List[str]  # IDs of precedents considered but not applicable
    
    # The decision process
    conflicts_resolved: List[Dict]  # List of ConflictResolution as dicts
    reasoning: str  # Full reasoning from the agent/voter
    
    # The outcome
    decision: str  # approved, rejected, approved_with_changes, deferred
    decision_summary: str  # Brief description of what was decided
    conditions: List[str]  # Any conditions attached
    
    # Actor
    actor: str  # Agent or voter ID
    actor_type: str  # agent, voter, human
    
    # Post-decision tracking (filled in later)
    outcome: Optional[str] = None  # success, partial_success, failure, unknown
    outcome_score: float = 0.0  # -1 to 1
    outcome_notes: str = ""
    outcome_timestamp: Optional[str] = None
    
    # Relationships
    parent_trace: Optional[str] = None  # If this decision led from another
    child_traces: List[str] = field(default_factory=list)
    related_traces: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None  # Vector embedding for similarity search


class ContextGraph:
    """
    The Context Graph - a queryable record of institutional reasoning.
    
    Stores decision traces and enables:
    - Precedent lookup: "How did we handle similar situations?"
    - Pattern recognition: "What approaches work for healthcare projects?"
    - Outcome tracking: "Did this decision lead to success or failure?"
    - Cross-project learning: "What can we learn from all past projects?"
    """
    
    def __init__(self, storage_dir: str = "context_graph"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        # Subdirectories
        (self.storage_dir / "traces").mkdir(exist_ok=True)
        (self.storage_dir / "projects").mkdir(exist_ok=True)
        (self.storage_dir / "patterns").mkdir(exist_ok=True)
        
        # Index file for quick lookups
        self.index_file = self.storage_dir / "index.json"
        self.index = self._load_index()
        
        # Initialize vector store if available
        self.vector_store = None
        if HAS_CHROMADB:
            self._init_vector_store()
    
    def _init_vector_store(self):
        """Initialize ChromaDB for similarity search"""
        try:
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.storage_dir / "vectors"),
                anonymized_telemetry=False
            ))
            self.vector_store = self.chroma_client.get_or_create_collection(
                name="decision_traces",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Warning: Could not initialize vector store: {e}")
            self.vector_store = None
    
    def _load_index(self) -> Dict:
        """Load the trace index"""
        if self.index_file.exists():
            with open(self.index_file, encoding="utf-8") as f:
                return json.load(f)
        return {
            "traces": {},  # trace_id -> metadata
            "by_project": {},  # project_id -> [trace_ids]
            "by_type": {},  # decision_type -> [trace_ids]
            "by_actor": {},  # actor -> [trace_ids]
            "by_outcome": {},  # outcome -> [trace_ids]
        }
    
    def _save_index(self):
        """Save the trace index"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)
    
    def _generate_trace_id(self, context: str, timestamp: str) -> str:
        """Generate unique trace ID"""
        content = f"{context}:{timestamp}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"TRACE-{hash_val.upper()}"
    
    # ════════════════════════════════════════════════════════════
    # CAPTURE - Recording decisions
    # ════════════════════════════════════════════════════════════
    
    def capture_decision(
        self,
        project_id: str,
        context: str,
        decision_type: str,
        inputs: List[DecisionInput],
        reasoning: str,
        decision: str,
        decision_summary: str,
        actor: str,
        actor_type: str = "agent",
        feature_id: Optional[str] = None,
        precedents_matched: List[PrecedentMatch] = None,
        conflicts_resolved: List[ConflictResolution] = None,
        conditions: List[str] = None,
        tags: List[str] = None,
        parent_trace: Optional[str] = None,
    ) -> DecisionTrace:
        """
        Capture a decision trace.
        
        This is the primary method for recording decisions.
        Call this whenever an agent or voter makes a significant decision.
        """
        timestamp = datetime.now().isoformat()
        trace_id = self._generate_trace_id(context, timestamp)
        
        trace = DecisionTrace(
            trace_id=trace_id,
            timestamp=timestamp,
            project_id=project_id,
            feature_id=feature_id,
            context=context,
            decision_type=decision_type,
            inputs=[asdict(i) if isinstance(i, DecisionInput) else i for i in inputs],
            precedents_matched=[asdict(p) if isinstance(p, PrecedentMatch) else p for p in (precedents_matched or [])],
            precedents_rejected=[],
            conflicts_resolved=[asdict(c) if isinstance(c, ConflictResolution) else c for c in (conflicts_resolved or [])],
            reasoning=reasoning,
            decision=decision,
            decision_summary=decision_summary,
            conditions=conditions or [],
            actor=actor,
            actor_type=actor_type,
            parent_trace=parent_trace,
            tags=tags or [],
        )
        
        # Save trace
        self._save_trace(trace)
        
        # Update index
        self._index_trace(trace)
        
        # Update parent if exists
        if parent_trace:
            self._add_child_trace(parent_trace, trace_id)
        
        return trace
    
    def _save_trace(self, trace: DecisionTrace):
        """Save a trace to disk"""
        trace_file = self.storage_dir / "traces" / f"{trace.trace_id}.yaml"
        with open(trace_file, "w", encoding="utf-8") as f:
            yaml.dump(asdict(trace), f, default_flow_style=False, sort_keys=False)
    
    def _index_trace(self, trace: DecisionTrace):
        """Add trace to index"""
        # Main index
        self.index["traces"][trace.trace_id] = {
            "project_id": trace.project_id,
            "decision_type": trace.decision_type,
            "decision": trace.decision,
            "actor": trace.actor,
            "timestamp": trace.timestamp,
            "context": trace.context[:100],
        }
        
        # By project
        if trace.project_id not in self.index["by_project"]:
            self.index["by_project"][trace.project_id] = []
        self.index["by_project"][trace.project_id].append(trace.trace_id)
        
        # By type
        if trace.decision_type not in self.index["by_type"]:
            self.index["by_type"][trace.decision_type] = []
        self.index["by_type"][trace.decision_type].append(trace.trace_id)
        
        # By actor
        if trace.actor not in self.index["by_actor"]:
            self.index["by_actor"][trace.actor] = []
        self.index["by_actor"][trace.actor].append(trace.trace_id)
        
        self._save_index()
        
        # Add to vector store if available
        if self.vector_store:
            self._embed_trace(trace)
    
    def _embed_trace(self, trace: DecisionTrace):
        """Add trace to vector store for similarity search"""
        # Create searchable text
        search_text = f"""
        Context: {trace.context}
        Type: {trace.decision_type}
        Decision: {trace.decision_summary}
        Reasoning: {trace.reasoning[:500]}
        Tags: {', '.join(trace.tags)}
        """
        
        try:
            self.vector_store.add(
                documents=[search_text],
                ids=[trace.trace_id],
                metadatas=[{
                    "project_id": trace.project_id,
                    "decision_type": trace.decision_type,
                    "decision": trace.decision,
                    "outcome": trace.outcome or "pending",
                    "outcome_score": trace.outcome_score,
                }]
            )
        except Exception as e:
            print(f"Warning: Could not embed trace: {e}")
    
    def _add_child_trace(self, parent_id: str, child_id: str):
        """Add child trace to parent"""
        trace = self.get_trace(parent_id)
        if trace:
            trace["child_traces"].append(child_id)
            trace_file = self.storage_dir / "traces" / f"{parent_id}.yaml"
            with open(trace_file, "w", encoding="utf-8") as f:
                yaml.dump(trace, f, default_flow_style=False, sort_keys=False)
    
    # ════════════════════════════════════════════════════════════
    # OUTCOME - Recording results
    # ════════════════════════════════════════════════════════════
    
    def record_outcome(
        self,
        trace_id: str,
        outcome: str,
        outcome_score: float,
        notes: str = ""
    ):
        """
        Record the outcome of a decision.
        
        Call this after deployment or when the impact of a decision becomes clear.
        
        Args:
            trace_id: The decision trace to update
            outcome: success, partial_success, failure, unknown
            outcome_score: -1.0 (total failure) to 1.0 (total success)
            notes: Additional context about the outcome
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return
        
        trace["outcome"] = outcome
        trace["outcome_score"] = outcome_score
        trace["outcome_notes"] = notes
        trace["outcome_timestamp"] = datetime.now().isoformat()
        
        # Save updated trace
        trace_file = self.storage_dir / "traces" / f"{trace_id}.yaml"
        with open(trace_file, "w", encoding="utf-8") as f:
            yaml.dump(trace, f, default_flow_style=False, sort_keys=False)
        
        # Update index
        if outcome not in self.index["by_outcome"]:
            self.index["by_outcome"][outcome] = []
        self.index["by_outcome"][outcome].append(trace_id)
        self._save_index()
        
        # Update vector store metadata
        if self.vector_store:
            try:
                self.vector_store.update(
                    ids=[trace_id],
                    metadatas=[{
                        "project_id": trace["project_id"],
                        "decision_type": trace["decision_type"],
                        "decision": trace["decision"],
                        "outcome": outcome,
                        "outcome_score": outcome_score,
                    }]
                )
            except:
                pass
    
    # ════════════════════════════════════════════════════════════
    # QUERY - Finding precedents
    # ════════════════════════════════════════════════════════════
    
    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """Get a single trace by ID"""
        trace_file = self.storage_dir / "traces" / f"{trace_id}.yaml"
        if trace_file.exists():
            with open(trace_file, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return None
    
    def find_precedents(
        self,
        context: str,
        decision_type: Optional[str] = None,
        limit: int = 5,
        min_outcome_score: float = -1.0,
        exclude_project: Optional[str] = None,
    ) -> List[PrecedentMatch]:
        """
        Find similar past decisions to inform current decision.
        
        Args:
            context: Description of current situation
            decision_type: Type of decision (architecture, security, etc.)
            limit: Maximum number of precedents to return
            min_outcome_score: Only return decisions with outcome >= this score
            exclude_project: Don't return precedents from this project
            
        Returns:
            List of PrecedentMatch objects, sorted by relevance
        """
        matches = []
        
        # Use vector search if available
        if self.vector_store:
            try:
                where_filter = {}
                if decision_type:
                    where_filter["decision_type"] = decision_type
                if min_outcome_score > -1.0:
                    where_filter["outcome_score"] = {"$gte": min_outcome_score}
                
                results = self.vector_store.query(
                    query_texts=[context],
                    n_results=limit * 2,  # Get extra to filter
                    where=where_filter if where_filter else None,
                )
                
                for i, trace_id in enumerate(results["ids"][0]):
                    trace = self.get_trace(trace_id)
                    if not trace:
                        continue
                    
                    # Skip if same project
                    if exclude_project and trace["project_id"] == exclude_project:
                        continue
                    
                    # Calculate similarity from distance
                    distance = results["distances"][0][i] if results["distances"] else 0.5
                    similarity = 1 - distance
                    
                    matches.append(PrecedentMatch(
                        trace_id=trace_id,
                        project=trace["project_id"],
                        similarity=similarity,
                        context=trace["context"],
                        decision=trace["decision_summary"],
                        outcome=trace.get("outcome", "pending"),
                        outcome_score=trace.get("outcome_score", 0.0),
                    ))
                    
                    if len(matches) >= limit:
                        break
                        
            except Exception as e:
                print(f"Vector search failed, falling back to keyword search: {e}")
        
        # Fallback to keyword search if no vector results
        if not matches:
            matches = self._keyword_search(context, decision_type, limit, exclude_project)
        
        return sorted(matches, key=lambda m: m.similarity, reverse=True)[:limit]
    
    def _keyword_search(
        self,
        context: str,
        decision_type: Optional[str],
        limit: int,
        exclude_project: Optional[str],
    ) -> List[PrecedentMatch]:
        """Simple keyword-based precedent search"""
        matches = []
        keywords = set(context.lower().split())
        
        # Get relevant trace IDs
        trace_ids = []
        if decision_type and decision_type in self.index["by_type"]:
            trace_ids = self.index["by_type"][decision_type]
        else:
            trace_ids = list(self.index["traces"].keys())
        
        for trace_id in trace_ids:
            trace = self.get_trace(trace_id)
            if not trace:
                continue
            
            if exclude_project and trace["project_id"] == exclude_project:
                continue
            
            # Simple keyword overlap scoring
            trace_text = f"{trace['context']} {trace['decision_summary']} {' '.join(trace.get('tags', []))}".lower()
            trace_keywords = set(trace_text.split())
            overlap = len(keywords & trace_keywords)
            
            if overlap > 0:
                similarity = overlap / max(len(keywords), len(trace_keywords))
                matches.append(PrecedentMatch(
                    trace_id=trace_id,
                    project=trace["project_id"],
                    similarity=similarity,
                    context=trace["context"],
                    decision=trace["decision_summary"],
                    outcome=trace.get("outcome", "pending"),
                    outcome_score=trace.get("outcome_score", 0.0),
                ))
        
        return matches
    
    def get_project_traces(self, project_id: str) -> List[Dict]:
        """Get all traces for a project"""
        trace_ids = self.index["by_project"].get(project_id, [])
        return [self.get_trace(tid) for tid in trace_ids if self.get_trace(tid)]
    
    def get_pattern_summary(self, decision_type: str) -> Dict:
        """
        Analyze patterns for a decision type across all projects.
        
        Returns insights like:
        - Common decisions and their outcomes
        - Success/failure rates
        - Common conflicts and resolutions
        """
        trace_ids = self.index["by_type"].get(decision_type, [])
        
        if not trace_ids:
            return {"error": "No traces found for this type"}
        
        traces = [self.get_trace(tid) for tid in trace_ids]
        traces = [t for t in traces if t]
        
        # Analyze outcomes
        outcomes = {}
        total_score = 0
        scored_count = 0
        
        for trace in traces:
            outcome = trace.get("outcome", "pending")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            
            if trace.get("outcome_score"):
                total_score += trace["outcome_score"]
                scored_count += 1
        
        avg_score = total_score / scored_count if scored_count > 0 else None
        
        # Find common decisions
        decisions = {}
        for trace in traces:
            summary = trace.get("decision_summary", "")[:50]
            decisions[summary] = decisions.get(summary, 0) + 1
        
        return {
            "decision_type": decision_type,
            "total_traces": len(traces),
            "outcome_distribution": outcomes,
            "average_outcome_score": avg_score,
            "common_decisions": dict(sorted(decisions.items(), key=lambda x: x[1], reverse=True)[:5]),
        }
    
    # ════════════════════════════════════════════════════════════
    # SYNTHESIS - Generating insights
    # ════════════════════════════════════════════════════════════
    
    def synthesize_precedents(self, precedents: List[PrecedentMatch]) -> str:
        """
        Create a natural language summary of relevant precedents.
        
        This is meant to be included in agent context.
        """
        if not precedents:
            return "No relevant precedents found."
        
        lines = ["## Relevant Precedents\n"]
        
        for i, p in enumerate(precedents, 1):
            outcome_emoji = "✅" if p.outcome_score > 0.5 else "⚠️" if p.outcome_score > 0 else "❌" if p.outcome_score < 0 else "❓"
            
            lines.append(f"### {i}. {p.project} ({p.similarity:.0%} similar)")
            lines.append(f"**Context:** {p.context}")
            lines.append(f"**Decision:** {p.decision}")
            lines.append(f"**Outcome:** {outcome_emoji} {p.outcome} (score: {p.outcome_score:+.1f})")
            lines.append("")
        
        # Add summary
        successful = [p for p in precedents if p.outcome_score > 0.5]
        failed = [p for p in precedents if p.outcome_score < 0]
        
        if successful:
            lines.append(f"**Pattern:** {len(successful)}/{len(precedents)} similar decisions led to positive outcomes.")
        if failed:
            lines.append(f"**Warning:** {len(failed)} similar decisions had negative outcomes.")
        
        return "\n".join(lines)
    
    def get_tribal_knowledge(self, tags: List[str]) -> List[str]:
        """
        Extract tribal knowledge (exception logic) relevant to given tags.
        
        Returns insights like:
        - "Healthcare projects always need HIPAA compliance review"
        - "Dave's clients prefer weekly progress reports"
        """
        knowledge = []
        
        # Search traces with matching tags
        for trace_id, meta in self.index["traces"].items():
            trace = self.get_trace(trace_id)
            if not trace:
                continue
            
            trace_tags = set(trace.get("tags", []))
            if trace_tags & set(tags):
                # Extract exception patterns from conflicts
                for conflict in trace.get("conflicts_resolved", []):
                    if conflict.get("reasoning"):
                        knowledge.append(conflict["reasoning"])
        
        return list(set(knowledge))[:10]  # Dedupe and limit


# ════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════

_context_graph = None

def get_context_graph(storage_dir: str = "context_graph") -> ContextGraph:
    """Get or create the global context graph instance"""
    global _context_graph
    if _context_graph is None:
        _context_graph = ContextGraph(storage_dir)
    return _context_graph


def capture_decision(
    project_id: str,
    context: str,
    decision_type: str,
    reasoning: str,
    decision: str,
    decision_summary: str,
    actor: str,
    **kwargs
) -> DecisionTrace:
    """Convenience function to capture a decision"""
    graph = get_context_graph()
    return graph.capture_decision(
        project_id=project_id,
        context=context,
        decision_type=decision_type,
        inputs=kwargs.get("inputs", []),
        reasoning=reasoning,
        decision=decision,
        decision_summary=decision_summary,
        actor=actor,
        **{k: v for k, v in kwargs.items() if k != "inputs"}
    )


def find_precedents(context: str, **kwargs) -> List[PrecedentMatch]:
    """Convenience function to find precedents"""
    graph = get_context_graph()
    return graph.find_precedents(context, **kwargs)


def record_outcome(trace_id: str, outcome: str, score: float, notes: str = ""):
    """Convenience function to record outcome"""
    graph = get_context_graph()
    graph.record_outcome(trace_id, outcome, score, notes)
