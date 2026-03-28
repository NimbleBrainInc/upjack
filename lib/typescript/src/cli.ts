#!/usr/bin/env node
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const MANIFEST_TEMPLATE = {
  manifest_version: "0.4",
  name: "",
  version: "0.1.0",
  title: "",
  description: "",
  server: {
    type: "node",
    entry_point: "server",
    mcp_config: { command: "node", args: ["server.ts"] },
  },
  _meta: {
    "ai.nimblebrain/upjack": {
      upjack_version: "0.1",
      namespace: "",
      entities: [] as Array<Record<string, unknown>>,
      context: "context.md",
      seed: { data: "seed/", run_on_install: true },
    },
  },
};

const SCHEMA_TEMPLATE = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "",
  description: "",
  allOf: [{ $ref: "https://upjack.dev/schemas/v1/upjack-entity.schema.json" }],
  properties: {
    name: { type: "string", maxLength: 256, description: "Display name" },
  },
  required: ["name"],
};

const SERVER_TEMPLATE = `import { resolve } from "node:path";
import { startServer } from "upjack/server";

const manifest = resolve(import.meta.dirname, "manifest.json");
startServer(manifest);
`;

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/ /g, "-")
    .replace(/^-+|-+$/g, "");
}

export function makePrefix(name: string): string {
  const n = name.toLowerCase().trim();
  if (n.length <= 4) return n.slice(0, 4);
  const consonants = [...n.slice(1)].filter((c) => !"aeiou ".includes(c));
  const prefix = n[0] + consonants.join("");
  return prefix.length >= 3 ? prefix.slice(0, 3) : n.slice(0, 3);
}

async function prompt(message: string, defaultVal = ""): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  const suffix = defaultVal ? ` [${defaultVal}]` : "";
  return new Promise((resolve) => {
    rl.question(`${message}${suffix}: `, (answer) => {
      rl.close();
      resolve(answer.trim() || defaultVal);
    });
  });
}

export async function init(args: string[]): Promise<void> {
  let directory: string | undefined;
  let appName: string | undefined;
  let entityName: string | undefined;

  // Simple arg parsing
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--name" && args[i + 1]) {
      appName = args[++i];
    } else if (args[i] === "--entity" && args[i + 1]) {
      entityName = args[++i];
    } else if (!args[i].startsWith("-")) {
      directory = args[i];
    }
  }

  if (!appName) {
    appName = await prompt("App name", "my-app");
  }
  const slug = slugify(appName);

  if (!directory) {
    directory = resolve(slug);
  } else {
    directory = resolve(directory);
  }

  if (!entityName) {
    entityName = await prompt("First entity type (e.g., task, contact, note)", "item");
  }
  entityName = entityName.toLowerCase().trim();

  const entityPlural = `${entityName}s`;
  const prefix = makePrefix(entityName);

  if (existsSync(directory) && readdirSync(directory).length > 0) {
    process.stderr.write(`Error: ${directory} already exists and is not empty.\n`);
    process.exit(1);
  }

  mkdirSync(directory, { recursive: true });
  mkdirSync(`${directory}/schemas`);
  mkdirSync(`${directory}/seed`);
  mkdirSync(`${directory}/skills`);

  // Manifest
  const manifest = JSON.parse(JSON.stringify(MANIFEST_TEMPLATE));
  manifest.name = slug;
  manifest.title = appName.replace(/-/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
  manifest.description = `A ${appName} app built with Upjack`;
  const upjack = manifest._meta["ai.nimblebrain/upjack"];
  upjack.namespace = `apps/${slug}`;
  upjack.entities = [
    {
      name: entityName,
      plural: entityPlural,
      schema: `schemas/${entityName}.schema.json`,
      prefix,
      index: true,
    },
  ];
  writeFileSync(`${directory}/manifest.json`, `${JSON.stringify(manifest, null, 2)}\n`);

  // Schema
  const schema = JSON.parse(JSON.stringify(SCHEMA_TEMPLATE));
  schema.title = entityName.charAt(0).toUpperCase() + entityName.slice(1);
  schema.description = `A ${entityName} entity`;
  writeFileSync(
    `${directory}/schemas/${entityName}.schema.json`,
    `${JSON.stringify(schema, null, 2)}\n`,
  );

  // Server
  writeFileSync(`${directory}/server.ts`, SERVER_TEMPLATE);

  // Context
  const title = appName.replace(/-/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
  const context = `# ${title} Domain Knowledge

You are managing a ${title} application. Help the user work effectively with ${entityPlural}.

## Entity Types

- **${entityName.charAt(0).toUpperCase() + entityName.slice(1)}**: The primary entity type. Prefix: \`${prefix}_\`

## Rules

- Validate data before creating or updating entities
- Keep records up to date
`;
  writeFileSync(`${directory}/context.md`, context);

  // Seed
  const seedData = [{ type: entityName, name: `Sample ${entityName}` }];
  writeFileSync(
    `${directory}/seed/sample-${entityPlural}.json`,
    `${JSON.stringify(seedData, null, 2)}\n`,
  );

  process.stderr.write(`Created Upjack app at ${directory}/\n`);
  process.stderr.write("\nNext steps:\n");
  process.stderr.write(`  cd ${slug}\n`);
  process.stderr.write(`  # Edit schemas/${entityName}.schema.json to add your fields\n`);
  process.stderr.write("  # Edit context.md with your domain knowledge\n");
  process.stderr.write("  npx tsx server.ts\n");
}

async function serve(args: string[]): Promise<void> {
  const manifestPath = args[0];
  if (!manifestPath) {
    process.stderr.write("Usage: upjack serve <manifest.json> [--root <dir>]\n");
    process.exit(1);
  }

  let root: string | undefined;
  const rootIdx = args.indexOf("--root");
  if (rootIdx !== -1 && args[rootIdx + 1]) {
    root = args[rootIdx + 1];
  }

  const { resolveRoot } = await import("./paths.js");
  const resolved = resolveRoot(root);
  mkdirSync(resolved, { recursive: true });

  const { startServer } = await import("./server.js");
  await startServer(resolve(manifestPath), resolved);
}

export async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === "init") {
    await init(args.slice(1));
  } else if (command === "serve") {
    await serve(args.slice(1));
  } else {
    process.stderr.write(
      "Usage: upjack <command>\n\nCommands:\n  init     Scaffold a new Upjack app\n  serve    Run MCP server from a manifest\n",
    );
    process.exit(1);
  }
}

// Only auto-execute when run directly (not when imported for testing)
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    process.stderr.write(`Error: ${err.message}\n`);
    process.exit(1);
  });
}
