"""
GitHub Integration Module

Handles repository discovery, creation, and synchronization.

Flow:
1. Search GitHub for existing repos with same/similar name
2. If found - offer to connect
3. If not found - create new or ask which to connect
4. Clone/link and sync changes
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GitHubRepo:
    """Represents a GitHub repository"""
    name: str
    full_name: str  # owner/repo
    url: str
    clone_url: str
    ssh_url: str
    description: Optional[str]
    private: bool
    default_branch: str
    updated_at: str
    language: Optional[str]
    
    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0]


class GitHubIntegration:
    """
    GitHub integration for AI-Dev-Workflow.
    
    Uses GitHub CLI (gh) for operations - more reliable than API tokens
    and handles auth automatically.
    """
    
    def __init__(self, default_org: Optional[str] = None):
        self.default_org = default_org or os.environ.get("GITHUB_ORG")
        self.default_visibility = os.environ.get("GITHUB_DEFAULT_VISIBILITY", "private")
        self._gh_available = None
        self._authenticated = None
    
    # ════════════════════════════════════════════════════════════
    # AVAILABILITY CHECKS
    # ════════════════════════════════════════════════════════════
    
    def is_gh_available(self) -> bool:
        """Check if GitHub CLI is installed"""
        if self._gh_available is None:
            try:
                result = subprocess.run(
                    ["gh", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self._gh_available = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._gh_available = False
        return self._gh_available
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with GitHub"""
        if self._authenticated is None:
            try:
                result = subprocess.run(
                    ["gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._authenticated = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._authenticated = False
        return self._authenticated
    
    def get_authenticated_user(self) -> Optional[str]:
        """Get the authenticated GitHub username"""
        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None
    
    # ════════════════════════════════════════════════════════════
    # REPOSITORY SEARCH
    # ════════════════════════════════════════════════════════════
    
    def search_repos(
        self,
        query: str,
        owner: Optional[str] = None,
        limit: int = 10
    ) -> List[GitHubRepo]:
        """
        Search for repositories matching query.
        
        Args:
            query: Search term (project name)
            owner: Limit to specific owner/org (optional)
            limit: Max results
            
        Returns:
            List of matching repositories
        """
        if not self.is_gh_available() or not self.is_authenticated():
            return []
        
        # Build search query
        search_query = query
        if owner:
            search_query = f"{query} user:{owner}"
        
        try:
            # Search using gh cli
            result = subprocess.run(
                [
                    "gh", "search", "repos", search_query,
                    "--limit", str(limit),
                    "--json", "name,fullName,url,description,isPrivate,defaultBranch,updatedAt,primaryLanguage"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            import json
            repos_data = json.loads(result.stdout)
            
            repos = []
            for r in repos_data:
                repos.append(GitHubRepo(
                    name=r.get("name", ""),
                    full_name=r.get("fullName", ""),
                    url=r.get("url", ""),
                    clone_url=f"https://github.com/{r.get('fullName', '')}.git",
                    ssh_url=f"git@github.com:{r.get('fullName', '')}.git",
                    description=r.get("description"),
                    private=r.get("isPrivate", False),
                    default_branch=r.get("defaultBranch", "main"),
                    updated_at=r.get("updatedAt", ""),
                    language=r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
                ))
            
            return repos
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    def search_user_repos(
        self,
        query: str,
        limit: int = 10
    ) -> List[GitHubRepo]:
        """Search only the authenticated user's repos"""
        user = self.get_authenticated_user()
        if user:
            return self.search_repos(query, owner=user, limit=limit)
        return []
    
    def search_org_repos(
        self,
        query: str,
        org: Optional[str] = None,
        limit: int = 10
    ) -> List[GitHubRepo]:
        """Search repos in an organization"""
        org = org or self.default_org
        if org:
            return self.search_repos(query, owner=org, limit=limit)
        return []
    
    def find_similar_repos(
        self,
        name: str,
        limit: int = 10
    ) -> List[Tuple[GitHubRepo, float]]:
        """
        Find repos with similar names, scored by similarity.
        
        Returns list of (repo, similarity_score) tuples.
        """
        # Search with the name and variations
        variations = self._generate_name_variations(name)
        
        all_repos = []
        seen = set()
        
        for variation in variations:
            repos = self.search_user_repos(variation, limit=5)
            
            # Also search org if configured
            if self.default_org:
                repos.extend(self.search_org_repos(variation, limit=5))
            
            for repo in repos:
                if repo.full_name not in seen:
                    seen.add(repo.full_name)
                    similarity = self._calculate_similarity(name, repo.name)
                    all_repos.append((repo, similarity))
        
        # Sort by similarity
        all_repos.sort(key=lambda x: x[1], reverse=True)
        
        return all_repos[:limit]
    
    def _generate_name_variations(self, name: str) -> List[str]:
        """Generate search variations for a name"""
        variations = [name]
        
        # Remove common suffixes/prefixes
        clean = name.lower()
        clean = re.sub(r'[-_]?(app|api|web|service|backend|frontend)$', '', clean)
        clean = re.sub(r'^(the|my)[-_]?', '', clean)
        
        if clean != name.lower():
            variations.append(clean)
        
        # kebab-case to words
        words = re.split(r'[-_]', name.lower())
        if len(words) > 1:
            variations.append(" ".join(words))
        
        # CamelCase to words
        camel_words = re.findall(r'[A-Z][a-z]+|[a-z]+', name)
        if len(camel_words) > 1:
            variations.append(" ".join(w.lower() for w in camel_words))
        
        return list(set(variations))
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity (0-1)"""
        n1 = name1.lower().replace("-", "").replace("_", "")
        n2 = name2.lower().replace("-", "").replace("_", "")
        
        # Exact match
        if n1 == n2:
            return 1.0
        
        # Contains
        if n1 in n2 or n2 in n1:
            return 0.8
        
        # Word overlap
        words1 = set(re.split(r'[-_\s]', name1.lower()))
        words2 = set(re.split(r'[-_\s]', name2.lower()))
        
        if words1 and words2:
            overlap = len(words1 & words2)
            total = len(words1 | words2)
            return overlap / total * 0.7
        
        return 0.0
    
    # ════════════════════════════════════════════════════════════
    # REPOSITORY OPERATIONS
    # ════════════════════════════════════════════════════════════
    
    def repo_exists(self, full_name: str) -> bool:
        """Check if a specific repo exists"""
        try:
            result = subprocess.run(
                ["gh", "repo", "view", full_name, "--json", "name"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def create_repo(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = True,
        org: Optional[str] = None,
    ) -> Optional[GitHubRepo]:
        """
        Create a new GitHub repository.
        
        Args:
            name: Repository name
            description: Optional description
            private: Private or public
            org: Organization (uses default or personal if None)
            
        Returns:
            Created repo info or None on failure
        """
        if not self.is_gh_available() or not self.is_authenticated():
            return None
        
        cmd = ["gh", "repo", "create"]
        
        # Add org prefix if specified
        if org or self.default_org:
            target_org = org or self.default_org
            cmd.append(f"{target_org}/{name}")
        else:
            cmd.append(name)
        
        # Add flags
        if private:
            cmd.append("--private")
        else:
            cmd.append("--public")
        
        if description:
            cmd.extend(["--description", description])
        
        cmd.append("--confirm")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Get the created repo info
                repo_name = f"{org or self.default_org or self.get_authenticated_user()}/{name}"
                return self.get_repo(repo_name)
            else:
                print(f"Failed to create repo: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error creating repo: {e}")
            return None
    
    def get_repo(self, full_name: str) -> Optional[GitHubRepo]:
        """Get repository details"""
        try:
            result = subprocess.run(
                [
                    "gh", "repo", "view", full_name,
                    "--json", "name,url,description,isPrivate,defaultBranch,updatedAt,primaryLanguage"
                ],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                return None
            
            import json
            r = json.loads(result.stdout)
            
            return GitHubRepo(
                name=r.get("name", ""),
                full_name=full_name,
                url=r.get("url", ""),
                clone_url=f"https://github.com/{full_name}.git",
                ssh_url=f"git@github.com:{full_name}.git",
                description=r.get("description"),
                private=r.get("isPrivate", False),
                default_branch=r.get("defaultBranch", "main"),
                updated_at=r.get("updatedAt", ""),
                language=r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
            )
            
        except Exception as e:
            print(f"Error getting repo: {e}")
            return None
    
    def clone_repo(
        self,
        full_name: str,
        target_dir: str,
        branch: Optional[str] = None
    ) -> bool:
        """
        Clone a repository to target directory.
        
        Args:
            full_name: owner/repo
            target_dir: Where to clone
            branch: Specific branch (optional)
            
        Returns:
            True on success
        """
        cmd = ["gh", "repo", "clone", full_name, target_dir]
        
        if branch:
            cmd.extend(["--", "-b", branch])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Clone failed: {e}")
            return False
    
    # ════════════════════════════════════════════════════════════
    # LOCAL GIT OPERATIONS
    # ════════════════════════════════════════════════════════════
    
    def init_local_repo(self, directory: str) -> bool:
        """Initialize a git repo in directory"""
        try:
            result = subprocess.run(
                ["git", "init"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def add_remote(
        self,
        directory: str,
        repo: GitHubRepo,
        remote_name: str = "origin"
    ) -> bool:
        """Add GitHub remote to local repo"""
        try:
            result = subprocess.run(
                ["git", "remote", "add", remote_name, repo.clone_url],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def commit_all(
        self,
        directory: str,
        message: str,
        author: Optional[str] = None
    ) -> bool:
        """Stage all changes and commit"""
        try:
            # Add all
            subprocess.run(
                ["git", "add", "-A"],
                cwd=directory,
                capture_output=True,
                timeout=30
            )
            
            # Commit
            cmd = ["git", "commit", "-m", message]
            if author:
                cmd.extend(["--author", author])
            
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except:
            return False
    
    def push(
        self,
        directory: str,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = True
    ) -> bool:
        """Push changes to remote"""
        try:
            cmd = ["git", "push"]
            if set_upstream:
                cmd.append("-u")
            cmd.append(remote)
            if branch:
                cmd.append(branch)
            
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except:
            return False
    
    def create_branch(
        self,
        directory: str,
        branch_name: str,
        checkout: bool = True
    ) -> bool:
        """Create and optionally checkout a branch"""
        try:
            if checkout:
                cmd = ["git", "checkout", "-b", branch_name]
            else:
                cmd = ["git", "branch", branch_name]
            
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def get_current_branch(self, directory: str) -> Optional[str]:
        """Get current branch name"""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None
    
    def is_git_repo(self, directory: str) -> bool:
        """Check if directory is a git repository"""
        git_dir = Path(directory) / ".git"
        return git_dir.exists()
    
    def get_remote_url(self, directory: str, remote: str = "origin") -> Optional[str]:
        """Get remote URL for a local repo"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None


# ════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════

_github = None

def get_github() -> GitHubIntegration:
    """Get or create GitHub integration instance"""
    global _github
    if _github is None:
        _github = GitHubIntegration()
    return _github


def setup_check() -> Dict[str, bool]:
    """Check GitHub setup status"""
    gh = get_github()
    return {
        "gh_cli_installed": gh.is_gh_available(),
        "authenticated": gh.is_authenticated(),
        "user": gh.get_authenticated_user(),
    }


def find_or_create_repo(
    name: str,
    search_first: bool = True,
    auto_create: bool = False,
    private: bool = True,
) -> Tuple[Optional[GitHubRepo], str]:
    """
    Find existing repo or create new one.
    
    Returns:
        (repo, action) where action is 'found', 'created', or 'none'
    """
    gh = get_github()
    
    if search_first:
        similar = gh.find_similar_repos(name, limit=5)
        
        # Check for exact or very close match
        for repo, similarity in similar:
            if similarity >= 0.9:
                return (repo, "found")
    
    if auto_create:
        repo = gh.create_repo(name, private=private)
        if repo:
            return (repo, "created")
    
    return (None, "none")
