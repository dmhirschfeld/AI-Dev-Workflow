"""
Service Catalog Integration

Detects reusable service candidates from requirements and
recommends existing services from the catalog.

Used by:
- Solutions Architect: Check catalog before designing
- Business Analyst: Identify standard functionality
- Code Reviewer: Ensure services are used when available
"""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class ServiceMatch:
    """A detected service from the catalog"""
    service_id: str
    service_name: str
    confidence: float  # 0.0 - 1.0
    matched_keywords: List[str]
    matched_patterns: List[str]
    features_needed: List[str]
    maturity: str
    repository: Optional[str] = None


@dataclass
class ServiceRecommendation:
    """Recommendation for using an existing service"""
    service_id: str
    service_name: str
    reason: str
    features_available: List[str]
    features_needed: List[str]
    integration_notes: str
    alternative: Optional[str] = None  # If service is planned/beta


@dataclass
class ExtractionCandidate:
    """A candidate for extracting into a new reusable service"""
    name: str
    description: str
    reason: str
    similar_to: Optional[str]  # Existing service it resembles
    reuse_potential: str  # "high", "medium", "low"
    suggested_features: List[str]


class ServiceCatalog:
    """
    Service catalog for detecting and recommending reusable services.
    """
    
    def __init__(self, catalog_path: str = "catalog/services.yaml"):
        self.catalog_path = Path(catalog_path)
        self.catalog: Dict[str, Any] = {}
        self.detection_patterns: Dict[str, Any] = {}
        
        self._load_catalog()
    
    def _load_catalog(self):
        """Load the service catalog"""
        if self.catalog_path.exists():
            with open(self.catalog_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.catalog = data.get("services", {})
                self.detection_patterns = data.get("detection_patterns", {})
    
    def detect_services(
        self,
        requirements: str,
        feature_description: str = ""
    ) -> List[ServiceMatch]:
        """
        Detect which services from the catalog match the requirements.
        
        Args:
            requirements: Full requirements document
            feature_description: Brief feature description
            
        Returns:
            List of matched services, sorted by confidence
        """
        text = f"{requirements}\n{feature_description}".lower()
        matches = []
        
        for service_id, patterns in self.detection_patterns.items():
            if service_id not in self.catalog:
                continue
            
            service = self.catalog[service_id]
            matched_keywords = []
            matched_patterns = []
            
            # Check keywords
            keywords = patterns.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in text:
                    matched_keywords.append(keyword)
            
            # Check regex patterns
            requirement_patterns = patterns.get("requirement_patterns", [])
            for pattern in requirement_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_patterns.append(pattern)
            
            # Calculate confidence
            if matched_keywords or matched_patterns:
                keyword_score = len(matched_keywords) / max(len(keywords), 1)
                pattern_score = len(matched_patterns) / max(len(requirement_patterns), 1)
                
                # Weight patterns higher than keywords
                confidence = (keyword_score * 0.4) + (pattern_score * 0.6)
                confidence = min(confidence * 1.5, 1.0)  # Boost but cap at 1.0
                
                # Detect which features are needed
                features_needed = self._detect_needed_features(
                    service_id,
                    text,
                    matched_keywords
                )
                
                matches.append(ServiceMatch(
                    service_id=service_id,
                    service_name=service.get("name", service_id),
                    confidence=round(confidence, 2),
                    matched_keywords=matched_keywords,
                    matched_patterns=matched_patterns,
                    features_needed=features_needed,
                    maturity=service.get("maturity", "unknown"),
                    repository=service.get("repository"),
                ))
        
        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
    
    def _detect_needed_features(
        self,
        service_id: str,
        text: str,
        matched_keywords: List[str]
    ) -> List[str]:
        """Detect which features of a service are needed"""
        service = self.catalog.get(service_id, {})
        features = service.get("features", [])
        
        needed = []
        for feature in features:
            feature_name = feature.get("name", "").lower()
            feature_id = feature.get("id", "")
            
            # Simple keyword matching in feature name
            for keyword in matched_keywords:
                if keyword.lower() in feature_name:
                    needed.append(feature_id)
                    break
            
            # Check if feature name appears in text
            if feature_name in text:
                if feature_id not in needed:
                    needed.append(feature_id)
        
        return needed
    
    def get_recommendations(
        self,
        requirements: str,
        confidence_threshold: float = 0.3
    ) -> List[ServiceRecommendation]:
        """
        Get service recommendations for requirements.
        
        Args:
            requirements: Requirements document
            confidence_threshold: Minimum confidence to include
            
        Returns:
            List of recommendations
        """
        matches = self.detect_services(requirements)
        recommendations = []
        
        for match in matches:
            if match.confidence < confidence_threshold:
                continue
            
            service = self.catalog.get(match.service_id, {})
            
            # Get all available features
            features_available = [
                f.get("id") for f in service.get("features", [])
                if f.get("status") in ("production", "stable")
            ]
            
            # Build integration notes
            integration_notes = self._build_integration_notes(service)
            
            # Check for alternatives if not production ready
            alternative = None
            if match.maturity not in ("production", "stable"):
                alternative = f"Service is {match.maturity}. Consider building custom or waiting."
            
            recommendations.append(ServiceRecommendation(
                service_id=match.service_id,
                service_name=match.service_name,
                reason=f"Matched: {', '.join(match.matched_keywords[:3])}",
                features_available=features_available,
                features_needed=match.features_needed,
                integration_notes=integration_notes,
                alternative=alternative,
            ))
        
        return recommendations
    
    def _build_integration_notes(self, service: Dict[str, Any]) -> str:
        """Build integration notes for a service"""
        notes = []
        
        # Required config
        config = service.get("configuration", {})
        required = config.get("required", [])
        if required:
            notes.append(f"Required config: {', '.join(required[:3])}")
        
        # Dependencies
        requires = service.get("requires_services", [])
        if requires:
            notes.append(f"Requires: {', '.join(requires)}")
        
        # API endpoint
        integration = service.get("integration", {})
        if integration.get("cloud_run_url"):
            notes.append(f"URL: {integration['cloud_run_url']}")
        
        return ". ".join(notes) if notes else "See catalog for details."
    
    def get_service_details(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get full details for a service"""
        return self.catalog.get(service_id)
    
    def identify_extraction_candidates(
        self,
        architecture: str,
        implementation_tasks: List[Dict[str, Any]]
    ) -> List[ExtractionCandidate]:
        """
        Identify components in the architecture that could become
        reusable services.
        
        Args:
            architecture: Architecture document
            implementation_tasks: List of implementation tasks
            
        Returns:
            Candidates for service extraction
        """
        candidates = []
        
        # Patterns that suggest reusable service potential
        extraction_patterns = [
            {
                "pattern": r"(authentication|auth|login|oauth)",
                "name": "Authentication Service",
                "similar_to": "auth-service",
            },
            {
                "pattern": r"(notification|email|sms|alert|push)",
                "name": "Notification Service",
                "similar_to": "notification-service",
            },
            {
                "pattern": r"(file.?upload|storage|attachment|document)",
                "name": "File Storage Service",
                "similar_to": "file-service",
            },
            {
                "pattern": r"(billing|payment|subscription|invoice)",
                "name": "Billing Service",
                "similar_to": "billing-service",
            },
            {
                "pattern": r"(audit|activity.?log|tracking|history)",
                "name": "Audit Service",
                "similar_to": "audit-service",
            },
            {
                "pattern": r"(permission|role|rbac|access.?control)",
                "name": "RBAC Service",
                "similar_to": "rbac-service",
            },
            {
                "pattern": r"(webhook|callback|integration)",
                "name": "Webhook Service",
                "similar_to": "webhook-service",
            },
            {
                "pattern": r"(search|index|elasticsearch|algolia)",
                "name": "Search Service",
                "similar_to": None,
            },
            {
                "pattern": r"(report|analytics|dashboard|metrics)",
                "name": "Analytics Service",
                "similar_to": "analytics-service",
            },
        ]
        
        text = architecture.lower()
        
        for extraction in extraction_patterns:
            if re.search(extraction["pattern"], text, re.IGNORECASE):
                similar = extraction["similar_to"]
                
                # Check if we already have this service
                if similar and similar in self.catalog:
                    existing = self.catalog[similar]
                    maturity = existing.get("maturity", "unknown")
                    
                    if maturity in ("production", "stable"):
                        # Already have it - don't flag as candidate
                        continue
                    else:
                        # Exists but not ready - flag as potential contribution
                        candidates.append(ExtractionCandidate(
                            name=extraction["name"],
                            description=f"Could contribute to existing {similar}",
                            reason=f"Pattern detected: {extraction['pattern']}",
                            similar_to=similar,
                            reuse_potential="high",
                            suggested_features=[],
                        ))
                else:
                    # New service candidate
                    candidates.append(ExtractionCandidate(
                        name=extraction["name"],
                        description=f"Potential new reusable service",
                        reason=f"Pattern detected: {extraction['pattern']}",
                        similar_to=similar,
                        reuse_potential="medium",
                        suggested_features=[],
                    ))
        
        return candidates
    
    def format_for_architect(
        self,
        requirements: str
    ) -> str:
        """
        Format service recommendations for the Solutions Architect.
        
        Args:
            requirements: Requirements document
            
        Returns:
            Formatted string to include in architect prompt
        """
        recommendations = self.get_recommendations(requirements)
        
        if not recommendations:
            return "No existing services detected for these requirements."
        
        lines = [
            "## Existing Services Available",
            "",
            "The following reusable services match your requirements:",
            "",
        ]
        
        for rec in recommendations:
            lines.append(f"### {rec.service_name} (`{rec.service_id}`)")
            lines.append(f"- **Reason**: {rec.reason}")
            lines.append(f"- **Features available**: {', '.join(rec.features_available[:5])}")
            
            if rec.features_needed:
                lines.append(f"- **Features you need**: {', '.join(rec.features_needed)}")
            
            lines.append(f"- **Integration**: {rec.integration_notes}")
            
            if rec.alternative:
                lines.append(f"- **Note**: {rec.alternative}")
            
            lines.append("")
        
        lines.extend([
            "---",
            "**IMPORTANT**: Use existing services instead of building custom.",
            "Only build custom if the service doesn't exist or doesn't meet requirements.",
        ])
        
        return "\n".join(lines)


class DesignSystem:
    """
    Design system catalog for UI/UX standards.
    """
    
    def __init__(self, design_system_path: str = "catalog/design_system.yaml"):
        self.path = Path(design_system_path)
        self.data: Dict[str, Any] = {}
        
        self._load()
    
    def _load(self):
        """Load the design system"""
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.data = yaml.safe_load(f)
    
    def get_tokens(self) -> Dict[str, Any]:
        """Get design tokens"""
        return self.data.get("tokens", {})
    
    def get_component(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get component definition"""
        components = self.data.get("components", {})
        return components.get(component_id)
    
    def get_layout(self, layout_id: str) -> Optional[Dict[str, Any]]:
        """Get layout pattern"""
        layouts = self.data.get("layouts", {})
        return layouts.get(layout_id)
    
    def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get interaction pattern"""
        interactions = self.data.get("interactions", {})
        return interactions.get(interaction_id)
    
    def detect_ui_requirements(self, requirements: str) -> List[str]:
        """
        Detect which UI components are needed based on requirements.
        
        Returns list of component IDs
        """
        text = requirements.lower()
        detected = []
        
        patterns = {
            "data_grid": ["list", "table", "grid", "records", "items"],
            "slide_out_panel": ["details", "edit", "side panel", "drawer"],
            "modal": ["confirm", "dialog", "popup", "alert"],
            "form": ["create", "edit", "input", "submit"],
            "sidebar_nav": ["navigation", "menu", "dashboard", "admin"],
            "toast": ["notification", "message", "alert"],
            "select": ["dropdown", "select", "choose", "pick"],
            "card": ["card", "tile", "widget"],
        }
        
        for component_id, keywords in patterns.items():
            for keyword in keywords:
                if keyword in text:
                    if component_id not in detected:
                        detected.append(component_id)
                    break
        
        return detected
    
    def format_for_designer(
        self,
        requirements: str,
        project_tokens: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format design system info for the UI/UX Designer.
        
        Args:
            requirements: Requirements document
            project_tokens: Project-specific token overrides
            
        Returns:
            Formatted string to include in designer prompt
        """
        detected = self.detect_ui_requirements(requirements)
        components = self.data.get("components", {})
        
        lines = [
            "## Design System Reference",
            "",
            "Use these standard components from our design system:",
            "",
        ]
        
        for component_id in detected:
            if component_id in components:
                comp = components[component_id]
                lines.append(f"### {comp.get('name', component_id)}")
                lines.append(f"{comp.get('description', '')[:200]}")
                
                variants = comp.get("variants", [])
                if variants:
                    if isinstance(variants[0], str):
                        lines.append(f"- Variants: {', '.join(variants[:4])}")
                    else:
                        variant_names = [v.get("name", str(v)) for v in variants[:4]]
                        lines.append(f"- Variants: {', '.join(variant_names)}")
                
                lines.append("")
        
        # Add project tokens if provided
        if project_tokens:
            lines.extend([
                "## Project Design Tokens",
                "",
                "This project uses custom colors/fonts:",
                "",
            ])
            
            colors = project_tokens.get("colors", {})
            if colors.get("primary"):
                lines.append(f"- Primary color: {colors['primary'].get('default')}")
            
            typography = project_tokens.get("typography", {})
            if typography.get("font_family"):
                lines.append(f"- Font: {typography['font_family'].get('sans')}")
        
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════

_catalog: Optional[ServiceCatalog] = None
_design_system: Optional[DesignSystem] = None


def get_service_catalog() -> ServiceCatalog:
    """Get or create the service catalog singleton"""
    global _catalog
    if _catalog is None:
        _catalog = ServiceCatalog()
    return _catalog


def get_design_system() -> DesignSystem:
    """Get or create the design system singleton"""
    global _design_system
    if _design_system is None:
        _design_system = DesignSystem()
    return _design_system


def check_for_existing_services(requirements: str) -> str:
    """
    Check if requirements can be met with existing services.
    Returns formatted recommendations for architect.
    """
    catalog = get_service_catalog()
    return catalog.format_for_architect(requirements)


def get_ui_guidelines(
    requirements: str,
    project_tokens: Optional[Dict[str, Any]] = None
) -> str:
    """
    Get UI/UX guidelines for requirements.
    Returns formatted guidelines for designer.
    """
    design_system = get_design_system()
    return design_system.format_for_designer(requirements, project_tokens)


def check_service_usage(
    architecture: str,
    requirements: str
) -> List[str]:
    """
    Check if architecture properly uses available services.
    Returns list of warnings if services should be used but aren't.
    """
    catalog = get_service_catalog()
    warnings = []
    
    # Detect services that match requirements
    recommendations = catalog.get_recommendations(requirements, confidence_threshold=0.5)
    
    for rec in recommendations:
        if rec.service_id not in architecture.lower():
            warnings.append(
                f"Consider using {rec.service_name} ({rec.service_id}) "
                f"instead of building custom. Reason: {rec.reason}"
            )
    
    return warnings
