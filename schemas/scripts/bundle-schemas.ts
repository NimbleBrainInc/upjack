#!/usr/bin/env tsx

/**
 * Bundle all upjack schemas by resolving $ref references.
 *
 * Iterates all v1/*.schema.json files (excluding .bundled.) and creates
 * self-contained bundled schemas that validators can use without HTTP fetches.
 */

import $RefParser from '@apidevtools/json-schema-ref-parser';
import { readdir, writeFile, stat } from 'fs/promises';
import { dirname, join, basename } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SCHEMA_DIR = join(__dirname, '..', 'v1');

async function bundleSchema(inputPath: string, outputPath: string) {
  console.log(`  Bundling: ${basename(inputPath)}`);

  const bundled = await $RefParser.dereference(inputPath, {
    resolve: {
      http: {
        read: async (file) => {
          console.log(`    Fetching: ${file.url}`);
          const response = await fetch(file.url);
          if (!response.ok) {
            throw new Error(`Failed to fetch ${file.url}: ${response.status}`);
          }
          return await response.text();
        }
      }
    },
    dereference: {
      circular: 'ignore'
    }
  });

  if (bundled.$id) {
    bundled.$id = (bundled.$id as string).replace('.schema.json', '.bundled.schema.json');
  }

  const output = {
    $comment: `AUTO-GENERATED: Bundled schema with all $refs resolved. Do not edit directly. Generated at ${new Date().toISOString()}`,
    ...bundled
  };

  await writeFile(outputPath, JSON.stringify(output, null, 2) + '\n');

  const inputSize = (await stat(inputPath)).size;
  const outputSize = (await stat(outputPath)).size;
  console.log(`    Source:  ${(inputSize / 1024).toFixed(1)} KB`);
  console.log(`    Bundled: ${(outputSize / 1024).toFixed(1)} KB`);
}

async function main() {
  console.log('Bundling upjack schemas...\n');

  const files = await readdir(SCHEMA_DIR);
  const sourceSchemas = files.filter(
    f => f.endsWith('.schema.json') && !f.includes('.bundled.')
  );

  if (sourceSchemas.length === 0) {
    console.error('No source schemas found in v1/');
    process.exit(1);
  }

  try {
    for (const file of sourceSchemas) {
      const inputPath = join(SCHEMA_DIR, file);
      const outputPath = join(SCHEMA_DIR, file.replace('.schema.json', '.bundled.schema.json'));
      await bundleSchema(inputPath, outputPath);
      console.log();
    }

    console.log(`Done. Bundled ${sourceSchemas.length} schema(s).`);
  } catch (error) {
    console.error('Failed to bundle schemas:', error);
    process.exit(1);
  }
}

main();
