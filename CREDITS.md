# Credits and source licences

Checked on 2026-09-07.

- [Bentley Systems OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp)
  provides the STAAD.Pro MCP server and its public tool contract. Its repository
  is licensed under MIT in
  [`LICENSE.md`](https://github.com/BentleySystems/openstaad-mcp/blob/main/LICENSE.md).
  Bentley Systems also provides the
  [MicroStation](https://www.bentley.com/software/microstation/) MCP server
  used by this adapter. MicroStation MCP is distributed with Bentley software
  and no code from it is redistributed here.
- [`yixuanzhong/PLAXIS-MCP`](https://github.com/yixuanzhong/PLAXIS-MCP)
  is licensed under
  [MIT](https://github.com/yixuanzhong/PLAXIS-MCP/blob/main/LICENSE).
  Its machine-level profile store, Windows Credential Manager storage, and
  fail-closed rejection of endpoint environment overrides shaped this
  adapter's resolve and emit design.
- [`Sompote/plaxisMCP`](https://github.com/Sompote/plaxisMCP) was consulted as
  a reference implementation. Its README states that the MCP server code is
  MIT and its bundled `plxscripting` component is under the Plaxis Public
  License 1.0. The repository has no root licence file detected by GitHub, so
  no code from it is copied here.
- [`gaopengbin/cesium-mcp`](https://github.com/gaopengbin/cesium-mcp) is
  licensed under [MIT](https://github.com/gaopengbin/cesium-mcp/blob/main/LICENSE).
  Its protocol-neutral command core with separate protocol adapters is the
  architectural pattern followed here.
- [`SeequentEvo/evo-mcp`](https://github.com/SeequentEvo/evo-mcp) is licensed
  under
  [Apache-2.0](https://github.com/SeequentEvo/evo-mcp/blob/main/LICENSE.md).
  Its tool filtering is cited as prior art for catalogue-size control, which
  this adapter has not yet solved across every client.
- [Anthropic](https://www.anthropic.com/) created the Model Context Protocol.
  This adapter follows the
  [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18).
  The specification repository records a transition from MIT to Apache-2.0,
  with non-specification documentation under CC-BY-4.0.
- [PyYAML](https://github.com/yaml/pyyaml) is the only runtime dependency and
  is MIT licensed.
- [`ggml-org/llama.cpp`](https://github.com/ggml-org/llama.cpp) is licensed
  under [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE).
  This adapter targets its OpenAI-compatible server endpoints and explicit
  Jinja tool-template path. No llama.cpp code or model weights are bundled.

Bentley, MicroStation, STAAD.Pro, PLAXIS, Seequent, Anthropic, Cesium, and
other names are trademarks of their respective owners.
