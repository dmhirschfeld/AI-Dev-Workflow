"""
Enhanced Code Indexing
Parses code into functions/classes with generated descriptions for better RAG retrieval.

Based on research showing that:
- Searching code descriptions is 12% more accurate than raw code
- Function-level chunking beats file-level chunking
- Noise dramatically reduces retrieval quality
"""

import ast
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Generator
import anthropic

from core.knowledge_base import KnowledgeBase


@dataclass
class CodeNode:
    """A parsed code element (function, class, method)"""
    name: str
    node_type: str  # function, class, method, module
    code: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    parent: str | None = None  # For methods, the class name
    signature: str | None = None
    

class PythonParser:
    """Parse Python files into code nodes"""
    
    def parse_file(self, file_path: str) -> list[CodeNode]:
        """Parse a Python file into code nodes"""
        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return []
        
        content = path.read_text(encoding="utf-8")
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        
        nodes = []
        lines = content.split("\n")
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Check if it's a method (inside a class)
                parent = self._find_parent_class(tree, node)
                
                code = self._extract_code(lines, node.lineno - 1, node.end_lineno)
                signature = self._extract_signature(node)
                
                nodes.append(CodeNode(
                    name=node.name,
                    node_type="method" if parent else "function",
                    code=code,
                    file_path=str(path),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=ast.get_docstring(node),
                    parent=parent,
                    signature=signature
                ))
            
            elif isinstance(node, ast.ClassDef):
                code = self._extract_code(lines, node.lineno - 1, node.end_lineno)
                
                nodes.append(CodeNode(
                    name=node.name,
                    node_type="class",
                    code=code,
                    file_path=str(path),
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=ast.get_docstring(node)
                ))
        
        return nodes
    
    def _find_parent_class(self, tree: ast.AST, target: ast.AST) -> str | None:
        """Find if a function is inside a class"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    if child is target:
                        return node.name
        return None
    
    def _extract_code(self, lines: list[str], start: int, end: int | None) -> str:
        """Extract code lines"""
        if end is None:
            end = start + 1
        return "\n".join(lines[start:end])
    
    def _extract_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Extract function signature"""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        
        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"
        
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)}){returns}"


class TypeScriptParser:
    """Parse TypeScript/JavaScript files into code nodes using regex (simplified)"""
    
    # Patterns for TS/JS parsing
    FUNCTION_PATTERN = re.compile(
        r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)[^{]*\{',
        re.MULTILINE
    )
    
    ARROW_FUNCTION_PATTERN = re.compile(
        r'^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>',
        re.MULTILINE
    )
    
    CLASS_PATTERN = re.compile(
        r'^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
        re.MULTILINE
    )
    
    def parse_file(self, file_path: str) -> list[CodeNode]:
        """Parse a TypeScript/JavaScript file into code nodes"""
        path = Path(file_path)
        if not path.exists() or path.suffix not in (".ts", ".tsx", ".js", ".jsx"):
            return []
        
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        nodes = []
        
        # Find functions
        for match in self.FUNCTION_PATTERN.finditer(content):
            name = match.group(1)
            start_line = content[:match.start()].count("\n") + 1
            end_line = self._find_block_end(lines, start_line - 1)
            
            nodes.append(CodeNode(
                name=name,
                node_type="function",
                code=self._extract_code(lines, start_line - 1, end_line),
                file_path=str(path),
                line_start=start_line,
                line_end=end_line
            ))
        
        # Find arrow functions
        for match in self.ARROW_FUNCTION_PATTERN.finditer(content):
            name = match.group(1)
            start_line = content[:match.start()].count("\n") + 1
            end_line = self._find_block_end(lines, start_line - 1)
            
            nodes.append(CodeNode(
                name=name,
                node_type="function",
                code=self._extract_code(lines, start_line - 1, end_line),
                file_path=str(path),
                line_start=start_line,
                line_end=end_line
            ))
        
        # Find classes
        for match in self.CLASS_PATTERN.finditer(content):
            name = match.group(1)
            start_line = content[:match.start()].count("\n") + 1
            end_line = self._find_block_end(lines, start_line - 1)
            
            nodes.append(CodeNode(
                name=name,
                node_type="class",
                code=self._extract_code(lines, start_line - 1, end_line),
                file_path=str(path),
                line_start=start_line,
                line_end=end_line
            ))
        
        return nodes
    
    def _find_block_end(self, lines: list[str], start: int) -> int:
        """Find end of a code block by counting braces"""
        brace_count = 0
        started = False
        
        for i in range(start, len(lines)):
            line = lines[i]
            for char in line:
                if char == "{":
                    brace_count += 1
                    started = True
                elif char == "}":
                    brace_count -= 1
            
            if started and brace_count == 0:
                return i + 1
        
        return len(lines)
    
    def _extract_code(self, lines: list[str], start: int, end: int) -> str:
        """Extract code lines"""
        return "\n".join(lines[start:end])


class DescriptionGenerator:
    """Generate natural language descriptions for code using Claude"""
    
    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()
    
    def generate(self, node: CodeNode) -> str:
        """Generate a description for a code node"""
        
        # If docstring exists, use it as base
        if node.docstring:
            return node.docstring
        
        # Generate using Claude
        prompt = f"""Describe what this {node.node_type} does in 1-2 sentences. Be specific about its purpose and behavior.

```
{node.code[:2000]}
```

Respond with only the description, no preamble."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            # Fallback to basic description
            return f"A {node.node_type} named {node.name}"


class EnhancedCodeIndexer:
    """Index code with semantic enrichment for better RAG retrieval"""
    
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        generate_descriptions: bool = True
    ):
        self.kb = knowledge_base
        self.generate_descriptions = generate_descriptions
        self.python_parser = PythonParser()
        self.ts_parser = TypeScriptParser()
        
        if generate_descriptions:
            self.description_generator = DescriptionGenerator()
        else:
            self.description_generator = None
    
    def index_file(self, file_path: str) -> int:
        """Index a single file, returns number of nodes indexed"""
        path = Path(file_path)
        
        if path.suffix == ".py":
            nodes = self.python_parser.parse_file(file_path)
        elif path.suffix in (".ts", ".tsx", ".js", ".jsx"):
            nodes = self.ts_parser.parse_file(file_path)
        else:
            # For other files, index as whole file
            return self._index_whole_file(file_path)
        
        for node in nodes:
            self._index_node(node)
        
        return len(nodes)
    
    def index_directory(
        self,
        directory: str,
        extensions: list[str] | None = None,
        exclude_dirs: list[str] | None = None
    ) -> dict:
        """Index all code files in a directory"""
        
        extensions = extensions or [".py", ".ts", ".tsx", ".js", ".jsx"]
        exclude_dirs = exclude_dirs or ["node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"]
        
        stats = {
            "files_processed": 0,
            "nodes_indexed": 0,
            "errors": []
        }
        
        dir_path = Path(directory)
        
        for file_path in dir_path.rglob("*"):
            # Skip excluded directories
            if any(excl in file_path.parts for excl in exclude_dirs):
                continue
            
            if file_path.is_file() and file_path.suffix in extensions:
                try:
                    count = self.index_file(str(file_path))
                    stats["files_processed"] += 1
                    stats["nodes_indexed"] += count
                except Exception as e:
                    stats["errors"].append(f"{file_path}: {e}")
        
        return stats
    
    def _index_node(self, node: CodeNode):
        """Index a single code node with description"""
        
        # Generate description if enabled
        description = ""
        if self.generate_descriptions and self.description_generator:
            description = self.description_generator.generate(node)
        elif node.docstring:
            description = node.docstring
        else:
            description = f"A {node.node_type} named {node.name}"
        
        # Build content with description + code
        content = f"""## {node.node_type.title()}: {node.name}

{description}

```
{node.code}
```"""
        
        # Build metadata
        metadata = {
            "name": node.name,
            "type": node.node_type,
            "file_path": node.file_path,
            "line_start": node.line_start,
            "line_end": node.line_end,
        }
        
        if node.parent:
            metadata["parent_class"] = node.parent
        
        if node.signature:
            metadata["signature"] = node.signature
        
        # Add to knowledge base
        self.kb.add_document(
            content=content,
            doc_type="code",
            metadata=metadata,
            doc_id=f"{node.file_path}:{node.name}:{node.line_start}"
        )
    
    def _index_whole_file(self, file_path: str) -> int:
        """Index a file as a whole (for non-parseable files)"""
        path = Path(file_path)
        
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return 0
        
        self.kb.add_document(
            content=content,
            doc_type="code",
            metadata={
                "name": path.name,
                "type": "file",
                "file_path": str(path),
                "extension": path.suffix
            }
        )
        
        return 1


def index_codebase(
    project_id: str,
    code_path: str,
    generate_descriptions: bool = True
) -> dict:
    """Index a codebase with enhanced semantic understanding"""
    
    kb = KnowledgeBase(project_id)
    indexer = EnhancedCodeIndexer(kb, generate_descriptions=generate_descriptions)
    
    stats = indexer.index_directory(code_path)
    
    return {
        "project_id": project_id,
        "code_path": code_path,
        **stats
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python enhanced_indexing.py <project_id> <code_path>")
        sys.exit(1)
    
    project_id = sys.argv[1]
    code_path = sys.argv[2]
    
    print(f"Indexing {code_path} for project {project_id}...")
    
    # Index without description generation for faster testing
    stats = index_codebase(project_id, code_path, generate_descriptions=False)
    
    print(f"\nIndexing complete:")
    print(f"  Files processed: {stats['files_processed']}")
    print(f"  Nodes indexed: {stats['nodes_indexed']}")
    
    if stats["errors"]:
        print(f"  Errors: {len(stats['errors'])}")
        for error in stats["errors"][:5]:
            print(f"    - {error}")
