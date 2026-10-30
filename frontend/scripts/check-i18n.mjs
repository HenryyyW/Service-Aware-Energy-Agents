#!/usr/bin/env node
/**
 * CI gate for i18n locale files.
 *
 * Fails (exit 1) when:
 *  - a locale is missing a namespace file another locale has;
 *  - a namespace's key set differs between locales (missing or extra keys);
 *  - any leaf string is empty;
 *  - any leaf string contains a placeholder marker (TODO/FIXME/???/<...>).
 *
 * Usage: node scripts/check-i18n.mjs [localesDir]
 * Default localesDir: src/i18n/locales
 */
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const localesDir = process.argv[2] ?? join(process.cwd(), "src", "i18n", "locales");
const PLACEHOLDER_RE = /TODO|FIXME|\?\?\?|<placeholder>|LOREM_IPSUM/i;

const failures = [];

if (!existsSync(localesDir) || !statSync(localesDir).isDirectory()) {
  console.error(`[i18n] locales directory not found: ${localesDir}`);
  process.exit(1);
}

const locales = readdirSync(localesDir).filter((name) =>
  statSync(join(localesDir, name)).isDirectory(),
);
if (locales.length === 0) {
  console.error("[i18n] no locale directories found");
  process.exit(1);
}

/** Load every namespace JSON for one locale: { namespace: parsedJson }. */
function loadLocale(locale) {
  const dir = join(localesDir, locale);
  const namespaces = {};
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
    const name = file.replace(/\.json$/, "");
    try {
      namespaces[name] = JSON.parse(readFileSync(join(dir, file), "utf8"));
    } catch (err) {
      failures.push(`${locale}/${file}: invalid JSON (${err.message})`);
    }
  }
  return namespaces;
}

/** Collect leaf paths: "a.b.c" for nested objects. */
function leafPaths(obj, prefix = "", out = new Set()) {
  for (const [key, value] of Object.entries(obj ?? {})) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      leafPaths(value, path, out);
    } else {
      out.add(path);
    }
  }
  return out;
}

/** Collect bad leaf values (empty or placeholder-marked). */
function badLeaves(obj, prefix = "", out = []) {
  for (const [key, value] of Object.entries(obj ?? {})) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      badLeaves(value, path, out);
    } else if (typeof value === "string") {
      if (value.trim() === "") {
        out.push(`${path}: empty string`);
      } else if (PLACEHOLDER_RE.test(value)) {
        out.push(`${path}: placeholder marker in "${value}"`);
      }
    }
  }
  return out;
}

const perLocale = Object.fromEntries(locales.map((l) => [l, loadLocale(l)]));

// 1. Same namespace file set everywhere.
const namespaceSets = new Map(
  Object.entries(perLocale).map(([locale, ns]) => [locale, Object.keys(ns).sort()]),
);
const referenceLocale = locales[0];
const referenceNamespaces = namespaceSets.get(referenceLocale);
for (const [locale, namespaces] of namespaceSets) {
  const missing = referenceNamespaces.filter((n) => !namespaces.includes(n));
  const extra = namespaces.filter((n) => !referenceNamespaces.includes(n));
  if (missing.length) failures.push(`${locale}: missing namespace files: ${missing.join(", ")}`);
  if (extra.length) failures.push(`${locale}: unexpected namespace files: ${extra.join(", ")}`);
}

// 2. Same key set per namespace (checked against every other locale).
for (const namespace of referenceNamespaces) {
  const keySets = new Map(
    Object.entries(perLocale)
      .filter(([, ns]) => ns[namespace] !== undefined)
      .map(([locale, ns]) => [locale, leafPaths(ns[namespace])]),
  );
  const localesWithNs = [...keySets.keys()];
  for (let i = 0; i < localesWithNs.length; i++) {
    for (let j = i + 1; j < localesWithNs.length; j++) {
      const a = localesWithNs[i];
      const b = localesWithNs[j];
      const onlyA = [...keySets.get(a)].filter((k) => !keySets.get(b).has(k));
      const onlyB = [...keySets.get(b)].filter((k) => !keySets.get(a).has(k));
      if (onlyA.length)
        failures.push(
          `${namespace}: keys in ${a} but not ${b} (${onlyA.length}): ${onlyA.slice(0, 5).join(", ")}${onlyA.length > 5 ? ", ..." : ""}`,
        );
      if (onlyB.length)
        failures.push(
          `${namespace}: keys in ${b} but not ${a} (${onlyB.length}): ${onlyB.slice(0, 5).join(", ")}${onlyB.length > 5 ? ", ..." : ""}`,
        );
    }
  }
}

// 3 + 4. Leaf value quality.
for (const [locale, ns] of Object.entries(perLocale)) {
  for (const [namespace, data] of Object.entries(ns)) {
    for (const problem of badLeaves(data, namespace)) {
      failures.push(`${locale}/${problem}`);
    }
  }
}

if (failures.length) {
  console.error(`[i18n] FAILED — ${failures.length} problem(s):`);
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

const fileCount = locales.reduce(
  (sum, l) => sum + Object.keys(perLocale[l]).length,
  0,
);
console.log(
  `[i18n] OK — ${locales.length} locale(s), ${fileCount} namespace file(s), key sets consistent, no placeholders.`,
);
