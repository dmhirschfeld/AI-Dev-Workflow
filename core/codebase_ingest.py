"""
Codebase Ingestion Module

Handles importing, indexing, and analyzing existing codebases.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
import yaml


@dataclass
class FileInfo:
    """Information about a single file"""
    path: str
    relative_path: str
    extension: str
    size: int
    lines: int
    language: str
    hash: str


@dataclass
class TechStack:
    """Detected technology stack"""
    frontend: list = field(default_factory=list)
    backend: list = field(default_factory=list)
    database: list = field(default_factory=list)
    infrastructure: list = field(default_factory=list)
    testing: list = field(default_factory=list)
    other: list = field(default_factory=list)


@dataclass
class IngestResult:
    """Result of codebase ingestion"""
    project_name: str
    source_path: str
    ingested_at: str
    file_count: int
    source_file_count: int
    total_lines: int
    tech_stack: TechStack
    files: list
    entry_points: list
    config_files: list
    has_tests: bool
    has_ci: bool
    has_docker: bool


# File extension to language mapping
LANGUAGE_MAP = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript React',
    '.jsx': 'JavaScript React',
    '.java': 'Java',
    '.go': 'Go',
    '.rs': 'Rust',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.cs': 'C#',
    '.cpp': 'C++',
    '.c': 'C',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.sql': 'SQL',
    '.html': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.vue': 'Vue',
    '.svelte': 'Svelte',
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', 'venv', '.venv', 'env', '.env',
    '__pycache__', '.git', '.svn', '.hg',
    'dist', 'build', 'target', 'out',
    '.idea', '.vscode', '.vs',
    'coverage', '.nyc_output',
    'vendor', 'packages',
}

# Config files that indicate tech stack
CONFIG_FILES = {
    'package.json': 'node',
    'requirements.txt': 'python',
    'Pipfile': 'python',
    'pyproject.toml': 'python',
    'Gemfile': 'ruby',
    'go.mod': 'go',
    'Cargo.toml': 'rust',
    'pom.xml': 'java',
    'build.gradle': 'java',
    'composer.json': 'php',
    'Dockerfile': 'docker',
    'docker-compose.yml': 'docker',
    'docker-compose.yaml': 'docker',
    '.github/workflows': 'github-actions',
    'Jenkinsfile': 'jenkins',
    '.gitlab-ci.yml': 'gitlab-ci',
    'tsconfig.json': 'typescript',
    'vite.config.js': 'vite',
    'vite.config.ts': 'vite',
    'next.config.js': 'nextjs',
    'nuxt.config.js': 'nuxt',
    'angular.json': 'angular',
    '.eslintrc': 'eslint',
    '.prettierrc': 'prettier',
    'jest.config.js': 'jest',
    'playwright.config.ts': 'playwright',
    'cypress.config.js': 'cypress',
}


class CodebaseIngestor:
    """Handles codebase ingestion and analysis"""
    
    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(exist_ok=True)
    
    def ingest(self, source_path: str, project_name: Optional[str] = None) -> IngestResult:
        """
        Ingest a codebase from the given path.
        
        Args:
            source_path: Path to the codebase to ingest
            project_name: Optional name for the project (derived from path if not provided)
            
        Returns:
            IngestResult with analysis of the codebase
        """
        source = Path(source_path)
        if not source.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        # Derive project name
        if not project_name:
            project_name = source.name.lower().replace(" ", "-")
            project_name = "".join(c for c in project_name if c.isalnum() or c == "-")
        
        # Scan files
        files = self._scan_files(source)
        source_files = [f for f in files if f.language != 'Unknown']
        
        # Detect tech stack
        tech_stack = self._detect_tech_stack(source, files)
        
        # Find entry points
        entry_points = self._find_entry_points(source, files)
        
        # Find config files
        config_files = self._find_config_files(source)
        
        # Check for common features
        has_tests = self._has_tests(source, files)
        has_ci = self._has_ci(source)
        has_docker = self._has_docker(source)
        
        # Calculate totals
        total_lines = sum(f.lines for f in files)
        
        result = IngestResult(
            project_name=project_name,
            source_path=str(source.absolute()),
            ingested_at=datetime.now().isoformat(),
            file_count=len(files),
            source_file_count=len(source_files),
            total_lines=total_lines,
            tech_stack=tech_stack,
            files=[asdict(f) for f in source_files],
            entry_points=entry_points,
            config_files=config_files,
            has_tests=has_tests,
            has_ci=has_ci,
            has_docker=has_docker,
        )
        
        # Save to project directory
        self._save_project(project_name, result, source)
        
        return result
    
    def _scan_files(self, root: Path) -> list[FileInfo]:
        """Scan all files in the directory"""
        files = []
        
        for path in root.rglob("*"):
            # Skip directories in skip list
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            
            if path.is_file():
                try:
                    relative = path.relative_to(root)
                    extension = path.suffix.lower()
                    language = LANGUAGE_MAP.get(extension, 'Unknown')
                    
                    # Count lines
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = sum(1 for _ in f)
                    except:
                        lines = 0
                    
                    # Calculate hash
                    try:
                        with open(path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()[:12]
                    except:
                        file_hash = ""
                    
                    files.append(FileInfo(
                        path=str(path),
                        relative_path=str(relative),
                        extension=extension,
                        size=path.stat().st_size,
                        lines=lines,
                        language=language,
                        hash=file_hash,
                    ))
                except Exception as e:
                    print(f"Warning: Could not process {path}: {e}")
        
        return files
    
    def _detect_tech_stack(self, root: Path, files: list[FileInfo]) -> TechStack:
        """Detect the technology stack from files"""
        stack = TechStack()
        
        # Check for package.json
        package_json = root / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    
                    # Frontend frameworks
                    if "react" in deps:
                        stack.frontend.append(f"React {deps.get('react', '').replace('^', '').replace('~', '')}")
                    if "vue" in deps:
                        stack.frontend.append(f"Vue {deps.get('vue', '')}")
                    if "next" in deps:
                        stack.frontend.append("Next.js")
                    if "vite" in deps:
                        stack.frontend.append("Vite")
                    
                    # Backend
                    if "express" in deps:
                        stack.backend.append("Express")
                    if "fastify" in deps:
                        stack.backend.append("Fastify")
                    if "nest" in deps or "@nestjs/core" in deps:
                        stack.backend.append("NestJS")
                    
                    # Testing
                    if "jest" in deps:
                        stack.testing.append("Jest")
                    if "playwright" in deps or "@playwright/test" in deps:
                        stack.testing.append("Playwright")
                    if "cypress" in deps:
                        stack.testing.append("Cypress")
                    if "vitest" in deps:
                        stack.testing.append("Vitest")
            except:
                pass
        
        # Check for requirements.txt / Python
        requirements = root / "requirements.txt"
        if requirements.exists():
            try:
                with open(requirements) as f:
                    reqs = f.read().lower()
                    if "django" in reqs:
                        stack.backend.append("Django")
                    if "flask" in reqs:
                        stack.backend.append("Flask")
                    if "fastapi" in reqs:
                        stack.backend.append("FastAPI")
                    if "pytest" in reqs:
                        stack.testing.append("pytest")
                    if "sqlalchemy" in reqs:
                        stack.database.append("SQLAlchemy")
            except:
                pass
        
        # Check for Docker
        if (root / "Dockerfile").exists():
            stack.infrastructure.append("Docker")
        if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
            stack.infrastructure.append("Docker Compose")
        
        # Check for CI/CD
        if (root / ".github" / "workflows").exists():
            stack.infrastructure.append("GitHub Actions")
        
        # Detect from file extensions
        extensions = set(f.extension for f in files)
        if '.ts' in extensions or '.tsx' in extensions:
            if "TypeScript" not in stack.frontend and "TypeScript" not in stack.backend:
                stack.other.append("TypeScript")
        
        return stack
    
    def _find_entry_points(self, root: Path, files: list[FileInfo]) -> list[dict]:
        """Find likely entry points"""
        entry_points = []
        
        entry_patterns = [
            "index.js", "index.ts", "main.js", "main.ts",
            "app.js", "app.ts", "server.js", "server.ts",
            "main.py", "app.py", "wsgi.py", "asgi.py",
            "main.go", "main.rs",
            "src/index.js", "src/index.ts", "src/main.js", "src/main.ts",
            "src/app.js", "src/app.ts",
        ]
        
        for pattern in entry_patterns:
            entry_path = root / pattern
            if entry_path.exists():
                entry_points.append({
                    "file": pattern,
                    "type": "main" if "main" in pattern else "app" if "app" in pattern else "index"
                })
        
        return entry_points
    
    def _find_config_files(self, root: Path) -> list[str]:
        """Find configuration files"""
        found = []
        
        for config_file in CONFIG_FILES.keys():
            if (root / config_file).exists():
                found.append(config_file)
        
        return found
    
    def _has_tests(self, root: Path, files: list[FileInfo]) -> bool:
        """Check if project has tests"""
        test_indicators = [
            "test", "tests", "spec", "specs", "__tests__"
        ]
        
        for f in files:
            path_lower = f.relative_path.lower()
            if any(ind in path_lower for ind in test_indicators):
                return True
            if ".test." in path_lower or ".spec." in path_lower or "_test." in path_lower:
                return True
        
        return False
    
    def _has_ci(self, root: Path) -> bool:
        """Check if project has CI/CD configuration"""
        ci_paths = [
            ".github/workflows",
            ".gitlab-ci.yml",
            "Jenkinsfile",
            ".circleci",
            ".travis.yml",
            "azure-pipelines.yml",
            "bitbucket-pipelines.yml",
        ]
        
        for ci_path in ci_paths:
            if (root / ci_path).exists():
                return True
        
        return False
    
    def _has_docker(self, root: Path) -> bool:
        """Check if project has Docker configuration"""
        return (root / "Dockerfile").exists()
    
    def _save_project(self, project_name: str, result: IngestResult, source: Path):
        """Save project configuration"""
        project_dir = self.projects_dir / project_name
        project_dir.mkdir(exist_ok=True)
        
        # Create project.yaml
        project_config = {
            "project": {
                "id": project_name,
                "name": project_name.replace("-", " ").title(),
                "type": "existing",
                "source_path": str(source.absolute()),
                "ingested_at": result.ingested_at,
            },
            "stats": {
                "file_count": result.file_count,
                "source_file_count": result.source_file_count,
                "total_lines": result.total_lines,
            },
            "tech_stack": asdict(result.tech_stack),
            "features": {
                "has_tests": result.has_tests,
                "has_ci": result.has_ci,
                "has_docker": result.has_docker,
            },
            "entry_points": result.entry_points,
            "config_files": result.config_files,
        }
        
        with open(project_dir / "project.yaml", "w", encoding="utf-8") as f:
            yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)
        
        # Save file index
        with open(project_dir / "file_index.json", "w", encoding="utf-8") as f:
            json.dump(result.files, f, indent=2)


def ingest_codebase(source_path: str, project_name: Optional[str] = None) -> IngestResult:
    """
    Convenience function to ingest a codebase.
    
    Args:
        source_path: Path to the codebase
        project_name: Optional project name
        
    Returns:
        IngestResult
    """
    ingestor = CodebaseIngestor()
    return ingestor.ingest(source_path, project_name)
