"""
Cross-System Synthesis Module

Gathers context from multiple external systems (Slack, Jira, email, meetings)
and synthesizes it into decision-relevant information.

This captures the "Reality (Event Clock)" - the actual conversations and
decisions that happen outside the System of Record.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json


@dataclass
class ExternalSignal:
    """A signal from an external system"""
    source: str  # slack, jira, email, meeting, github
    timestamp: str
    content: str
    author: Optional[str]
    channel: Optional[str]  # Slack channel, email thread, Jira project
    url: Optional[str]
    relevance_score: float  # 0-1 how relevant to current context
    signal_type: str  # approval, concern, requirement, context, decision


@dataclass
class SynthesizedContext:
    """Context synthesized from multiple sources"""
    summary: str
    signals: List[ExternalSignal]
    key_stakeholders: List[str]
    decisions_mentioned: List[str]
    concerns_raised: List[str]
    requirements_implied: List[str]
    tribal_knowledge: List[str]


class CrossSystemSynthesizer:
    """
    Synthesizes context from multiple external systems.
    
    Integrates with:
    - Slack (via MCP or API)
    - Jira (via MCP or API)
    - Email/Gmail (via MCP)
    - Meeting transcripts
    - GitHub (comments, PRs, issues)
    
    The goal is to capture "verbal/shadow approvals" and tribal knowledge
    that never makes it into the System of Record.
    """
    
    def __init__(self):
        self.mcp_clients = {}
        self.signal_cache = {}
    
    def register_mcp_client(self, source: str, client: Any):
        """Register an MCP client for a source"""
        self.mcp_clients[source] = client
    
    async def gather_context(
        self,
        project_name: str,
        feature_name: Optional[str] = None,
        keywords: List[str] = None,
        time_window_days: int = 30,
    ) -> SynthesizedContext:
        """
        Gather context from all connected systems.
        
        Args:
            project_name: Name of the project to search for
            feature_name: Specific feature being worked on
            keywords: Additional keywords to search
            time_window_days: How far back to search
            
        Returns:
            SynthesizedContext with aggregated information
        """
        signals = []
        
        # Build search terms
        search_terms = [project_name]
        if feature_name:
            search_terms.append(feature_name)
        if keywords:
            search_terms.extend(keywords)
        
        # Gather from each source
        if "slack" in self.mcp_clients:
            slack_signals = await self._gather_from_slack(
                search_terms, time_window_days
            )
            signals.extend(slack_signals)
        
        if "jira" in self.mcp_clients:
            jira_signals = await self._gather_from_jira(
                search_terms, time_window_days
            )
            signals.extend(jira_signals)
        
        if "gmail" in self.mcp_clients:
            email_signals = await self._gather_from_email(
                search_terms, time_window_days
            )
            signals.extend(email_signals)
        
        if "github" in self.mcp_clients:
            github_signals = await self._gather_from_github(
                search_terms, time_window_days
            )
            signals.extend(github_signals)
        
        # Also check local meeting transcripts
        transcript_signals = self._gather_from_transcripts(
            search_terms, time_window_days
        )
        signals.extend(transcript_signals)
        
        # Synthesize into coherent context
        return self._synthesize(signals, project_name, feature_name)
    
    async def _gather_from_slack(
        self,
        search_terms: List[str],
        days: int
    ) -> List[ExternalSignal]:
        """Gather signals from Slack"""
        signals = []
        client = self.mcp_clients.get("slack")
        
        if not client:
            return signals
        
        try:
            # Search Slack messages
            query = " ".join(search_terms)
            # This would call the actual MCP client
            # results = await client.search_messages(query, days=days)
            
            # For now, return empty - actual implementation would parse results
            pass
            
        except Exception as e:
            print(f"Slack search failed: {e}")
        
        return signals
    
    async def _gather_from_jira(
        self,
        search_terms: List[str],
        days: int
    ) -> List[ExternalSignal]:
        """Gather signals from Jira"""
        signals = []
        client = self.mcp_clients.get("jira")
        
        if not client:
            return signals
        
        try:
            # Search Jira issues
            # JQL query would go here
            pass
            
        except Exception as e:
            print(f"Jira search failed: {e}")
        
        return signals
    
    async def _gather_from_email(
        self,
        search_terms: List[str],
        days: int
    ) -> List[ExternalSignal]:
        """Gather signals from email"""
        signals = []
        client = self.mcp_clients.get("gmail")
        
        if not client:
            return signals
        
        try:
            # Search Gmail
            pass
            
        except Exception as e:
            print(f"Email search failed: {e}")
        
        return signals
    
    async def _gather_from_github(
        self,
        search_terms: List[str],
        days: int
    ) -> List[ExternalSignal]:
        """Gather signals from GitHub (PRs, issues, comments)"""
        signals = []
        client = self.mcp_clients.get("github")
        
        if not client:
            return signals
        
        try:
            # Search GitHub
            pass
            
        except Exception as e:
            print(f"GitHub search failed: {e}")
        
        return signals
    
    def _gather_from_transcripts(
        self,
        search_terms: List[str],
        days: int
    ) -> List[ExternalSignal]:
        """Gather signals from local meeting transcripts"""
        signals = []
        
        from pathlib import Path
        transcripts_dir = Path("transcripts")
        
        if not transcripts_dir.exists():
            return signals
        
        cutoff = datetime.now() - timedelta(days=days)
        
        for transcript_file in transcripts_dir.glob("*.txt"):
            try:
                # Check file date
                file_time = datetime.fromtimestamp(transcript_file.stat().st_mtime)
                if file_time < cutoff:
                    continue
                
                content = transcript_file.read_text(encoding="utf-8", errors="ignore")
                content_lower = content.lower()
                
                # Check if any search terms match
                if not any(term.lower() in content_lower for term in search_terms):
                    continue
                
                # Extract relevant sections
                relevant_sections = self._extract_relevant_sections(
                    content, search_terms
                )
                
                for section in relevant_sections:
                    signals.append(ExternalSignal(
                        source="meeting_transcript",
                        timestamp=file_time.isoformat(),
                        content=section[:500],
                        author=None,
                        channel=transcript_file.stem,
                        url=str(transcript_file),
                        relevance_score=0.7,
                        signal_type="context",
                    ))
                    
            except Exception as e:
                print(f"Error reading transcript {transcript_file}: {e}")
        
        return signals
    
    def _extract_relevant_sections(
        self,
        content: str,
        search_terms: List[str]
    ) -> List[str]:
        """Extract sections of content that contain search terms"""
        sections = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(term.lower() in line_lower for term in search_terms):
                # Get surrounding context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                section = "\n".join(lines[start:end])
                sections.append(section)
        
        return sections[:5]  # Limit to 5 sections
    
    def _synthesize(
        self,
        signals: List[ExternalSignal],
        project_name: str,
        feature_name: Optional[str]
    ) -> SynthesizedContext:
        """Synthesize signals into coherent context"""
        
        if not signals:
            return SynthesizedContext(
                summary=f"No external signals found for {project_name}",
                signals=[],
                key_stakeholders=[],
                decisions_mentioned=[],
                concerns_raised=[],
                requirements_implied=[],
                tribal_knowledge=[],
            )
        
        # Extract stakeholders
        stakeholders = list(set(
            s.author for s in signals if s.author
        ))
        
        # Extract decisions (look for decision-like language)
        decisions = []
        concerns = []
        requirements = []
        tribal = []
        
        decision_keywords = ["decided", "approved", "agreed", "go with", "chosen", "selected"]
        concern_keywords = ["worried", "concern", "risk", "issue", "problem", "careful"]
        requirement_keywords = ["must", "need to", "require", "should", "have to"]
        tribal_keywords = ["always", "never", "we usually", "dave prefers", "the client wants"]
        
        for signal in signals:
            content_lower = signal.content.lower()
            
            if any(kw in content_lower for kw in decision_keywords):
                decisions.append(signal.content[:100])
                signal.signal_type = "decision"
            
            if any(kw in content_lower for kw in concern_keywords):
                concerns.append(signal.content[:100])
                signal.signal_type = "concern"
            
            if any(kw in content_lower for kw in requirement_keywords):
                requirements.append(signal.content[:100])
                signal.signal_type = "requirement"
            
            if any(kw in content_lower for kw in tribal_keywords):
                tribal.append(signal.content[:100])
                signal.signal_type = "tribal_knowledge"
        
        # Build summary
        summary_parts = [f"Found {len(signals)} relevant signals for {project_name}"]
        if feature_name:
            summary_parts.append(f"(feature: {feature_name})")
        if decisions:
            summary_parts.append(f"{len(decisions)} decisions mentioned")
        if concerns:
            summary_parts.append(f"{len(concerns)} concerns raised")
        
        return SynthesizedContext(
            summary=". ".join(summary_parts),
            signals=signals,
            key_stakeholders=stakeholders[:10],
            decisions_mentioned=decisions[:5],
            concerns_raised=concerns[:5],
            requirements_implied=requirements[:5],
            tribal_knowledge=tribal[:5],
        )
    
    def format_for_agent(self, context: SynthesizedContext) -> str:
        """Format synthesized context for inclusion in agent prompt"""
        if not context.signals:
            return ""
        
        lines = ["## Cross-System Context\n"]
        lines.append(context.summary)
        lines.append("")
        
        if context.decisions_mentioned:
            lines.append("### Decisions Already Made")
            for d in context.decisions_mentioned:
                lines.append(f"- {d}")
            lines.append("")
        
        if context.concerns_raised:
            lines.append("### Concerns Raised")
            for c in context.concerns_raised:
                lines.append(f"- ⚠️ {c}")
            lines.append("")
        
        if context.requirements_implied:
            lines.append("### Implied Requirements")
            for r in context.requirements_implied:
                lines.append(f"- {r}")
            lines.append("")
        
        if context.tribal_knowledge:
            lines.append("### Tribal Knowledge")
            for t in context.tribal_knowledge:
                lines.append(f"- 💡 {t}")
            lines.append("")
        
        if context.key_stakeholders:
            lines.append(f"**Key Stakeholders:** {', '.join(context.key_stakeholders)}")
        
        return "\n".join(lines)


# Synchronous version for simpler use cases
class SimpleSynthesizer:
    """
    Simplified synthesizer for when MCP is not available.
    
    Works with local files and basic API calls.
    """
    
    def __init__(self, transcripts_dir: str = "transcripts"):
        self.transcripts_dir = Path(transcripts_dir) if transcripts_dir else None
        self.project_notes_dir = Path("projects")
    
    def gather_local_context(
        self,
        project_id: str,
        feature_name: Optional[str] = None,
    ) -> SynthesizedContext:
        """Gather context from local files only"""
        signals = []
        
        # Check project notes
        project_dir = self.project_notes_dir / project_id
        if project_dir.exists():
            signals.extend(self._scan_project_notes(project_dir, feature_name))
        
        # Check transcripts
        if self.transcripts_dir and self.transcripts_dir.exists():
            signals.extend(self._scan_transcripts(project_id, feature_name))
        
        return self._synthesize(signals, project_id, feature_name)
    
    def _scan_project_notes(
        self,
        project_dir: Path,
        feature_name: Optional[str]
    ) -> List[ExternalSignal]:
        """Scan project notes for relevant context"""
        signals = []
        
        for note_file in project_dir.glob("**/*.md"):
            try:
                content = note_file.read_text(encoding="utf-8")
                
                # Always include, these are project-specific
                signals.append(ExternalSignal(
                    source="project_notes",
                    timestamp=datetime.fromtimestamp(note_file.stat().st_mtime).isoformat(),
                    content=content[:500],
                    author=None,
                    channel=note_file.stem,
                    url=str(note_file),
                    relevance_score=0.9,
                    signal_type="context",
                ))
            except:
                pass
        
        return signals
    
    def _scan_transcripts(
        self,
        project_id: str,
        feature_name: Optional[str]
    ) -> List[ExternalSignal]:
        """Scan meeting transcripts"""
        signals = []
        search_terms = [project_id]
        if feature_name:
            search_terms.append(feature_name)
        
        for transcript in self.transcripts_dir.glob("*.txt"):
            try:
                content = transcript.read_text(encoding="utf-8", errors="ignore")
                if any(term.lower() in content.lower() for term in search_terms):
                    signals.append(ExternalSignal(
                        source="transcript",
                        timestamp=datetime.fromtimestamp(transcript.stat().st_mtime).isoformat(),
                        content=content[:500],
                        author=None,
                        channel=transcript.stem,
                        url=str(transcript),
                        relevance_score=0.7,
                        signal_type="context",
                    ))
            except:
                pass
        
        return signals
    
    def _synthesize(
        self,
        signals: List[ExternalSignal],
        project_id: str,
        feature_name: Optional[str]
    ) -> SynthesizedContext:
        """Basic synthesis"""
        return SynthesizedContext(
            summary=f"Found {len(signals)} local context signals for {project_id}",
            signals=signals,
            key_stakeholders=[],
            decisions_mentioned=[],
            concerns_raised=[],
            requirements_implied=[],
            tribal_knowledge=[],
        )


from pathlib import Path
