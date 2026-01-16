"""
Ingest Planner Module - Phase 2

Generates:
- Improvement roadmap with prioritization
- AI implementation opportunities
- Milestone breakdown
- Recommendations report
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from datetime import datetime
from core.assessment import AssessmentReport, Finding


@dataclass
class RoadmapItem:
    """Single actionable item in the roadmap"""
    id: str
    title: str
    description: str
    category: str
    priority: str  # critical, high, medium, low
    effort_hours: float
    impact: str  # high, medium, low
    
    # Implementation
    tasks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    
    # AI capability
    ai_can_implement: bool = False
    ai_approach: str = ""
    ai_confidence: str = ""  # high, medium, low
    
    # Tracking
    status: str = "pending"  # pending, in_progress, completed, skipped
    finding_id: str = ""


@dataclass
class AIOpportunity:
    """Opportunity to add AI features to the application"""
    id: str
    title: str
    description: str
    category: str  # user_value, efficiency, functionality, automation
    
    # Value proposition
    user_benefit: str
    business_value: str
    technical_benefit: str
    
    # Implementation
    approach: str
    integrations_needed: List[str]
    estimated_hours: float
    complexity: str  # low, medium, high
    
    # Prioritization
    priority: str
    quick_win: bool


@dataclass
class Milestone:
    """Development milestone grouping roadmap items"""
    id: str
    name: str
    description: str
    target: str  # e.g., "Week 1", "Sprint 1"
    
    items: List[str]  # RoadmapItem IDs
    estimated_hours: float
    
    deliverables: List[str]
    success_criteria: List[str]
    dependencies: List[str]  # Other milestone IDs


@dataclass
class PlanningReport:
    """Complete Phase 2 Planning Report"""
    project_name: str
    planned_at: str
    
    # Summary
    total_items: int
    critical_count: int
    quick_wins_count: int
    ai_opportunities_count: int
    total_hours: float
    
    # Content
    roadmap: List[RoadmapItem]
    ai_opportunities: List[AIOpportunity]
    milestones: List[Milestone]
    
    # Recommendations
    recommended_approach: str
    risk_factors: List[str]
    dependencies: List[str]


class IngestPlanner:
    """Creates improvement plan from assessment"""
    
    def __init__(self, assessment: AssessmentReport):
        self.assessment = assessment
        self.roadmap: List[RoadmapItem] = []
        self.ai_opps: List[AIOpportunity] = []
        self.counter = 0
        self.ai_counter = 0
    
    def create_plan(self) -> PlanningReport:
        """Generate complete planning report"""
        
        # Convert findings to roadmap items
        self._generate_roadmap()
        
        # Generate AI opportunities
        self._generate_ai_opportunities()
        
        # Create milestones
        milestones = self._create_milestones()
        
        # Calculate totals
        total_hours = sum(item.effort_hours for item in self.roadmap)
        critical = sum(1 for item in self.roadmap if item.priority == 'critical')
        quick_wins = sum(1 for item in self.roadmap if item.effort_hours <= 2 and item.impact == 'high')
        
        return PlanningReport(
            project_name=self.assessment.project_name,
            planned_at=datetime.now().isoformat(),
            total_items=len(self.roadmap),
            critical_count=critical,
            quick_wins_count=quick_wins,
            ai_opportunities_count=len(self.ai_opps),
            total_hours=total_hours,
            roadmap=self.roadmap,
            ai_opportunities=self.ai_opps,
            milestones=milestones,
            recommended_approach=self._get_recommendation(),
            risk_factors=self._get_risks(),
            dependencies=self._get_dependencies()
        )
    
    def _generate_roadmap(self):
        """Convert findings to actionable roadmap items"""
        
        for finding in self.assessment.all_findings:
            self.counter += 1
            
            # Map severity to priority
            priority_map = {
                'critical': 'critical',
                'high': 'high',
                'medium': 'medium',
                'low': 'low',
                'info': 'low'
            }
            
            # Determine impact
            impact = 'high' if finding.severity in ['critical', 'high'] else \
                    'medium' if finding.severity == 'medium' else 'low'
            
            item = RoadmapItem(
                id=f"R{self.counter:03d}",
                title=finding.title,
                description=finding.description,
                category=finding.category,
                priority=priority_map.get(finding.severity, 'medium'),
                effort_hours=finding.effort_hours,
                impact=impact,
                tasks=self._generate_tasks(finding),
                dependencies=[],
                affected_files=[finding.location] if finding.location else [],
                ai_can_implement=finding.ai_can_fix,
                ai_approach=finding.ai_approach,
                ai_confidence='high' if finding.ai_can_fix else '',
                finding_id=finding.id
            )
            self.roadmap.append(item)
    
    def _generate_tasks(self, finding: Finding) -> List[str]:
        """Generate implementation tasks"""
        tasks = []
        
        if finding.recommendation:
            tasks.append(finding.recommendation)
        
        # Category-specific tasks
        cat = finding.category
        if cat == 'security':
            tasks.extend(["Review security implications", "Test for vulnerabilities"])
        elif cat == 'testing':
            tasks.extend(["Identify test scenarios", "Write test cases", "Verify coverage"])
        elif cat in ['ux_navigation', 'ux_styling', 'ux_accessibility']:
            tasks.extend(["Review UX impact", "Test across devices"])
        elif cat == 'documentation':
            tasks.extend(["Draft content", "Review accuracy"])
        elif cat == 'architecture':
            tasks.extend(["Plan changes", "Update architecture docs"])
        
        return tasks[:5]
    
    def _generate_ai_opportunities(self):
        """Generate AI enhancement opportunities for the app"""
        
        # Standard opportunities based on app patterns
        standard = [
            AIOpportunity(
                id="AI001",
                title="Smart Search with Natural Language",
                description="Allow users to search using conversational queries instead of keywords",
                category="user_value",
                user_benefit="Find information faster with natural language",
                business_value="Increased engagement and user satisfaction",
                technical_benefit="Better search relevance",
                approach="Integrate semantic search with LLM query understanding",
                integrations_needed=["OpenAI/Anthropic API", "Vector database"],
                estimated_hours=16,
                complexity="medium",
                priority="high",
                quick_win=False
            ),
            AIOpportunity(
                id="AI002",
                title="AI-Powered Form Assistance",
                description="Auto-complete and validate form inputs intelligently",
                category="user_value",
                user_benefit="Faster form completion with fewer errors",
                business_value="Higher conversion rates",
                technical_benefit="Better data quality",
                approach="LLM-based field suggestions with validation",
                integrations_needed=["LLM API"],
                estimated_hours=8,
                complexity="low",
                priority="high",
                quick_win=True
            ),
            AIOpportunity(
                id="AI003",
                title="Content Summarization",
                description="Auto-generate summaries of long content or documents",
                category="user_value",
                user_benefit="Quick understanding of key points",
                business_value="Improved user productivity",
                technical_benefit="Simple API integration",
                approach="LLM summarization with configurable length",
                integrations_needed=["LLM API"],
                estimated_hours=4,
                complexity="low",
                priority="medium",
                quick_win=True
            ),
            AIOpportunity(
                id="AI004",
                title="Intelligent Error Messages",
                description="AI analyzes errors and suggests fixes to users",
                category="user_value",
                user_benefit="Self-service problem resolution",
                business_value="Reduced support costs",
                technical_benefit="Better error handling UX",
                approach="Error pattern analysis with LLM suggestions",
                integrations_needed=["LLM API", "Error tracking"],
                estimated_hours=12,
                complexity="medium",
                priority="medium",
                quick_win=False
            ),
            AIOpportunity(
                id="AI005",
                title="Automated Documentation",
                description="Generate and maintain docs from code and usage",
                category="efficiency",
                user_benefit="Always current documentation",
                business_value="Faster onboarding, reduced debt",
                technical_benefit="Docs stay in sync with code",
                approach="AI analyzes code and generates markdown/HTML docs",
                integrations_needed=["LLM API", "Build pipeline"],
                estimated_hours=12,
                complexity="medium",
                priority="medium",
                quick_win=False
            ),
            AIOpportunity(
                id="AI006",
                title="Smart Notifications",
                description="AI determines what to notify users about and when",
                category="user_value",
                user_benefit="Relevant notifications, less noise",
                business_value="Higher engagement rates",
                technical_benefit="Personalization without complex rules",
                approach="ML model for notification relevance scoring",
                integrations_needed=["LLM API", "User analytics"],
                estimated_hours=20,
                complexity="high",
                priority="low",
                quick_win=False
            ),
            AIOpportunity(
                id="AI007",
                title="Code Review Assistant",
                description="AI reviews PRs for issues and suggests improvements",
                category="efficiency",
                user_benefit="Faster, more thorough code review",
                business_value="Higher code quality, fewer bugs",
                technical_benefit="Consistent review standards",
                approach="LLM analyzes diffs and comments on PRs",
                integrations_needed=["GitHub API", "LLM API"],
                estimated_hours=16,
                complexity="medium",
                priority="high",
                quick_win=False
            ),
            AIOpportunity(
                id="AI008",
                title="Personalized Recommendations",
                description="Suggest relevant content/actions based on user behavior",
                category="user_value",
                user_benefit="Discover relevant content proactively",
                business_value="Higher engagement and retention",
                technical_benefit="Better content utilization",
                approach="Collaborative filtering enhanced with LLM",
                integrations_needed=["Analytics", "LLM API", "Vector DB"],
                estimated_hours=24,
                complexity="high",
                priority="medium",
                quick_win=False
            ),
        ]
        
        self.ai_opps = standard
        
        # Add opportunities from AI-fixable findings
        for finding in self.assessment.all_findings:
            if finding.ai_can_fix:
                self.ai_counter += 1
                self.ai_opps.append(AIOpportunity(
                    id=f"AI{100 + self.ai_counter:03d}",
                    title=f"AI Fix: {finding.title}",
                    description=finding.ai_approach,
                    category="automation",
                    user_benefit="Automated improvement",
                    business_value="Reduced manual effort",
                    technical_benefit=finding.recommendation,
                    approach=finding.ai_approach,
                    integrations_needed=["AI Coding Assistant"],
                    estimated_hours=finding.effort_hours * 0.5,  # AI is faster
                    complexity="low" if finding.effort_hours < 4 else "medium",
                    priority="high" if finding.severity in ['critical', 'high'] else "medium",
                    quick_win=finding.effort_hours <= 2
                ))
    
    def _create_milestones(self) -> List[Milestone]:
        """Group roadmap items into milestones"""
        milestones = []
        
        # M1: Critical fixes
        critical = [i for i in self.roadmap if i.priority == 'critical']
        if critical:
            milestones.append(Milestone(
                id="M1",
                name="Critical Fixes",
                description="Address all critical issues immediately",
                target="Immediate",
                items=[i.id for i in critical],
                estimated_hours=sum(i.effort_hours for i in critical),
                deliverables=["All critical issues resolved", "Security vulnerabilities patched"],
                success_criteria=["No critical findings", "All tests passing"],
                dependencies=[]
            ))
        
        # M2: Quick wins (low effort, any impact)
        quick = [i for i in self.roadmap if i.effort_hours <= 2 and i.priority != 'critical']
        if quick:
            milestones.append(Milestone(
                id="M2",
                name="Quick Wins",
                description="Low-effort improvements for fast progress",
                target="Week 1",
                items=[i.id for i in quick[:10]],
                estimated_hours=sum(i.effort_hours for i in quick[:10]),
                deliverables=["Visible improvements", "Team momentum"],
                success_criteria=["All quick wins completed"],
                dependencies=["M1"] if critical else []
            ))
        
        # M3: UX improvements
        ux = [i for i in self.roadmap if i.category.startswith('ux_') and i.id not in 
              [x.id for m in milestones for x in self.roadmap if x.id in m.items]]
        if ux:
            milestones.append(Milestone(
                id="M3",
                name="UX Improvements",
                description="Enhance navigation, styling, and accessibility",
                target="Week 2-3",
                items=[i.id for i in ux[:8]],
                estimated_hours=sum(i.effort_hours for i in ux[:8]),
                deliverables=["Improved accessibility score", "Consistent styling", "Better navigation"],
                success_criteria=["Accessibility audit passing", "Style guide implemented"],
                dependencies=["M2"] if quick else ["M1"] if critical else []
            ))
        
        # M4: Code quality & architecture
        code = [i for i in self.roadmap if i.category in ['code_quality', 'architecture', 'tech_debt']
                and i.id not in [x.id for m in milestones for x in self.roadmap if x.id in m.items]]
        if code:
            milestones.append(Milestone(
                id="M4",
                name="Code Quality",
                description="Improve code organization and maintainability",
                target="Week 3-4",
                items=[i.id for i in code[:8]],
                estimated_hours=sum(i.effort_hours for i in code[:8]),
                deliverables=["Linting configured", "Code reorganized", "Tech debt reduced"],
                success_criteria=["Linting passing", "Architecture documented"],
                dependencies=["M3"] if ux else ["M2"] if quick else []
            ))
        
        # M5: Testing & documentation
        test_doc = [i for i in self.roadmap if i.category in ['testing', 'documentation']
                    and i.id not in [x.id for m in milestones for x in self.roadmap if x.id in m.items]]
        if test_doc:
            milestones.append(Milestone(
                id="M5",
                name="Testing & Docs",
                description="Establish test coverage and documentation",
                target="Week 4-5",
                items=[i.id for i in test_doc[:8]],
                estimated_hours=sum(i.effort_hours for i in test_doc[:8]),
                deliverables=["Test suite", "Updated documentation"],
                success_criteria=["Test coverage > 60%", "README complete"],
                dependencies=["M4"] if code else []
            ))
        
        # M6: AI enhancements
        ai_items = [i for i in self.roadmap if i.ai_can_implement]
        if ai_items:
            milestones.append(Milestone(
                id="M6",
                name="AI Enhancements",
                description="Implement AI-powered improvements",
                target="Week 5+",
                items=[i.id for i in ai_items[:5]],
                estimated_hours=sum(i.effort_hours for i in ai_items[:5]),
                deliverables=["AI features implemented"],
                success_criteria=["Features functional", "User feedback positive"],
                dependencies=["M4"]
            ))
        
        return milestones
    
    def _get_recommendation(self) -> str:
        """Generate overall recommendation"""
        score = self.assessment.overall_score
        critical = self.assessment.critical_count
        
        if critical > 0:
            return f"URGENT: Address {critical} critical issues before other work. Focus on security and stability."
        elif score < 50:
            return "Significant improvement needed. Start with quick wins for momentum, then systematically address each area."
        elif score < 70:
            return "Codebase is acceptable. Prioritize high-impact items and establish better practices incrementally."
        else:
            return "Codebase is in good shape. Focus on refinements and consider AI enhancements for added value."
    
    def _get_risks(self) -> List[str]:
        """Identify implementation risks"""
        risks = []
        
        if self.assessment.critical_count > 3:
            risks.append("Multiple critical issues may indicate deeper problems")
        if self.assessment.testing.score < 40:
            risks.append("Low test coverage makes refactoring risky")
        if self.assessment.documentation.score < 40:
            risks.append("Poor documentation may cause knowledge gaps")
        if len(self.roadmap) > 30:
            risks.append("Large backlog may overwhelm team")
        
        return risks
    
    def _get_dependencies(self) -> List[str]:
        """Get external dependencies"""
        deps = set()
        for opp in self.ai_opps:
            deps.update(opp.integrations_needed)
        return list(deps)


def create_plan(assessment: AssessmentReport) -> PlanningReport:
    """Create improvement plan from assessment"""
    planner = IngestPlanner(assessment)
    return planner.create_plan()
