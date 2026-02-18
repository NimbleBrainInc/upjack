#!/usr/bin/env tsx

/**
 * Validate that bundled schemas compile with AJV2020 and can validate sample data.
 */

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readdir, readFile } from 'fs/promises';
import { dirname, join, basename } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SCHEMA_DIR = join(__dirname, '..', 'v1');

const SAMPLE_ENTITY = {
  id: 'ct_01JKXM9V3QWERTY123456ABCDF',
  type: 'contact',
  version: 1,
  created_at: '2026-02-17T12:00:00Z',
  updated_at: '2026-02-17T12:00:00Z',
  created_by: 'agent',
  status: 'active',
  tags: ['hot-lead'],
  relationships: [],
  first_name: 'Sarah',
  last_name: 'Chen'
};

const SAMPLE_MANIFEST = {
  upjack_version: '0.1',
  namespace: 'apps/crm',
  display: {
    name: 'CRM',
    icon: '📊',
    category: 'sales'
  },
  entities: [
    {
      name: 'contact',
      schema: 'schemas/contact.schema.json',
      prefix: 'ct'
    }
  ],
  skills: [
    {
      source: 'bundled',
      path: 'skills/lead-qualification/SKILL.md'
    }
  ],
  context: 'context.md'
};

// Sample full MCPB manifest with Upjack extension (validates upjack-app schema)
const SAMPLE_APP: Record<string, unknown> = {
  name: 'nimblebrain-crm',
  version: '0.1.0',
  description: 'A CRM app built with Upjack',
  author: { name: 'NimbleBrain' },
  server: {
    type: 'python',
    entry_point: 'server.py',
    mcp_config: { command: 'python', args: ['-m', 'crm.server'] }
  },
  _meta: {
    'ai.nimblebrain/upjack': SAMPLE_MANIFEST
  }
};

async function validate() {
  console.log('Validating bundled schemas...\n');

  const files = await readdir(SCHEMA_DIR);
  const bundledSchemas = files.filter(f => f.includes('.bundled.schema.json'));

  if (bundledSchemas.length === 0) {
    console.error('No bundled schemas found. Run `make bundle` first.');
    process.exit(1);
  }

  const ajv = new Ajv2020({
    allErrors: true,
    strict: false,
    validateSchema: false
  });
  addFormats(ajv);

  for (const file of bundledSchemas) {
    const schemaPath = join(SCHEMA_DIR, file);
    console.log(`Validating: ${file}`);

    const schemaText = await readFile(schemaPath, 'utf-8');
    const schema = JSON.parse(schemaText);
    const validateFn = ajv.compile(schema);

    if (file.includes('upjack-entity')) {
      // Test valid entity
      const valid = validateFn(SAMPLE_ENTITY);
      if (valid) {
        console.log('  Sample entity validates successfully.');
      } else {
        console.error('  Sample entity validation failed:');
        for (const err of validateFn.errors ?? []) {
          console.error(`    ${err.instancePath}: ${err.message}`);
        }
        process.exit(1);
      }

      // Test invalid entity (missing required fields)
      const invalid = validateFn({ id: 'bad' });
      if (!invalid) {
        console.log('  Invalid entity correctly rejected.');
      } else {
        console.error('  Invalid entity was incorrectly accepted.');
        process.exit(1);
      }
    }

    if (file.includes('upjack-manifest') && !file.includes('upjack-app')) {
      // Test valid manifest (extension block only)
      const valid = validateFn(SAMPLE_MANIFEST);
      if (valid) {
        console.log('  Sample manifest validates successfully.');
      } else {
        console.error('  Sample manifest validation failed:');
        for (const err of validateFn.errors ?? []) {
          console.error(`    ${err.instancePath}: ${err.message}`);
        }
        process.exit(1);
      }

      // Test invalid manifest (missing required fields)
      const invalid = validateFn({ upjack_version: '0.1' });
      if (!invalid) {
        console.log('  Invalid manifest correctly rejected.');
      } else {
        console.error('  Invalid manifest was incorrectly accepted.');
        process.exit(1);
      }
    }

    if (file.includes('upjack-app')) {
      // Test valid full app manifest (MCPB + Upjack extension)
      const valid = validateFn(SAMPLE_APP);
      if (valid) {
        console.log('  Sample app manifest validates successfully.');
      } else {
        console.error('  Sample app manifest validation failed:');
        for (const err of validateFn.errors ?? []) {
          console.error(`    ${err.instancePath}: ${err.message}`);
        }
        process.exit(1);
      }

      // Test MCPB manifest WITHOUT upjack extension (should fail)
      const missingUpjack = validateFn({
        name: 'plain-server',
        version: '1.0.0',
        description: 'A plain MCPB server',
        author: { name: 'Test' },
        server: {
          type: 'node',
          entry_point: 'index.js',
          mcp_config: { command: 'node', args: ['index.js'] }
        }
      });
      if (!missingUpjack) {
        console.log('  MCPB manifest without upjack extension correctly rejected.');
      } else {
        console.error('  MCPB manifest without upjack extension was incorrectly accepted.');
        process.exit(1);
      }

      // Test with invalid upjack block (missing required fields)
      const invalidUpjack = validateFn({
        name: 'bad-app',
        version: '1.0.0',
        description: 'Bad upjack app',
        author: { name: 'Test' },
        server: {
          type: 'python',
          entry_point: 'server.py',
          mcp_config: { command: 'python' }
        },
        _meta: {
          'ai.nimblebrain/upjack': {
            upjack_version: '0.1'
            // missing namespace and entities
          }
        }
      });
      if (!invalidUpjack) {
        console.log('  Invalid upjack extension correctly rejected.');
      } else {
        console.error('  Invalid upjack extension was incorrectly accepted.');
        process.exit(1);
      }
    }

    console.log();
  }

  console.log('All schema checks passed.');
}

validate();
