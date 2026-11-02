#!/usr/bin/env node
// Copies the Build Forge skills into ./.agents/skills of the current project.
// Existing skill folders are kept unless --force is passed.
const fs = require('fs');
const path = require('path');

const source = path.join(__dirname, '..', 'skills');
const target = path.join(process.cwd(), '.agents', 'skills');
const force = process.argv.includes('--force');

if (!fs.existsSync(source)) {
  console.error('Skills folder not found in the package.');
  process.exit(1);
}

fs.mkdirSync(target, { recursive: true });

const added = [];
const kept = [];
for (const name of fs.readdirSync(source)) {
  const from = path.join(source, name);
  if (!fs.statSync(from).isDirectory()) continue;
  const to = path.join(target, name);
  if (fs.existsSync(to) && !force) {
    kept.push(name);
    continue;
  }
  fs.cpSync(from, to, { recursive: true, force: true });
  added.push(name);
}

console.log(`Build Forge: ${added.length} skill(s) installed in .agents/skills`);
for (const n of added) console.log(`  added  ${n}`);
for (const n of kept) console.log(`  kept   ${n} (exists, use --force to overwrite)`);
console.log('\nNext:');
console.log('  1. pip install pyyaml');
console.log('  2. Ask your agent to run project-bootstrap');
