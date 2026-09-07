# Concepts

- **Model:** the weights that generate text and tool calls, such as a local
  GGUF model or a hosted model.
- **Provider:** the service that runs a model. `llama-server` is a local
  provider with OpenAI-compatible HTTP routes.
- **Client or agent:** the application the user drives. It sends prompts to a
  provider and calls MCP tools.
- **MCP server:** a process that exposes tools and context. The Bentley
  application servers remain separate local processes.
- **Host:** the process that owns MCP client connections. Depending on the
  product, the host may be an editor, desktop application, or CLI.

The adapter is client-neutral because target writers are discovered from
`targets/`. It is model-neutral because provider plugins are separate from MCP
server configuration. A provider is not an MCP client.

