import { resolve, sep } from "node:path";

function checkWithinRoot(root: string, target: string): string {
  const rootResolved = resolve(root);
  const targetResolved = resolve(target);
  const rootPrefix = rootResolved + sep;
  if (targetResolved !== rootResolved && !targetResolved.startsWith(rootPrefix)) {
    throw new Error(`Path escapes workspace root: ${target} resolves to ${targetResolved}`);
  }
  return target;
}

/**
 * Get the directory path for an entity type's data.
 *
 * @param root - Workspace root directory.
 * @param namespace - App namespace (e.g., 'apps/crm').
 * @param plural - Entity plural name (e.g., 'contacts').
 * @returns Path to the entity data directory.
 * @throws Error if the resolved path escapes the workspace root.
 */
export function entityDir(root: string, namespace: string, plural: string): string {
  const target = `${root}/${namespace}/data/${plural}`;
  return checkWithinRoot(root, target);
}

/**
 * Get the file path for a specific entity.
 *
 * @param root - Workspace root directory.
 * @param namespace - App namespace (e.g., 'apps/crm').
 * @param plural - Entity plural name (e.g., 'contacts').
 * @param entityId - Prefixed ULID (e.g., 'ct_01JKXM...').
 * @returns Path to the entity JSON file.
 * @throws Error if the resolved path escapes the workspace root.
 */
export function entityPath(
  root: string,
  namespace: string,
  plural: string,
  entityId: string,
): string {
  const target = `${root}/${namespace}/data/${plural}/${entityId}.json`;
  return checkWithinRoot(root, target);
}

/**
 * Get the directory path for an app's schemas.
 *
 * @param root - Workspace root directory.
 * @param namespace - App namespace (e.g., 'apps/crm').
 * @returns Path to the schemas directory.
 * @throws Error if the resolved path escapes the workspace root.
 */
export function schemaDir(root: string, namespace: string): string {
  const target = `${root}/${namespace}/schemas`;
  return checkWithinRoot(root, target);
}
