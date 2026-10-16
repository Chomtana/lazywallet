from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import Settings
from .prompt import SYSTEM_PROMPT
from .tools import SERVER_NAME, TOOL_NAMES, WalletTools, build_mcp_server

APPROVAL_TOOL_TIMEOUT_MS = "360000"  # > the 300 s approval wait in propose_transfer


async def connect_claude(tools: WalletTools, settings: Settings) -> ClaudeSDKClient:
    """Start a Claude Code session with only the wallet tools. Auth: ANTHROPIC_API_KEY from the root .env when set
    (the CLI inherits os.environ), otherwise the developer's Claude Code login."""
    options = ClaudeAgentOptions(
        model=settings.model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        mcp_servers={SERVER_NAME: build_mcp_server(tools)},
        allowed_tools=TOOL_NAMES,
        strict_mcp_config=True,
        setting_sources=[],
        include_partial_messages=True,
        max_turns=10,
        env={"MCP_TOOL_TIMEOUT": APPROVAL_TOOL_TIMEOUT_MS},
    )
    client = ClaudeSDKClient(options=options)
    await client.connect()
    return client
