#!/usr/bin/env node
// Build Forge CLI - multi-agent skills installer, linker and verifier
// Dependency-free, Node 18+ compatible.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const AGENTS = [
  {
    id: 'claude',
    label: 'Claude Code',
    skillsFolder: '.claude/skills',
    pointerFile: 'CLAUDE.md'
  },
  {
    id: 'gemini',
    label: 'Gemini CLI',
    skillsFolder: null,
    pointerFile: 'GEMINI.md'
  },
  {
    id: 'copilot',
    label: 'GitHub Copilot',
    skillsFolder: null,
    pointerFile: '.github/copilot-instructions.md'
  },
  {
    id: 'cursor',
    label: 'Cursor',
    skillsFolder: null,
    pointerFile: '.cursorrules'
  },
  {
    id: 'windsurf',
    label: 'Windsurf',
    skillsFolder: null,
    pointerFile: '.windsurfrules'
  },
  {
    id: 'codex',
    label: 'OpenAI Codex',
    skillsFolder: null,
    pointerFile: null
  }
];

const POINTER_CONTENT = 'Read AGENTS.md first and follow it. If AGENTS.md does not exist yet, run the project-bootstrap skill at .agents/skills/project-bootstrap/SKILL.md.\n';

function hashFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const normalized = content.replace(/\r\n/g, '\n');
  return crypto.createHash('sha256').update(normalized, 'utf8').digest('hex');
}

function computeSkillsManifest(skillsDir) {
  const manifest = {};
  function walk(dir, relPrefix) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const rel = path.join(relPrefix, entry.name);
      if (entry.isDirectory()) {
        walk(full, rel);
      } else if (entry.isFile()) {
        // use forward slashes in manifest
        const normalizedRel = rel.split(path.sep).join('/');
        manifest[normalizedRel] = hashFile(full);
      }
    }
  }
  walk(skillsDir, 'skills');
  return manifest;
}

function parseArgs(args) {
  let command = 'install';
  const positional = [];
  let force = false;
  let agentsArg = null;

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--force') {
      force = true;
    } else if (a === '--agents') {
      agentsArg = args[++i];
    } else if (a.startsWith('--agents=')) {
      agentsArg = a.slice('--agents='.length);
    } else if (a.startsWith('-')) {
      // ignore other flags
    } else {
      positional.push(a);
    }
  }

  if (positional.length > 0) {
    const first = positional[0].toLowerCase();
    if (['install', 'link', 'unlink', 'verify', 'help'].includes(first)) {
      command = first;
    }
  }

  return { command, force, agentsArg };
}

function resolveSelectedAgents(agentsArg, cwd) {
  if (!agentsArg || agentsArg === 'all') {
    return AGENTS;
  }
  if (agentsArg === 'auto') {
    return AGENTS.filter(agent => {
      if (agent.skillsFolder) {
        const topDir = agent.skillsFolder.split('/')[0];
        if (fs.existsSync(path.join(cwd, topDir))) return true;
        if (fs.existsSync(path.join(cwd, agent.skillsFolder))) return true;
      }
      if (agent.pointerFile) {
        const topDir = agent.pointerFile.split('/')[0];
        if (fs.existsSync(path.join(cwd, topDir))) return true;
        if (fs.existsSync(path.join(cwd, agent.pointerFile))) return true;
      }
      if (agent.id === 'codex' && fs.existsSync(path.join(cwd, '.codex'))) {
        return true;
      }
      return false;
    });
  }
  const ids = agentsArg.split(',').map(s => s.trim().toLowerCase());
  return AGENTS.filter(agent => ids.includes(agent.id));
}

function installCommand(cwd, force, agentsArg) {
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');

  if (!fs.existsSync(packageSkillsDir)) {
    console.error('Skills folder not found in the package.');
    process.exit(1);
  }

  fs.mkdirSync(targetSkillsDir, { recursive: true });

  const added = [];
  const kept = [];
  for (const name of fs.readdirSync(packageSkillsDir)) {
    const from = path.join(packageSkillsDir, name);
    if (!fs.statSync(from).isDirectory()) continue;
    const to = path.join(targetSkillsDir, name);
    if (fs.existsSync(to) && !force) {
      kept.push(name);
      continue;
    }
    fs.cpSync(from, to, { recursive: true, force: true });
    added.push(name);
  }

  // Write lockfile
  const manifest = computeSkillsManifest(targetSkillsDir);
  fs.writeFileSync(lockFilePath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  console.log(`Build Forge: ${added.length} skill(s) installed in .agents/skills`);
  for (const n of added) console.log(`  added  ${n}`);
  for (const n of kept) console.log(`  kept   ${n} (exists, use --force to overwrite)`);
  console.log('  lock   .agents/build-forge.lock.json written');

  if (agentsArg) {
    linkCommand(cwd, agentsArg);
  } else {
    const needingLink = AGENTS.filter(a => a.skillsFolder || a.pointerFile);
    console.log('\nHint: To link skills or pointer files for your coding agent:');
    console.log('  npx @v1006/build-forge link --agents <auto|all|id>');
    console.log('Available agents: ' + needingLink.map(a => `${a.label} (${a.id})`).join(', '));
  }
}

function normalizePathForCompare(p) {
  let resolved = path.resolve(p);
  if (resolved.startsWith('\\\\?\\')) {
    resolved = resolved.slice(4);
  }
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function removeSymlinkOrJunction(p) {
  try {
    fs.unlinkSync(p);
  } catch (err) {
    if (process.platform === 'win32') {
      try {
        fs.rmdirSync(p);
      } catch (rmErr) {
        throw err;
      }
    } else {
      throw err;
    }
  }
}

function createSymlinkOrCopy(target, linkPath, isDir, label) {
  try {
    const symlinkType = process.platform === 'win32' ? (isDir ? 'junction' : 'file') : (isDir ? 'dir' : 'file');
    const symlinkTarget = (process.platform === 'win32' && symlinkType === 'junction')
      ? path.resolve(path.dirname(linkPath), target)
      : target;
    fs.symlinkSync(symlinkTarget, linkPath, symlinkType);
  } catch (err) {
    // If linking fails, copy and warn
    if (isDir) {
      const absTarget = path.resolve(path.dirname(linkPath), target);
      fs.cpSync(absTarget, linkPath, { recursive: true });
      console.warn(`Warning: Linking failed for ${label}. Copied folder instead. Note that copies do not update on their own.`);
    } else {
      throw err;
    }
  }
}

function linkCommand(cwd, agentsArg) {
  const selected = resolveSelectedAgents(agentsArg || 'all', cwd);
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');

  if (!fs.existsSync(targetSkillsDir)) {
    console.error('.agents/skills not found. Run install first: npx @v1006/build-forge install');
    process.exit(1);
  }

  for (const agent of selected) {
    // 1. Pointer file
    if (agent.pointerFile) {
      const ptrPath = path.join(cwd, agent.pointerFile);
      if (!fs.existsSync(ptrPath)) {
        fs.mkdirSync(path.dirname(ptrPath), { recursive: true });
        fs.writeFileSync(ptrPath, POINTER_CONTENT, 'utf8');
        console.log(`  pointer  ${agent.pointerFile} created for ${agent.label}`);
      }
    }

    // 2. Skills folder
    if (agent.skillsFolder) {
      const skillsPath = path.join(cwd, agent.skillsFolder);
      let lstat = null;
      try {
        lstat = fs.lstatSync(skillsPath);
      } catch (e) {
        lstat = null;
      }

      if (!lstat) {
        // Folder does not exist. Create parent directory and relative symlink to .agents/skills
        fs.mkdirSync(path.dirname(skillsPath), { recursive: true });
        const rel = path.relative(path.dirname(skillsPath), targetSkillsDir);
        createSymlinkOrCopy(rel, skillsPath, true, agent.label);
        console.log(`  link     ${agent.skillsFolder} -> ${rel} for ${agent.label}`);
      } else if (lstat.isSymbolicLink()) {
        // Symlink already exists, no change needed
      } else if (lstat.isDirectory()) {
        // Real folder exists: add 1 relative symlink per missing skill
        const skills = fs.readdirSync(targetSkillsDir);
        for (const skill of skills) {
          const srcSkill = path.join(targetSkillsDir, skill);
          if (!fs.statSync(srcSkill).isDirectory()) continue;

          const destSkill = path.join(skillsPath, skill);
          if (fs.existsSync(destSkill)) continue; // Never overwrite

          const rel = path.relative(skillsPath, srcSkill);
          createSymlinkOrCopy(rel, destSkill, true, `${agent.label} (${skill})`);
          console.log(`  link     ${path.join(agent.skillsFolder, skill)} -> ${rel}`);
        }
      }
    }
  }
}

function unlinkCommand(cwd, agentsArg) {
  const selected = resolveSelectedAgents(agentsArg || 'all', cwd);
  const targetSkillsDir = path.resolve(cwd, '.agents', 'skills');

  for (const agent of selected) {
    if (!agent.skillsFolder) continue;
    const skillsPath = path.join(cwd, agent.skillsFolder);
    let lstat = null;
    try {
      lstat = fs.lstatSync(skillsPath);
    } catch (e) {
      continue;
    }

    if (lstat.isSymbolicLink()) {
      try {
        const rawTarget = fs.readlinkSync(skillsPath);
        const resolved = path.resolve(path.dirname(skillsPath), rawTarget);
        if (normalizePathForCompare(resolved) === normalizePathForCompare(targetSkillsDir)) {
          removeSymlinkOrJunction(skillsPath);
          console.log(`  unlinked ${agent.skillsFolder}`);
        }
      } catch (e) {
        // skip if cannot readlink
      }
    } else if (lstat.isDirectory()) {
      // Check each entry in real folder
      for (const entry of fs.readdirSync(skillsPath)) {
        const entryPath = path.join(skillsPath, entry);
        try {
          const entryStat = fs.lstatSync(entryPath);
          if (entryStat.isSymbolicLink()) {
            const raw = fs.readlinkSync(entryPath);
            const resolved = path.resolve(skillsPath, raw);
            const expectedTarget = path.join(targetSkillsDir, entry);
            if (
              normalizePathForCompare(resolved) === normalizePathForCompare(expectedTarget) ||
              normalizePathForCompare(resolved).startsWith(normalizePathForCompare(targetSkillsDir) + path.sep)
            ) {
              removeSymlinkOrJunction(entryPath);
              console.log(`  unlinked ${path.join(agent.skillsFolder, entry)}`);
            }
          }
        } catch (e) {
          // skip
        }
      }
    }
  }
}

function areDirsIdentical(dirA, dirB) {
  if (!fs.existsSync(dirA) || !fs.existsSync(dirB)) return false;
  const filesA = [];
  const filesB = [];
  function collect(dir, base, list) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const rel = path.join(base, e.name);
      if (e.isDirectory()) collect(path.join(dir, e.name), rel, list);
      else if (e.isFile()) list.push(rel);
    }
  }
  collect(dirA, '', filesA);
  collect(dirB, '', filesB);
  filesA.sort();
  filesB.sort();
  if (filesA.length !== filesB.length) return false;
  for (let i = 0; i < filesA.length; i++) {
    if (filesA[i] !== filesB[i]) return false;
    const hA = hashFile(path.join(dirA, filesA[i]));
    const hB = hashFile(path.join(dirB, filesB[i]));
    if (hA !== hB) return false;
  }
  return true;
}

function verifyCommand(cwd) {
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const targetSkillsDir = path.resolve(cwd, '.agents', 'skills');

  if (!fs.existsSync(lockFilePath)) {
    console.error('Verify error: Lock file not found at .agents/build-forge.lock.json');
    process.exit(2);
  }

  let lockData = {};
  try {
    lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
  } catch (err) {
    console.error('Verify error: Invalid JSON in .agents/build-forge.lock.json');
    process.exit(1);
  }

  let failed = false;

  // 1. Verify files against lockfile
  const currentManifest = computeSkillsManifest(targetSkillsDir);
  for (const [relFile, expectedHash] of Object.entries(lockData)) {
    const currentHash = currentManifest[relFile];
    if (!currentHash) {
      console.error(`  missing   .agents/${relFile}`);
      failed = true;
    } else if (currentHash !== expectedHash) {
      console.error(`  modified  .agents/${relFile}`);
      failed = true;
    }
  }
  for (const relFile of Object.keys(currentManifest)) {
    if (!lockData[relFile]) {
      console.error(`  extra     .agents/${relFile}`);
      failed = true;
    }
  }

  // 2. Verify agent links and copies
  for (const agent of AGENTS) {
    if (!agent.skillsFolder) continue;
    const skillsPath = path.join(cwd, agent.skillsFolder);
    let lstat = null;
    try {
      lstat = fs.lstatSync(skillsPath);
    } catch (e) {
      continue;
    }

    if (lstat.isSymbolicLink()) {
      try {
        fs.statSync(skillsPath);
      } catch (err) {
        console.error(`  broken link: ${agent.skillsFolder}`);
        failed = true;
      }
    } else if (lstat.isDirectory()) {
      for (const entry of fs.readdirSync(skillsPath)) {
        const entryPath = path.join(skillsPath, entry);
        let entryStat = null;
        try {
          entryStat = fs.lstatSync(entryPath);
        } catch (e) {
          continue;
        }

        if (entryStat.isSymbolicLink()) {
          try {
            fs.statSync(entryPath);
          } catch (err) {
            console.error(`  broken link: ${entryPath}`);
            failed = true;
          }
        } else if (entryStat.isDirectory()) {
          // It is a real folder copy of a pipeline skill if it exists in .agents/skills
          const srcSkill = path.join(targetSkillsDir, entry);
          if (fs.existsSync(srcSkill) && !areDirsIdentical(srcSkill, entryPath)) {
            console.error(`  copy differs from .agents/skills: ${entryPath}`);
            failed = true;
          }
        }
      }
    }
  }

  if (failed) {
    console.error('\nVerify failed: Integrity differences or broken links found.');
    process.exit(1);
  }

  console.log('Verify ok: All skills match lock file and all links are valid.');
  process.exit(0);
}

function main() {
  const args = process.argv.slice(2);
  const { command, force, agentsArg } = parseArgs(args);
  const cwd = process.cwd();

  if (command === 'install') {
    installCommand(cwd, force, agentsArg);
  } else if (command === 'link') {
    linkCommand(cwd, agentsArg);
  } else if (command === 'unlink') {
    unlinkCommand(cwd, agentsArg);
  } else if (command === 'verify') {
    verifyCommand(cwd);
  } else if (command === 'help') {
    console.log('Build Forge CLI');
    console.log('Commands:');
    console.log('  install [--force] [--agents <ids|auto|all>]');
    console.log('  link [--agents <ids|auto|all>]');
    console.log('  unlink [--agents <ids|auto|all>]');
    console.log('  verify');
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  AGENTS,
  POINTER_CONTENT,
  parseArgs,
  installCommand,
  linkCommand,
  unlinkCommand,
  verifyCommand
};
