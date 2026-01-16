"""
Agent Factory and Execution
Handles loading agent configurations and executing agent tasks via Claude API
"""

import os
import yaml
import asyncio
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
import anthropic

if TYPE_CHECKING:
    from core.audit import AuditLogger


@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    id: str
    role: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt_file: str
    description: str
    responsibilities: list[str]
    tools: list[str] | None = None
    perspective: str | None = None  # For voters


@dataclass
class AgentResponse:
    """Response from an agent execution"""
    agent_id: str
    role: str
    content: str
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None = None


class AgentFactory:
    """Factory for creating and managing agents"""
    
    def __init__(self, config_path: str = "agents/definitions.yaml"):
        self.config_path = Path(config_path)
        self.agents: dict[str, AgentConfig] = {}
        self.voters: dict[str, AgentConfig] = {}
        self.system_prompts: dict[str, str] = {}
        self._load_configurations()
    
    def _load_configurations(self):
        """Load all agent configurations from YAML"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        # Load regular agents
        for agent_data in config.get("agents", []):
            agent = AgentConfig(
                id=agent_data["id"],
                role=agent_data["role"],
                model=agent_data["model"],
                temperature=agent_data["temperature"],
                max_tokens=agent_data["max_tokens"],
                system_prompt_file=agent_data["system_prompt_file"],
                description=agent_data["description"],
                responsibilities=agent_data["responsibilities"],
                tools=agent_data.get("tools")
            )
            self.agents[agent.id] = agent
        
        # Load voters
        for voter_data in config.get("voters", []):
            voter = AgentConfig(
                id=voter_data["id"],
                role=voter_data["role"],
                model=voter_data["model"],
                temperature=voter_data["temperature"],
                max_tokens=2048,
                system_prompt_file=voter_data["system_prompt_file"],
                description=voter_data["perspective"],
                responsibilities=[],
                perspective=voter_data["perspective"]
            )
            self.voters[voter.id] = voter
    
    def get_agent(self, agent_id: str) -> AgentConfig | None:
        """Get agent configuration by ID"""
        return self.agents.get(agent_id) or self.voters.get(agent_id)
    
    def get_system_prompt(self, agent: AgentConfig) -> str:
        """Load system prompt for an agent"""
        if agent.id not in self.system_prompts:
            prompt_path = Path(agent.system_prompt_file)
            if prompt_path.exists():
                self.system_prompts[agent.id] = prompt_path.read_text()
            else:
                # Generate default prompt
                self.system_prompts[agent.id] = self._generate_default_prompt(agent)
        return self.system_prompts[agent.id]
    
    def _generate_default_prompt(self, agent: AgentConfig) -> str:
        """Generate a default system prompt for an agent"""
        responsibilities = "\n".join(f"- {r}" for r in agent.responsibilities)
        
        prompt = f"""You are the {agent.role} in a multi-agent software development workflow.

## Your Role
{agent.description}

## Your Responsibilities
{responsibilities}

## Guidelines
1. Focus only on your area of expertise
2. Be thorough but concise in your outputs
3. Flag concerns for other agents when relevant
4. Document your decisions and rationale
5. Follow the project's coding standards and architectural patterns

## Output Format
Provide structured, actionable outputs that can be consumed by other agents in the workflow.
"""
        if agent.perspective:
            prompt += f"\n## Voting Perspective\nWhen voting, evaluate from this perspective: {agent.perspective}"
        
        return prompt
    
    def list_agents(self) -> list[str]:
        """List all available agent IDs"""
        return list(self.agents.keys())
    
    def list_voters(self) -> list[str]:
        """List all available voter IDs"""
        return list(self.voters.keys())


class AgentExecutor:
    """Executes agent tasks via Claude API"""

    def __init__(self, factory: AgentFactory, audit_logger: "Optional[AuditLogger]" = None):
        self.factory = factory
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.audit_logger = audit_logger
        self.current_phase: Optional[str] = None
        self.current_checkpoint: Optional[str] = None

    def set_phase(self, phase: str, checkpoint: Optional[str] = None):
        """Set current workflow phase for audit logging"""
        self.current_phase = phase
        self.current_checkpoint = checkpoint

    async def execute(
        self,
        agent_id: str,
        task: str,
        context: str = "",
        conversation_history: list[dict] | None = None
    ) -> AgentResponse:
        """Execute a task with a specific agent"""
        agent = self.factory.get_agent(agent_id)
        if not agent:
            return AgentResponse(
                agent_id=agent_id,
                role="unknown",
                content="",
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=f"Agent {agent_id} not found"
            )

        system_prompt = self.factory.get_system_prompt(agent)

        # Build messages
        messages = conversation_history or []

        # Add context and task
        user_content = ""
        if context:
            user_content += f"## Context\n{context}\n\n"
        user_content += f"## Task\n{task}"

        messages.append({"role": "user", "content": user_content})

        # Track timing for audit
        start_time = time.perf_counter()

        try:
            response = self.client.messages.create(
                model=agent.model,
                max_tokens=agent.max_tokens,
                temperature=agent.temperature,
                system=system_prompt,
                messages=messages
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            content = response.content[0].text if response.content else ""

            result = AgentResponse(
                agent_id=agent_id,
                role=agent.role,
                content=content,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                success=True
            )

            # Log to audit trail
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id=agent_id,
                    model=agent.model,
                    input_text=user_content,
                    output_text=content,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    duration_ms=duration_ms,
                    phase=self.current_phase,
                    checkpoint=self.current_checkpoint,
                    success=True
                )

            return result

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Log failure to audit trail
            if self.audit_logger:
                self.audit_logger.log_agent_call(
                    agent_id=agent_id,
                    model=agent.model,
                    input_text=user_content,
                    output_text="",
                    input_tokens=0,
                    output_tokens=0,
                    duration_ms=duration_ms,
                    phase=self.current_phase,
                    checkpoint=self.current_checkpoint,
                    success=False,
                    error=str(e)
                )

            return AgentResponse(
                agent_id=agent_id,
                role=agent.role,
                content="",
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=str(e)
            )
    
    async def execute_parallel(
        self,
        agent_tasks: list[tuple[str, str, str]],  # (agent_id, task, context)
    ) -> list[AgentResponse]:
        """Execute multiple agent tasks in parallel"""
        tasks = [
            self.execute(agent_id, task, context)
            for agent_id, task, context in agent_tasks
        ]
        return await asyncio.gather(*tasks)


# Convenience function for synchronous execution
def run_agent(
    agent_id: str,
    task: str,
    context: str = "",
    config_path: str = "agents/definitions.yaml"
) -> AgentResponse:
    """Run a single agent task synchronously"""
    factory = AgentFactory(config_path)
    executor = AgentExecutor(factory)
    return asyncio.run(executor.execute(agent_id, task, context))


if __name__ == "__main__":
    # Example usage
    factory = AgentFactory()
    
    print("Available Agents:")
    for agent_id in factory.list_agents():
        agent = factory.get_agent(agent_id)
        print(f"  - {agent_id}: {agent.role}")
    
    print("\nAvailable Voters:")
    for voter_id in factory.list_voters():
        voter = factory.get_agent(voter_id)
        print(f"  - {voter_id}: {voter.role}")
