# upjack

Schema-driven entity management for AI-native applications. TypeScript edition.

```bash
npm install upjack
```

```typescript
import { UpjackApp } from "upjack";

const app = UpjackApp.fromManifest("manifest.json");

// Typed CRUD + search for every entity you define
const contact = app.createEntity("contact", { name: "Alice", email: "alice@example.com" });
const results = app.searchEntities("contact", { query: "alice" });
```

```typescript
// One function call → full MCP server
import { createServer } from "upjack/server";

const server = createServer("manifest.json");
// Tools: create_contact, get_contact, update_contact, list_contacts, search_contacts, delete_contact
```

See the [main README](../../README.md) for full documentation.

## Development

```bash
npm install
make check    # format + lint + typecheck + test
make build    # produces dist/
```

## License

Apache 2.0
