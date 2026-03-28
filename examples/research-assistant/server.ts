import { resolve } from "node:path";
import { startServer } from "upjack/server";

const manifest = resolve(import.meta.dirname, "manifest.json");
startServer(manifest);
