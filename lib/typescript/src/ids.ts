import { ulid } from "ulidx";

const ID_PATTERN = /^[a-z]{2,4}_[0-9A-HJKMNP-TV-Z]{26}$/;
const PREFIX_PATTERN = /^[a-z]{2,4}$/;

/**
 * Generate a new prefixed ULID.
 *
 * @param prefix - 2-4 lowercase letter prefix (e.g., 'ct' for contact).
 * @returns Prefixed ULID string (e.g., 'ct_01JKXM9V3QWERTY123456ABCDF').
 * @throws Error if prefix doesn't match ^[a-z]{2,4}$.
 */
export function generateId(prefix: string): string {
  if (!PREFIX_PATTERN.test(prefix)) {
    throw new Error(`Invalid prefix '${prefix}': must be 2-4 lowercase letters`);
  }
  return `${prefix}_${ulid()}`;
}

/**
 * Parse a prefixed ULID into [prefix, ulidStr].
 *
 * @param entityId - Prefixed ULID string.
 * @returns Tuple of [prefix, ulidString].
 * @throws Error if the ID doesn't match the expected format.
 */
export function parseId(entityId: string): [string, string] {
  if (!validateId(entityId)) {
    throw new Error(`Invalid entity ID: '${entityId}'`);
  }
  const idx = entityId.indexOf("_");
  return [entityId.slice(0, idx), entityId.slice(idx + 1)];
}

/**
 * Check if a string is a valid prefixed ULID.
 *
 * @param entityId - String to validate.
 * @returns True if valid, false otherwise.
 */
export function validateId(entityId: string): boolean {
  return ID_PATTERN.test(entityId);
}
