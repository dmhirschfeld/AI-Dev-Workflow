"""
Project Knowledge Base with RAG (Retrieval-Augmented Generation)
Uses ChromaDB for vector storage and semantic search
"""

import os
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime

import chromadb
from chromadb.config import Settings


@dataclass
class Document:
    """A document in the knowledge base"""
    id: str
    content: str
    metadata: dict
    doc_type: str
    file_path: str | None = None
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SearchResult:
    """Result from a knowledge base search"""
    document_id: str
    content: str
    metadata: dict
    relevance_score: float
    doc_type: str


class KnowledgeBase:
    """
    RAG-enabled knowledge base for project context.
    Stores and retrieves project documents, code, requirements, etc.
    """
    
    # Document type categories
    DOC_TYPES = Literal[
        "code",
        "requirements", 
        "architecture",
        "api_spec",
        "schema",
        "test",
        "documentation",
        "decision",
        "standard"
    ]
    
    def __init__(
        self,
        project_id: str,
        persist_directory: str = "./data/knowledge_base"
    ):
        self.project_id = project_id
        self.persist_directory = Path(persist_directory) / project_id
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create collection for this project
        self.collection = self.client.get_or_create_collection(
            name=f"project_{project_id}",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
    
    def _generate_doc_id(self, content: str, doc_type: str) -> str:
        """Generate a unique document ID based on content hash"""
        hash_input = f"{doc_type}:{content}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def add_document(
        self,
        content: str,
        doc_type: str,
        metadata: dict | None = None,
        file_path: str | None = None,
        doc_id: str | None = None
    ) -> str:
        """Add a document to the knowledge base"""
        
        if doc_id is None:
            doc_id = self._generate_doc_id(content, doc_type)
        
        base_metadata = {
            "doc_type": doc_type,
            "project_id": self.project_id,
            "timestamp": datetime.now().isoformat(),
            "file_path": file_path or ""
        }
        
        if metadata:
            base_metadata.update(metadata)
        
        # Upsert to handle updates
        self.collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[base_metadata]
        )
        
        return doc_id
    
    def add_file(self, file_path: str, doc_type: str, metadata: dict | None = None) -> str:
        """Add a file to the knowledge base"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = path.read_text(encoding="utf-8")
        
        file_metadata = {
            "filename": path.name,
            "extension": path.suffix,
            **(metadata or {})
        }
        
        return self.add_document(
            content=content,
            doc_type=doc_type,
            metadata=file_metadata,
            file_path=str(path.absolute())
        )
    
    def add_directory(
        self,
        directory: str,
        doc_type: str,
        extensions: list[str] | None = None,
        exclude_dirs: list[str] | None = None
    ) -> list[str]:
        """Recursively add all files from a directory"""
        
        extensions = extensions or [".py", ".js", ".ts", ".md", ".yaml", ".json"]
        exclude_dirs = exclude_dirs or ["node_modules", ".git", "__pycache__", "venv", ".venv"]
        
        added_ids = []
        dir_path = Path(directory)
        
        for file_path in dir_path.rglob("*"):
            # Skip excluded directories
            if any(excl in file_path.parts for excl in exclude_dirs):
                continue
            
            # Check extension
            if file_path.is_file() and file_path.suffix in extensions:
                try:
                    doc_id = self.add_file(str(file_path), doc_type)
                    added_ids.append(doc_id)
                except Exception as e:
                    print(f"Failed to add {file_path}: {e}")
        
        return added_ids
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        doc_types: list[str] | None = None,
        metadata_filter: dict | None = None
    ) -> list[SearchResult]:
        """Search the knowledge base for relevant documents"""
        
        # Build where filter
        where_filter = None
        if doc_types:
            if len(doc_types) == 1:
                where_filter = {"doc_type": doc_types[0]}
            else:
                where_filter = {"doc_type": {"$in": doc_types}}
        
        if metadata_filter:
            if where_filter:
                where_filter = {"$and": [where_filter, metadata_filter]}
            else:
                where_filter = metadata_filter
        
        # Execute search
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        # Format results
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                search_results.append(SearchResult(
                    document_id=doc_id,
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i],
                    relevance_score=1 - results["distances"][0][i],  # Convert distance to similarity
                    doc_type=results["metadatas"][0][i].get("doc_type", "unknown")
                ))
        
        return search_results
    
    def get_document(self, doc_id: str) -> Document | None:
        """Retrieve a specific document by ID"""
        result = self.collection.get(ids=[doc_id])
        
        if result["ids"]:
            return Document(
                id=doc_id,
                content=result["documents"][0],
                metadata=result["metadatas"][0],
                doc_type=result["metadatas"][0].get("doc_type", "unknown"),
                file_path=result["metadatas"][0].get("file_path")
            )
        return None
    
    def delete_document(self, doc_id: str):
        """Delete a document from the knowledge base"""
        self.collection.delete(ids=[doc_id])
    
    def get_all_by_type(self, doc_type: str) -> list[Document]:
        """Get all documents of a specific type"""
        results = self.collection.get(
            where={"doc_type": doc_type}
        )
        
        documents = []
        for i, doc_id in enumerate(results["ids"]):
            documents.append(Document(
                id=doc_id,
                content=results["documents"][i],
                metadata=results["metadatas"][i],
                doc_type=doc_type,
                file_path=results["metadatas"][i].get("file_path")
            ))
        
        return documents
    
    def get_stats(self) -> dict:
        """Get statistics about the knowledge base"""
        count = self.collection.count()
        
        # Get counts by type
        type_counts = {}
        for doc_type in ["code", "requirements", "architecture", "api_spec", 
                         "schema", "test", "documentation", "decision", "standard"]:
            results = self.collection.get(where={"doc_type": doc_type})
            type_counts[doc_type] = len(results["ids"])
        
        return {
            "project_id": self.project_id,
            "total_documents": count,
            "by_type": type_counts
        }
    
    def clear(self):
        """Clear all documents from the knowledge base"""
        self.client.delete_collection(f"project_{self.project_id}")
        self.collection = self.client.create_collection(
            name=f"project_{self.project_id}",
            metadata={"hnsw:space": "cosine"}
        )


class ContextManager:
    """
    Manages context retrieval for agents based on their role and task.
    """
    
    # Define what document types are relevant for each agent role
    ROLE_CONTEXT_MAP = {
        "orchestrator": ["requirements", "architecture", "decision"],
        "ideation": ["requirements", "documentation"],
        "product_owner": ["requirements", "decision"],
        "business_analyst": ["requirements", "architecture", "documentation"],
        "ui_ux_designer": ["requirements", "architecture", "documentation"],
        "solutions_architect": ["requirements", "architecture", "code", "api_spec", "schema"],
        "data_architect": ["schema", "architecture", "requirements"],
        "security_specialist": ["code", "architecture", "api_spec", "standard"],
        "api_designer": ["api_spec", "architecture", "requirements"],
        "developer": ["code", "requirements", "architecture", "api_spec", "schema", "standard"],
        "code_reviewer": ["code", "standard", "architecture", "test"],
        "code_simplifier": ["code", "standard", "architecture"],
        "test_writer": ["code", "requirements", "test"],
        "technical_writer": ["code", "api_spec", "architecture", "documentation"],
        "devops": ["code", "architecture", "documentation"]
    }
    
    def __init__(self, knowledge_base: KnowledgeBase, project_config: dict | None = None):
        self.kb = knowledge_base
        self.project_config = project_config or {}
    
    def get_context_for_agent(
        self,
        agent_id: str,
        task_description: str,
        max_results: int = 10
    ) -> str:
        """Get relevant context for an agent based on role and task"""
        
        # Determine agent role (strip voter_ prefix if present)
        role = agent_id.replace("voter_", "")
        if role not in self.ROLE_CONTEXT_MAP:
            role = "developer"  # Default fallback
        
        relevant_types = self.ROLE_CONTEXT_MAP.get(role, [])
        
        # Search for relevant documents
        results = self.kb.search(
            query=task_description,
            n_results=max_results,
            doc_types=relevant_types
        )
        
        # Build context string
        context_parts = []
        
        # Add project config if available
        if self.project_config:
            context_parts.append(self._format_project_config())
        
        # Add search results
        for result in results:
            context_parts.append(self._format_search_result(result))
        
        return "\n\n---\n\n".join(context_parts)
    
    def _format_project_config(self) -> str:
        """Format project configuration as context"""
        config = self.project_config
        
        return f"""## Project Configuration
- **Name**: {config.get('name', 'Unknown')}
- **Tech Stack**: {config.get('tech_stack', {})}
- **Standards**: {config.get('standards', 'Default')}
"""
    
    def _format_search_result(self, result: SearchResult) -> str:
        """Format a search result for context"""
        file_info = ""
        if result.metadata.get("file_path"):
            file_info = f"\n**File**: {result.metadata['file_path']}"
        
        return f"""## {result.doc_type.upper()}{file_info}
**Relevance**: {result.relevance_score:.2f}

{result.content[:2000]}{'...' if len(result.content) > 2000 else ''}
"""
    
    def get_full_context(self, doc_types: list[str] | None = None) -> str:
        """Get full context of specific document types"""
        types_to_fetch = doc_types or ["requirements", "architecture", "standard"]
        
        context_parts = []
        for doc_type in types_to_fetch:
            docs = self.kb.get_all_by_type(doc_type)
            for doc in docs:
                context_parts.append(f"## {doc_type.upper()}: {doc.metadata.get('filename', doc.id)}\n\n{doc.content}")
        
        return "\n\n---\n\n".join(context_parts)


if __name__ == "__main__":
    # Example usage
    kb = KnowledgeBase("test_project")
    
    # Add some test documents
    kb.add_document(
        content="Users should be able to log in with email and password.",
        doc_type="requirements",
        metadata={"feature": "authentication"}
    )
    
    kb.add_document(
        content="The system uses a microservices architecture with API Gateway.",
        doc_type="architecture",
        metadata={"component": "overview"}
    )
    
    # Search
    results = kb.search("user authentication")
    print("Search Results:")
    for r in results:
        print(f"  - {r.doc_type}: {r.content[:50]}... (score: {r.relevance_score:.2f})")
    
    # Stats
    print("\nKnowledge Base Stats:")
    print(kb.get_stats())
