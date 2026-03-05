## [TRACKED] TypeScript server: entity schemas not passed to MCP tool definitions

**Type**: bug
**File**: lib/typescript/src/server.ts (lines 86-93, 107-122)
**Priority**: high
**Found during**: #6

**Description**:
The TypeScript server has the same bug as the Python server — `create_*` and `update_*`
tools use `z.record(z.string(), z.unknown())` which produces `{"type": "object"}` with
no properties. LLMs can't see entity field structure.

The Python server was fixed by subclassing FastMCP's `Tool` class with raw JSON Schema
parameters. The TypeScript MCP SDK (`@modelcontextprotocol/sdk`) is tightly coupled to
Zod — `McpServer.registerTool()` stores schemas via `getZodSchemaObject()` and converts
them via `toJsonSchemaCompat()` on listing. There's no escape hatch for raw JSON Schema.

**Suggested approach**:
1. Build Zod schemas programmatically from entity JSON Schema at registration time
   (walk the JSON Schema tree, emit `z.object()`, `z.array()`, `z.string()`, etc.)
2. OR use a library like `json-schema-to-zod` for runtime conversion
3. OR access the lower-level `Server` class from `@modelcontextprotocol/sdk` which
   works with raw JSON Schema in protocol messages (bigger refactor)

Option 1 is likely cleanest — a `jsonSchemaToZod()` utility function that handles the
subset of JSON Schema features used in entity schemas (object, array, string, number,
integer, boolean, enum, required, properties, items, minimum, maximum, format, description).
