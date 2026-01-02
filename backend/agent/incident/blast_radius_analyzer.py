"""
BlastRadiusAnalyzer — System-Level Thinking

Advanced impact analysis system that analyzes the "blast radius" of changes
across services, dependencies, and system boundaries. This enables NAVI to
think at the system level and understand how changes propagate through
the architecture.

Key Capabilities:
- Analyze change impact across services
- Map dependency relationships  
- Predict downstream effects
- Assess architectural risk
- Generate system-level recommendations
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional, Any
from .incident_store import Incident, IncidentType

logger = logging.getLogger(__name__)

@dataclass
class ImpactAnalysis:
    """Analysis of change impact across system components"""
    changed_files: List[str]
    directly_affected_services: List[str]
    indirectly_affected_services: List[str]
    affected_dependencies: List[str]
    risk_score: float  # 0.0 - 1.0
    blast_radius: str  # "LOCAL", "SERVICE", "CROSS_SERVICE", "SYSTEM_WIDE"
    impact_paths: List[List[str]]  # Paths of impact propagation
    recommendations: List[str]
    
@dataclass
class ChangeRisk:
    """Risk assessment for a specific change"""
    component: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_factors: List[str]
    mitigation_strategies: List[str]
    monitoring_recommendations: List[str]

@dataclass
class ServiceDependency:
    """Represents a dependency between services"""
    source_service: str
    target_service: str
    dependency_type: str  # "api", "database", "queue", "file", "config"
    strength: float  # How critical is this dependency (0.0 - 1.0)
    failure_impact: str  # What happens if this dependency fails

class BlastRadiusAnalyzer:
    """
    System-level impact analyzer that maps change propagation through
    services and dependencies to understand architectural risk and
    provide system-thinking recommendations.
    """
    
    def __init__(self):
        """Initialize the blast radius analyzer"""
        self.service_map: Dict[str, Set[str]] = {}  # service -> files
        self.dependency_graph: Dict[str, List[ServiceDependency]] = {}  # service -> dependencies
        self.impact_cache: Dict[str, ImpactAnalysis] = {}
        logger.info("BlastRadiusAnalyzer initialized for system-level impact analysis")
    
    def analyze_change_impact(self, 
                            changed_files: List[str],
                            incidents: List[Incident],
                            service_topology: Optional[Dict[str, Any]] = None) -> ImpactAnalysis:
        """
        Analyze the blast radius and system impact of file changes
        
        Args:
            changed_files: Files being changed
            incidents: Historical incident data for impact modeling
            service_topology: Optional service dependency information
            
        Returns:
            Comprehensive impact analysis
        """
        logger.info(f"Analyzing blast radius for {len(changed_files)} changed files")
        
        # Build service mappings if not cached
        if not self.service_map:
            self._build_service_mappings(incidents)
        
        # Build dependency graph if topology provided
        if service_topology:
            self._build_dependency_graph(service_topology)
        
        # Identify directly affected services
        directly_affected = self._identify_directly_affected_services(changed_files)
        
        # Trace impact through dependency graph
        indirectly_affected, impact_paths = self._trace_dependency_impact(directly_affected)
        
        # Identify affected external dependencies
        affected_dependencies = self._identify_affected_dependencies(changed_files, incidents)
        
        # Calculate overall risk score
        risk_score = self._calculate_impact_risk(directly_affected, indirectly_affected, 
                                                affected_dependencies, incidents)
        
        # Determine blast radius category
        blast_radius = self._categorize_blast_radius(directly_affected, indirectly_affected, 
                                                   changed_files)
        
        # Generate recommendations
        recommendations = self._generate_impact_recommendations(blast_radius, directly_affected, 
                                                              indirectly_affected, risk_score)
        
        return ImpactAnalysis(
            changed_files=changed_files,
            directly_affected_services=directly_affected,
            indirectly_affected_services=indirectly_affected,
            affected_dependencies=affected_dependencies,
            risk_score=risk_score,
            blast_radius=blast_radius,
            impact_paths=impact_paths,
            recommendations=recommendations
        )
    
    def _build_service_mappings(self, incidents: List[Incident]) -> None:
        """Build mappings between files and services from incident data"""
        logger.info("Building service mappings from incident data")
        
        for incident in incidents:
            services = self._infer_services_from_files(incident.files)
            for service in services:
                if service not in self.service_map:
                    self.service_map[service] = set()
                self.service_map[service].update(incident.files)
        
        logger.info(f"Built mappings for {len(self.service_map)} services")
    
    def _build_dependency_graph(self, service_topology: Dict[str, Any]) -> None:
        """Build service dependency graph from topology data"""
        # This would integrate with service mesh, API gateway, or other topology sources
        # For now, implement basic inference
        
        for service, data in service_topology.items():
            dependencies = []
            
            # Extract dependencies from various sources
            if 'dependencies' in data:
                for dep_name, dep_info in data['dependencies'].items():
                    dependency = ServiceDependency(
                        source_service=service,
                        target_service=dep_name,
                        dependency_type=dep_info.get('type', 'api'),
                        strength=dep_info.get('strength', 0.5),
                        failure_impact=dep_info.get('failure_impact', 'service_degradation')
                    )
                    dependencies.append(dependency)
            
            self.dependency_graph[service] = dependencies
    
    def _identify_directly_affected_services(self, changed_files: List[str]) -> List[str]:
        """Identify services directly affected by file changes"""
        affected_services = set()
        
        # Method 1: Use service mappings from incidents
        for service, service_files in self.service_map.items():
            if any(file_path in service_files for file_path in changed_files):
                affected_services.add(service)
        
        # Method 2: Infer from file paths
        inferred_services = self._infer_services_from_files(changed_files)
        affected_services.update(inferred_services)
        
        return list(affected_services)
    
    def _trace_dependency_impact(self, directly_affected: List[str]) -> Tuple[List[str], List[List[str]]]:
        """Trace impact through service dependency graph"""
        indirectly_affected = set()
        impact_paths = []
        
        # BFS traversal to find downstream impact
        for source_service in directly_affected:
            visited = set()
            queue = deque([(source_service, [source_service])])
            
            while queue:
                current_service, path = queue.popleft()
                
                if current_service in visited:
                    continue
                visited.add(current_service)
                
                # Find services that depend on current service
                for service, dependencies in self.dependency_graph.items():
                    for dep in dependencies:
                        if dep.target_service == current_service and service not in visited:
                            new_path = path + [service]
                            impact_paths.append(new_path)
                            
                            # Only continue traversal for strong dependencies
                            if dep.strength > 0.5 and len(new_path) < 5:  # Limit depth
                                queue.append((service, new_path))
                                indirectly_affected.add(service)
        
        return list(indirectly_affected), impact_paths
    
    def _identify_affected_dependencies(self, changed_files: List[str], 
                                      incidents: List[Incident]) -> List[str]:
        """Identify external dependencies affected by changes"""
        dependencies = set()
        
        # Look for dependency-related files
        dependency_files = [
            "package.json", "requirements.txt", "pom.xml", "Cargo.toml",
            "go.mod", "composer.json", "Pipfile", "yarn.lock"
        ]
        
        for file_path in changed_files:
            if any(dep_file in file_path for dep_file in dependency_files):
                dependencies.add(f"dependency_file:{file_path}")
        
        # Look for database/external service references
        for incident in incidents:
            if incident.incident_type == IncidentType.DEPENDENCY_ISSUE:
                if any(file_path in incident.files for file_path in changed_files):
                    if incident.tags:
                        for tag in incident.tags:
                            if tag.startswith("dependency:"):
                                dependencies.add(tag.replace("dependency:", ""))
        
        return list(dependencies)
    
    def _calculate_impact_risk(self, directly_affected: List[str], 
                             indirectly_affected: List[str],
                             affected_dependencies: List[str],
                             incidents: List[Incident]) -> float:
        """Calculate overall risk score for the impact"""
        risk_score = 0.0
        
        # Direct impact risk
        risk_score += len(directly_affected) * 0.3
        
        # Indirect impact risk (cascading)
        risk_score += len(indirectly_affected) * 0.2
        
        # Dependency risk
        risk_score += len(affected_dependencies) * 0.1
        
        # Historical risk (services with many incidents)
        service_incident_counts = defaultdict(int)
        for incident in incidents:
            services = self._infer_services_from_files(incident.files)
            for service in services:
                service_incident_counts[service] += 1
        
        for service in directly_affected:
            incident_count = service_incident_counts.get(service, 0)
            risk_score += min(0.2, incident_count * 0.02)
        
        # Critical service modifier
        critical_services = self._identify_critical_services(directly_affected + indirectly_affected)
        risk_score += len(critical_services) * 0.1
        
        return min(1.0, risk_score)
    
    def _categorize_blast_radius(self, directly_affected: List[str], 
                               indirectly_affected: List[str],
                               changed_files: List[str]) -> str:
        """Categorize the scope of impact"""
        total_services = len(directly_affected) + len(indirectly_affected)
        
        if total_services == 0:
            return "LOCAL"  # No service impact detected
        elif total_services == 1 and not indirectly_affected:
            return "SERVICE"  # Single service impact
        elif total_services <= 3:
            return "CROSS_SERVICE"  # Limited cross-service impact
        else:
            return "SYSTEM_WIDE"  # Wide-ranging impact
    
    def _generate_impact_recommendations(self, blast_radius: str,
                                       directly_affected: List[str],
                                       indirectly_affected: List[str], 
                                       risk_score: float) -> List[str]:
        """Generate recommendations based on impact analysis"""
        recommendations = []
        
        if blast_radius == "SYSTEM_WIDE":
            recommendations.append("🚨 SYSTEM-WIDE IMPACT: Coordinate with all affected teams")
            recommendations.append("📋 Create deployment plan with rollback strategy")
            recommendations.append("⏰ Schedule deployment during low-traffic period")
            
        elif blast_radius == "CROSS_SERVICE":
            recommendations.append("🔗 CROSS-SERVICE IMPACT: Notify affected service owners")
            recommendations.append("🧪 Run integration tests across affected services")
            recommendations.append("📊 Monitor service boundaries during deployment")
            
        elif blast_radius == "SERVICE":
            recommendations.append("🎯 SERVICE-LEVEL IMPACT: Focus testing on affected service")
            recommendations.append("📈 Monitor service metrics closely")
        
        # Risk-based recommendations
        if risk_score > 0.7:
            recommendations.append("⚠️ HIGH RISK: Consider feature flags or canary deployment")
            recommendations.append("🔄 Prepare immediate rollback procedures")
        
        # Service-specific recommendations
        critical_services = self._identify_critical_services(directly_affected)
        if critical_services:
            recommendations.append(f"🏗️ Critical services affected: {', '.join(critical_services)}")
            recommendations.append("👥 Require senior engineer approval")
        
        if indirectly_affected:
            recommendations.append(f"📡 Monitor downstream services: {', '.join(indirectly_affected[:3])}")
        
        return recommendations[:6]  # Limit to top 6
    
    def _infer_services_from_files(self, files: List[str]) -> Set[str]:
        """Infer service names from file paths"""
        services = set()
        
        for file_path in files:
            parts = file_path.split('/')
            
            # Common service directory patterns
            if 'services' in parts:
                idx = parts.index('services')
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif 'microservices' in parts:
                idx = parts.index('microservices')
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif 'apps' in parts:
                idx = parts.index('apps')
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif 'src' in parts and len(parts) > parts.index('src') + 1:
                idx = parts.index('src')
                services.add(parts[idx + 1])
            elif parts and not parts[0].startswith('.'):
                # Use top-level directory as service name
                services.add(parts[0])
        
        return services
    
    def _identify_critical_services(self, services: List[str]) -> List[str]:
        """Identify critical services from the list"""
        critical_patterns = [
            "auth", "authentication", "user", "payment", "billing",
            "api-gateway", "gateway", "core", "main", "database",
            "notification", "email", "sms"
        ]
        
        critical_services = []
        for service in services:
            if any(pattern in service.lower() for pattern in critical_patterns):
                critical_services.append(service)
        
        return critical_services
    
    def get_service_risk_profile(self, service_name: str, incidents: List[Incident]) -> ChangeRisk:
        """Get detailed risk profile for a specific service"""
        # Find incidents related to this service
        service_incidents = [
            inc for inc in incidents 
            if service_name in self._infer_services_from_files(inc.files)
        ]
        
        # Calculate risk level
        incident_count = len(service_incidents)
        if incident_count >= 10:
            risk_level = "CRITICAL"
        elif incident_count >= 5:
            risk_level = "HIGH"
        elif incident_count >= 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Generate risk factors
        risk_factors = []
        if incident_count > 0:
            risk_factors.append(f"{incident_count} historical incidents")
            
            recent_incidents = [
                inc for inc in service_incidents 
                if (incidents[0].timestamp - inc.timestamp).days <= 30  # Assuming incidents are sorted
            ]
            if recent_incidents:
                risk_factors.append(f"{len(recent_incidents)} incidents in last 30 days")
        
        if service_name in self._identify_critical_services([service_name]):
            risk_factors.append("Critical system service")
        
        # Generate mitigation strategies
        mitigation_strategies = [
            "Implement comprehensive monitoring",
            "Add circuit breakers for external dependencies",
            "Create detailed runbook for common issues",
            "Implement graceful degradation"
        ]
        
        monitoring_recommendations = [
            "Monitor service health metrics",
            "Track error rates and latency",
            "Set up alerts for anomalies",
            "Monitor downstream service impact"
        ]
        
        return ChangeRisk(
            component=service_name,
            risk_level=risk_level,
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies[:3],
            monitoring_recommendations=monitoring_recommendations[:3]
        )