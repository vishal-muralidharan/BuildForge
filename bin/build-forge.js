#!/usr/bin/env node
// Build Forge CLI - multi-agent skills installer, linker and verifier
// Dependency-free, Node 18+ compatible.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

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
const SUPPORTED_SCHEMA_VERSIONS = [1, 2];

function hashFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const normalized = content.replace(/\r\n/g, '\n');
  return crypto.createHash('sha256').update(normalized, 'utf8').digest('hex');
}

function computeSkillsManifest(skillsDir, allowedSkillNames = null) {
  const manifest = {};
  function walk(dir, relPrefix) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === '__pycache__' || entry.name.endsWith('.pyc') || entry.name === '.DS_Store') continue;
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
  if (!fs.existsSync(skillsDir)) return manifest;
  for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === '__pycache__') continue;
    if (allowedSkillNames && !allowedSkillNames.has(entry.name)) continue;
    walk(path.join(skillsDir, entry.name), path.join('skills', entry.name));
  }
  return manifest;
}

function getInstalledSkills(cwd, lockData) {
  if (lockData && Array.isArray(lockData._installed)) {
    return new Set(lockData._installed);
  }
  const skillsDir = path.join(cwd, '.agents', 'skills');
  const set = new Set();
  const pkgSkillsDir = path.join(__dirname, '..', 'skills');
  const pkgSkills = fs.existsSync(pkgSkillsDir)
    ? new Set(fs.readdirSync(pkgSkillsDir, { withFileTypes: true }).filter(d => d.isDirectory() && d.name !== '__pycache__').map(d => d.name))
    : new Set();
  const lockSkills = new Set();
  if (lockData && typeof lockData === 'object') {
    for (const k of Object.keys(lockData)) {
      if (k.startsWith('skills/')) {
        const parts = k.split('/');
        if (parts.length >= 2) lockSkills.add(parts[1]);
      }
    }
  }

  if (fs.existsSync(skillsDir)) {
    for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== '__pycache__') {
        const isPkg = pkgSkills.size === 0 || pkgSkills.has(entry.name);
        const inLock = lockSkills.size === 0 || lockSkills.has(entry.name);
        if (isPkg && inLock) {
          set.add(entry.name);
        }
      }
    }
  }
  return set;
}

function checkSkillsIntegrity(cwd) {
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const targetSkillsDir = path.resolve(cwd, '.agents', 'skills');

  if (!fs.existsSync(lockFilePath)) {
    return { ok: false, error: 'NO_LOCK', message: 'Lock file not found at .agents/build-forge.lock.json' };
  }

  let lockData = {};
  try {
    lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
  } catch (err) {
    return { ok: false, error: 'INVALID_JSON', message: 'Invalid JSON in .agents/build-forge.lock.json' };
  }

  const installedSkills = getInstalledSkills(cwd, lockData);
  const currentManifest = computeSkillsManifest(targetSkillsDir, installedSkills);

  const missing = [];
  const modified = [];
  const extra = [];

  for (const [relFile, expectedHash] of Object.entries(lockData)) {
    if (relFile.startsWith('_') || relFile === 'version') continue;
    const parts = relFile.split('/');
    if (parts.length >= 2 && parts[0] === 'skills') {
      const skillName = parts[1];
      if (!installedSkills.has(skillName)) continue;
    }
    const currentHash = currentManifest[relFile];
    if (!currentHash) {
      missing.push(relFile);
    } else if (currentHash !== expectedHash) {
      modified.push(relFile);
    }
  }

  for (const relFile of Object.keys(currentManifest)) {
    if (relFile.startsWith('_') || relFile === 'version') continue;
    if (!lockData[relFile]) {
      extra.push(relFile);
    }
  }

  const ok = (missing.length === 0 && modified.length === 0 && extra.length === 0);
  return {
    ok,
    missing,
    modified,
    extra,
    installedSkills,
    lockData,
    currentManifest,
    targetSkillsDir,
    lockFilePath
  };
}

function pruneObsoleteSkillFiles(packageSkillDir, targetSkillDir, skillName, oldLockData, workDir) {
  if (!fs.existsSync(targetSkillDir) || !oldLockData) return [];
  const pruned = [];

  function walkFiles(dir) {
    const list = [];
    if (!fs.existsSync(dir)) return list;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== '__pycache__') {
          list.push(...walkFiles(full));
        }
      } else {
        if (!entry.name.endsWith('.pyc') && entry.name !== '.DS_Store') {
          list.push(full);
        }
      }
    }
    return list;
  }

  const diskFiles = walkFiles(targetSkillDir);
  for (const file of diskFiles) {
    const relSkill = path.relative(targetSkillDir, file).replace(/\\/g, '/');
    const pkgFile = path.join(packageSkillDir, relSkill);
    if (!fs.existsSync(pkgFile)) {
      const lockKey = `skills/${skillName}/${relSkill}`;
      const oldHash = oldLockData[lockKey];
      if (oldHash) {
        const curHash = hashFile(file);
        if (curHash === oldHash) {
          try {
            fs.unlinkSync(file);
            delete oldLockData[lockKey];
            pruned.push(lockKey);
            console.log(`  removed obsolete file: .agents/${lockKey}`);
          } catch (e) {}
        } else {
          // User modified this file before upstream removed it!
          if (workDir) {
            fs.mkdirSync(workDir, { recursive: true });
            const backupName = `removed-${skillName}-${relSkill.replace(/\//g, '_')}`;
            const backupPath = path.join(workDir, backupName);
            try {
              fs.copyFileSync(file, backupPath);
              console.warn(`  warning: kept modified file removed upstream: .agents/${lockKey} (saved backup to .agents/work/${backupName})`);
            } catch (e) {}
          } else {
            console.warn(`  warning: kept modified file removed upstream: .agents/${lockKey}`);
          }
        }
      }
      // If !oldHash, file was never in old lock (user-created file) -> keep it!
    }
  }

  // Clean up empty directories from bottom to top
  function cleanEmptyDirs(dir) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== '__pycache__') {
        const full = path.join(dir, entry.name);
        cleanEmptyDirs(full);
      }
    }
    if (dir !== targetSkillDir && fs.existsSync(dir) && fs.readdirSync(dir).length === 0) {
      try {
        fs.rmdirSync(dir);
      } catch (e) {}
    }
  }
  cleanEmptyDirs(targetSkillDir);

  return pruned;
}

function generateSkillPatch(packageSkillDir, targetSkillDir, skillName, oldLockData = null) {
  if (!fs.existsSync(targetSkillDir)) return '';

  function walk(dir) {
    const list = [];
    if (!fs.existsSync(dir)) return list;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name !== '__pycache__') list.push(...walk(full));
      } else {
        if (!e.name.endsWith('.pyc') && e.name !== '.DS_Store') list.push(full);
      }
    }
    return list;
  }

  const diskFiles = walk(targetSkillDir);
  const modifiedRels = [];
  for (const f of diskFiles) {
    const rel = path.relative(targetSkillDir, f).replace(/\\/g, '/');
    const lockKey = `skills/${skillName}/${rel}`;
    const oldHash = oldLockData ? oldLockData[lockKey] : null;
    const curHash = hashFile(f);
    // If it was in oldLockData and matches oldHash, user did NOT modify it
    if (oldHash && curHash === oldHash) {
      continue;
    }
    // Otherwise it has local modifications or is a newly created file
    modifiedRels.push(rel);
  }

  if (modifiedRels.length === 0) {
    return '';
  }

  const python = findPythonCommand();
  if (python) {
    const pyScript = `
import difflib, os, sys, json
pkg_dir = sys.argv[1]
target_dir = sys.argv[2]
modified_rels = json.loads(sys.argv[3])
diff_lines = []
for rel in sorted(modified_rels):
    p_pkg = os.path.join(pkg_dir, rel)
    p_target = os.path.join(target_dir, rel)
    l1 = []
    if os.path.exists(p_pkg):
        with open(p_pkg, 'r', encoding='utf-8', errors='ignore') as fp:
            l1 = fp.readlines()
    l2 = []
    if os.path.exists(p_target):
        with open(p_target, 'r', encoding='utf-8', errors='ignore') as fp:
            l2 = fp.readlines()
    d = list(difflib.unified_diff(l1, l2, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    diff_lines.extend(d)
sys.stdout.writelines(diff_lines)
`;
    try {
      const res = spawnSync(python.cmd, [...python.args, '-c', pyScript, packageSkillDir, targetSkillDir, JSON.stringify(modifiedRels)], {
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024
      });
      if (res.stdout) return res.stdout;
    } catch (e) {}
  }
  return '';
}

function parseArgs(args) {
  let command = 'install';
  const positional = [];
  let force = false;
  let all = false;
  let help = false;
  let agentsArg = null;
  let json = false;
  let dryRun = false;
  let adopt = false;
  let yes = false;
  let patch = false;
  let noGitignore = false;
  const keepModified = new Set();
  const restore = new Set();

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--help' || a === '-h') {
      help = true;
    } else if (a === '--all') {
      all = true;
    } else if (a === '--force') {
      force = true;
    } else if (a === '--json') {
      json = true;
    } else if (a === '--dry-run') {
      dryRun = true;
    } else if (a === '--adopt') {
      adopt = true;
    } else if (a === '--yes') {
      yes = true;
    } else if (a === '--patch') {
      patch = true;
    } else if (a === '--no-gitignore') {
      noGitignore = true;
    } else if (a === '--keep-modified') {
      const next = args[++i];
      if (next) next.split(',').forEach(s => s.trim() && keepModified.add(s.trim()));
    } else if (a.startsWith('--keep-modified=')) {
      a.slice('--keep-modified='.length).split(',').forEach(s => s.trim() && keepModified.add(s.trim()));
    } else if (a === '--restore') {
      const next = args[++i];
      if (next) next.split(',').forEach(s => s.trim() && restore.add(s.trim()));
    } else if (a.startsWith('--restore=')) {
      a.slice('--restore='.length).split(',').forEach(s => s.trim() && restore.add(s.trim()));
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
    if (['install', 'link', 'unlink', 'verify', 'status', 'diff', 'doctor', 'outdated', 'update', 'upgrade', 'add', 'remove', 'list', 'help'].includes(first)) {
      command = first;
    }
  }

  if (help) {
    command = 'help';
  }

  return { command, positional, force, all, help, agentsArg, json, dryRun, adopt, yes, keepModified, restore, patch, noGitignore };
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

function installCommand(cwd, options = {}, legacyAgentsArg = null) {
  let force = false;
  let all = false;
  let agentsArg = null;
  let noGitignore = false;
  if (typeof options === 'boolean') {
    force = options;
    agentsArg = legacyAgentsArg;
  } else if (options && typeof options === 'object') {
    force = !!options.force;
    all = !!options.all;
    agentsArg = options.agentsArg || null;
    noGitignore = !!options.noGitignore;
  }
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');

  if (!fs.existsSync(packageSkillsDir)) {
    console.error('Skills folder not found in the package.');
    process.exit(1);
  }

  fs.mkdirSync(targetSkillsDir, { recursive: true });

  const workDir = path.join(cwd, '.agents', 'work');
  let oldLockData = null;
  if (fs.existsSync(lockFilePath)) {
    try { oldLockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8')); } catch (e) {}
  }

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
    if (force && fs.existsSync(to) && oldLockData) {
      pruneObsoleteSkillFiles(from, to, name, oldLockData, workDir);
    }
    fs.cpSync(from, to, { recursive: true, force: true });
    added.push(name);
  }

  // Write lockfile scoped strictly to package pipeline skills from packaged integrity.json
  const integrityPath = path.join(__dirname, '..', 'integrity.json');
  let integrity = {};
  if (fs.existsSync(integrityPath)) {
    try { integrity = JSON.parse(fs.readFileSync(integrityPath, 'utf8')); } catch (e) {}
  }
  const manifest = {};
  const allInstalledPkgSkills = new Set([...added, ...kept]);
  for (const skillName of allInstalledPkgSkills) {
    for (const [relFile, hash] of Object.entries(integrity)) {
      if (relFile.startsWith(`skills/${skillName}/`)) {
        manifest[relFile] = hash;
      }
    }
  }
  let pkgVersion = '0.1.0';
  try {
    const pkgJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
    pkgVersion = pkgJson.version || pkgVersion;
  } catch (e) {}
  manifest['_version'] = pkgVersion;
  manifest['_installed'] = Array.from(allInstalledPkgSkills).sort();
  fs.writeFileSync(lockFilePath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  const differingKept = [];
  if (kept.length > 0) {
    const diskManifest = computeSkillsManifest(targetSkillsDir, new Set(kept));
    for (const name of kept) {
      let differs = false;
      for (const [relFile, hash] of Object.entries(integrity)) {
        if (relFile.startsWith(`skills/${name}/`)) {
          if (!diskManifest[relFile] || diskManifest[relFile] !== hash) {
            differs = true;
            break;
          }
        }
      }
      if (!differs) {
        for (const relFile of Object.keys(diskManifest)) {
          if (relFile.startsWith(`skills/${name}/`) && !integrity[relFile]) {
            differs = true;
            break;
          }
        }
      }
      if (differs) {
        differingKept.push(name);
      }
    }
  }

  if (kept.length > 0 && differingKept.length > 0) {
    console.log(`Build Forge: ${added.length} skill(s) installed, ${kept.length} existing skill(s) kept.`);
    for (const n of added) console.log(`  added  ${n}`);
    for (const n of kept) {
      if (differingKept.includes(n)) {
        console.log(`  kept   ${n} (differs from package; use --force to overwrite)`);
      } else {
        console.log(`  kept   ${n} (exists, use --force to overwrite)`);
      }
    }
    console.log('  lock   .agents/build-forge.lock.json written');
    console.log(`\nNotice: ${differingKept.length} kept skill(s) differ from the package: ${differingKept.join(', ')}`);
    console.log('To review and update skills safely, run: npx @v1006/build-forge update');
  } else {
    console.log(`Build Forge: ${added.length} skill(s) installed in .agents/skills`);
    for (const n of added) console.log(`  added  ${n}`);
    for (const n of kept) console.log(`  kept   ${n} (exists, use --force to overwrite)`);
    console.log('  lock   .agents/build-forge.lock.json written');
  }

  // Ensure transient work and vendor directories are ignored if .gitignore exists
  if (!noGitignore) {
    const gitignorePath = path.join(cwd, '.gitignore');
    if (fs.existsSync(gitignorePath)) {
      try {
        let gitignoreContent = fs.readFileSync(gitignorePath, 'utf8');
        const lines = gitignoreContent.split(/\r?\n/).map(l => l.trim());
        const toAdd = [];
        if (!lines.includes('.agents/work/') && !lines.includes('.agents/work')) {
          toAdd.push('.agents/work/');
        }
        if (!lines.includes('.agents/vendor/') && !lines.includes('.agents/vendor')) {
          toAdd.push('.agents/vendor/');
        }
        if (toAdd.length > 0) {
          if (!gitignoreContent.endsWith('\n') && gitignoreContent.length > 0) {
            gitignoreContent += '\n';
          }
          gitignoreContent += toAdd.join('\n') + '\n';
          fs.writeFileSync(gitignorePath, gitignoreContent, 'utf8');
          console.log(`  ignore added ${toAdd.join(', ')} to .gitignore`);
        }
      } catch (e) {
        // Non-fatal if .gitignore is not writable
      }
    }
  }

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
  // Use 'dir' on Windows for directory symlinks. GitHub runners have Developer Mode
  // enabled (SeCreateSymbolicLinkPrivilege), so 'dir' symlinks work without UAC.
  // Junctions (mklink /J) are NOT true symlinks: Python os.path.islink() returns
  // False for them, which breaks the CI link tests.
  const symlinkType = isDir ? 'dir' : 'file';
  try {
    fs.symlinkSync(target, linkPath, symlinkType);
  } catch (err) {
    if (isDir) {
      // Last resort: copy so the agent can at least read the skills.
      const absTarget = path.resolve(path.dirname(linkPath), target);
      fs.cpSync(absTarget, linkPath, { recursive: true });
      process.stderr.write(`Warning: Linking failed for ${label}: ${err.message}. Copied folder instead.\n`);
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
  const result = checkSkillsIntegrity(cwd);
  if (!result.ok && result.error === 'NO_LOCK') {
    console.error(`Verify error: ${result.message}`);
    process.exit(2);
  }
  if (!result.ok && result.error === 'INVALID_JSON') {
    console.error(`Verify error: ${result.message}`);
    process.exit(1);
  }

  let failed = false;

  for (const relFile of result.missing) {
    console.error(`  missing   .agents/${relFile}`);
    failed = true;
  }
  for (const relFile of result.modified) {
    console.error(`  modified  .agents/${relFile}`);
    failed = true;
  }
  for (const relFile of result.extra) {
    console.error(`  extra     .agents/${relFile}`);
    failed = true;
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

function statusCommand(cwd) {
  console.log('Build Forge Status Report');
  console.log(`  Root: ${cwd}`);
  console.log(`  Node: ${process.version}`);
  console.log(`  Platform: ${process.platform}`);

  const profilePath = path.join(cwd, '.agents', 'project-profile.yaml');
  const profileOk = fs.existsSync(profilePath);
  console.log(`  Project Profile: ${profileOk ? 'Found (.agents/project-profile.yaml)' : 'Not found (run project-bootstrap)'}`);

  const skillsDir = path.join(cwd, '.agents', 'skills');
  let installedCount = 0;
  if (fs.existsSync(skillsDir)) {
    installedCount = fs.readdirSync(skillsDir).filter(name => {
      try {
        return fs.statSync(path.join(skillsDir, name)).isDirectory();
      } catch (e) {
        return false;
      }
    }).length;
  }
  console.log(`  Installed Skills: ${installedCount} in .agents/skills`);

  const lockPath = path.join(cwd, '.agents', 'build-forge.lock.json');
  let lockOk = false;
  let lockedCount = 0;
  if (fs.existsSync(lockPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
      lockedCount = Object.keys(data).length;
      lockOk = true;
    } catch (e) {}
  }
  console.log(`  Build Forge Lock: ${lockOk ? `Valid (${lockedCount} files tracked)` : 'Missing or invalid (run build-forge install)'}`);

  const refsPath = path.join(cwd, '.agents', 'references.lock.json');
  let refsCount = 0;
  if (fs.existsSync(refsPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(refsPath, 'utf8'));
      refsCount = Object.keys(data).length;
    } catch (e) {}
  }
  console.log(`  Vendor References: ${refsCount} installed (.agents/references.lock.json)`);

  console.log('  Agent Links:');
  for (const agent of AGENTS) {
    const details = [];
    if (agent.pointerFile) {
      const p = path.join(cwd, agent.pointerFile);
      if (fs.existsSync(p)) details.push('pointer: yes');
    }
    if (agent.skillsFolder) {
      const sp = path.join(cwd, agent.skillsFolder);
      try {
        const lst = fs.lstatSync(sp);
        if (lst.isSymbolicLink()) details.push('link: symlink');
        else if (lst.isDirectory()) details.push('link: folder');
      } catch (e) {
        // none
      }
    }
    const statusStr = details.length > 0 ? details.join(', ') : 'not linked';
    console.log(`    - ${agent.label} (${agent.id}): ${statusStr}`);
  }
}

function diffCommand(cwd, options = {}) {
  const patch = !!options.patch;
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');

  if (!fs.existsSync(targetSkillsDir)) {
    console.error('.agents/skills not found. Run install first: npx @v1006/build-forge install');
    process.exit(1);
  }

  const pkgManifest = computeSkillsManifest(packageSkillsDir);
  const targetSkills = new Set(
    fs.readdirSync(packageSkillsDir).filter(name => fs.statSync(path.join(packageSkillsDir, name)).isDirectory())
  );
  const currentManifest = computeSkillsManifest(targetSkillsDir, targetSkills);

  const modifiedSkillNames = new Set();
  let diffs = 0;
  for (const [relFile, pkgHash] of Object.entries(pkgManifest)) {
    const curHash = currentManifest[relFile];
    if (!curHash) {
      console.log(`  missing in project: .agents/${relFile}`);
      diffs++;
      const parts = relFile.split('/');
      if (parts.length >= 2) modifiedSkillNames.add(parts[1]);
    } else if (curHash !== pkgHash) {
      console.log(`  modified in project: .agents/${relFile}`);
      diffs++;
      const parts = relFile.split('/');
      if (parts.length >= 2) modifiedSkillNames.add(parts[1]);
    }
  }

  for (const relFile of Object.keys(currentManifest)) {
    if (!pkgManifest[relFile]) {
      console.log(`  extra in project skill: .agents/${relFile}`);
      diffs++;
      const parts = relFile.split('/');
      if (parts.length >= 2) modifiedSkillNames.add(parts[1]);
    }
  }

  if (patch && modifiedSkillNames.size > 0) {
    const workDir = path.join(cwd, '.agents', 'work');
    fs.mkdirSync(workDir, { recursive: true });
    for (const name of modifiedSkillNames) {
      const pDiff = generateSkillPatch(
        path.join(packageSkillsDir, name),
        path.join(targetSkillsDir, name),
        name
      );
      if (pDiff) {
        const patchFile = path.join(workDir, `${name}.patch`);
        fs.writeFileSync(patchFile, pDiff, 'utf8');
        console.log(`  exported patch: .agents/work/${name}.patch`);
      }
    }
  }

  if (diffs === 0) {
    console.log('Diff clean: Installed core skills match package skills exactly.');
  } else {
    console.log(`\nFound ${diffs} difference(s) between package and project skills.`);
  }
}

function findPythonCommand() {
  const candidates = [
    { cmd: 'python3', args: [] },
    { cmd: '/opt/homebrew/bin/python3', args: [] },
    { cmd: '/usr/local/bin/python3', args: [] },
    { cmd: '/usr/bin/python3', args: [] },
    { cmd: 'python', args: [] },
    { cmd: 'py', args: ['-3'] }
  ];
  for (const c of candidates) {
    try {
      const res = spawnSync(c.cmd, [...c.args, '--version'], { encoding: 'utf8', timeout: 5000 });
      if (res.status === 0) {
        const out = ((res.stdout || '') + ' ' + (res.stderr || '')).trim();
        if (out.includes('Python 3')) {
          return { cmd: c.cmd, args: c.args, versionStr: out };
        }
      }
    } catch (e) {}
  }
  return null;
}

function doctorCommand(cwd, isJson) {
  const checks = [];
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');

  function addCheck(name, status, message, hint = '') {
    checks.push({ name, status, message, hint });
  }

  // 1. Node version
  const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
  if (nodeMajor >= 18) {
    addCheck('Node.js', 'OK', `v${process.versions.node}`);
  } else {
    addCheck('Node.js', 'FAIL', `v${process.versions.node} (requires >= 18)`, 'Upgrade Node.js to version 18 or higher.');
  }

  // 2. Python 3
  const python = findPythonCommand();
  if (python) {
    addCheck('Python 3', 'OK', `${python.cmd} (${python.versionStr})`);
  } else {
    addCheck('Python 3', 'FAIL', 'Python 3 not found in PATH', 'Install Python 3 and add it to your PATH.');
  }

  // 3. PyYAML
  if (python) {
    try {
      const resYaml = spawnSync(python.cmd, [...python.args, '-c', 'import yaml'], { encoding: 'utf8', timeout: 5000 });
      if (resYaml.status === 0) {
        addCheck('PyYAML', 'OK', 'PyYAML is installed');
      } else {
        addCheck('PyYAML', 'FAIL', 'PyYAML module not found', 'Run: pip install pyyaml');
      }
    } catch (e) {
      addCheck('PyYAML', 'FAIL', 'Could not run PyYAML check', 'Run: pip install pyyaml');
    }
  } else {
    addCheck('PyYAML', 'FAIL', 'Cannot verify PyYAML without Python 3', 'Install Python 3 then run: pip install pyyaml');
  }

  // 4. Git
  try {
    const resGit = spawnSync('git', ['--version'], { encoding: 'utf8', timeout: 5000 });
    if (resGit.status === 0) {
      addCheck('Git', 'OK', (resGit.stdout || '').trim());
    } else {
      addCheck('Git', 'FAIL', 'git command returned non-zero', 'Ensure git is working properly.');
    }
  } catch (e) {
    addCheck('Git', 'FAIL', 'git command not found', 'Install git and ensure it is available in your PATH.');
  }

  // 5. Lock file and verify result
  const integrityResult = checkSkillsIntegrity(cwd);
  if (!integrityResult.ok && integrityResult.error === 'NO_LOCK') {
    addCheck('Lock file', 'FAIL', '.agents/build-forge.lock.json not found', 'Run: npx @v1006/build-forge install');
  } else if (!integrityResult.ok && integrityResult.error === 'INVALID_JSON') {
    addCheck('Lock file', 'FAIL', 'Invalid JSON in .agents/build-forge.lock.json', 'Run: npx @v1006/build-forge install --force');
  } else if (!integrityResult.ok) {
    const total = integrityResult.missing.length + integrityResult.modified.length + integrityResult.extra.length;
    const parts = [];
    if (integrityResult.missing.length > 0) parts.push(`${integrityResult.missing.length} missing`);
    if (integrityResult.modified.length > 0) parts.push(`${integrityResult.modified.length} modified`);
    if (integrityResult.extra.length > 0) parts.push(`${integrityResult.extra.length} extra`);
    addCheck('Lock file', 'FAIL', `${total} skill file(s) ${parts.join(', ')}`, 'Run: npx @v1006/build-forge install --force');
  } else {
    const fileCount = Object.keys(integrityResult.currentManifest).length;
    addCheck('Lock file', 'OK', `All skills match lock file (${fileCount} files)`);
  }

  // 6. Profile validity
  const profilePath = path.join(cwd, '.agents', 'project-profile.yaml');
  if (!fs.existsSync(profilePath)) {
    addCheck('Profile', 'WARN', '.agents/project-profile.yaml not found', 'Run project-bootstrap to create .agents/project-profile.yaml');
  } else {
    let schemaVersion = null;
    try {
      const pText = fs.readFileSync(profilePath, 'utf8');
      const m = pText.match(/^schema_version:\s*(\d+)/m);
      if (m) schemaVersion = parseInt(m[1], 10);
    } catch (e) {}

    if (schemaVersion !== null && !SUPPORTED_SCHEMA_VERSIONS.includes(schemaVersion)) {
      addCheck('Profile', 'FAIL', `Unsupported schema_version ${schemaVersion} in profile (supported: ${SUPPORTED_SCHEMA_VERSIONS.join(', ')})`, 'Run: python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py apply --apply');
    } else {
      let valScript = path.join(cwd, '.agents', 'skills', 'project-bootstrap', 'scripts', 'validate_profile.py');
      if (!fs.existsSync(valScript)) {
        valScript = path.join(__dirname, '..', 'skills', 'project-bootstrap', 'scripts', 'validate_profile.py');
      }
      if (python && fs.existsSync(valScript)) {
        try {
          const resVal = spawnSync(python.cmd, [...python.args, valScript, '--profile', profilePath, '--root', cwd], {
            encoding: 'utf8',
            timeout: 10000
          });
          if (resVal.status === 0) {
            addCheck('Profile', 'OK', `.agents/project-profile.yaml is valid (schema_version ${schemaVersion || 2})`);
          } else {
            addCheck('Profile', 'FAIL', 'Profile validation errors found', 'Run: python3 .agents/skills/project-bootstrap/scripts/validate_profile.py --profile .agents/project-profile.yaml --root .');
          }
        } catch (e) {
          addCheck('Profile', 'FAIL', `Could not run profile validator: ${e.message}`, 'Check Python configuration.');
        }
      } else {
        addCheck('Profile', 'OK', '.agents/project-profile.yaml exists');
      }
    }
  }

  // 7. References verify (if any)
  const refsYaml = path.join(cwd, '.agents', 'references.yaml');
  const refsLock = path.join(cwd, '.agents', 'references.lock.json');
  if (!fs.existsSync(refsYaml) && !fs.existsSync(refsLock)) {
    addCheck('References', 'OK', 'No external references configured');
  } else {
    let refsScript = path.join(cwd, '.agents', 'skills', 'extend-pipeline', 'scripts', 'refs.py');
    if (!fs.existsSync(refsScript)) {
      refsScript = path.join(__dirname, '..', 'skills', 'extend-pipeline', 'scripts', 'refs.py');
    }
    if (python && fs.existsSync(refsScript)) {
      try {
        const resRefs = spawnSync(python.cmd, [...python.args, refsScript, 'verify', '--root', cwd], {
          encoding: 'utf8',
          timeout: 10000
        });
        if (resRefs.status === 0) {
          addCheck('References', 'OK', 'All external references verified');
        } else {
          addCheck('References', 'FAIL', 'External references verification failed', 'Run: python3 .agents/skills/extend-pipeline/scripts/refs.py restore');
        }
      } catch (e) {
        addCheck('References', 'FAIL', `Could not verify references: ${e.message}`, 'Check references installation.');
      }
    } else {
      addCheck('References', 'OK', 'External references present');
    }
  }

  // 8. Blueprint stale (if any)
  const bpManifest = path.join(cwd, '.agents', 'blueprints', 'manifest.json');
  const bpDir = path.join(cwd, '.agents', 'blueprints');
  if (!fs.existsSync(bpManifest) && !fs.existsSync(bpDir)) {
    addCheck('Blueprints', 'OK', 'No blueprints configured');
  } else {
    let bpScript = path.join(cwd, '.agents', 'skills', 'project-blueprints', 'scripts', 'blueprint.py');
    if (!fs.existsSync(bpScript)) {
      bpScript = path.join(__dirname, '..', 'skills', 'project-blueprints', 'scripts', 'blueprint.py');
    }
    if (python && fs.existsSync(bpScript)) {
      try {
        const resBp = spawnSync(python.cmd, [...python.args, bpScript, 'stale', '--root', cwd], {
          encoding: 'utf8',
          timeout: 10000
        });
        if (resBp.status === 0 && (!resBp.stdout || resBp.stdout.trim() === '')) {
          addCheck('Blueprints', 'OK', 'Blueprints are up to date');
        } else {
          addCheck('Blueprints', 'WARN', 'Blueprints are stale', 'Run: python3 .agents/skills/project-blueprints/scripts/blueprint.py extract');
        }
      } catch (e) {
        addCheck('Blueprints', 'OK', 'Blueprints present');
      }
    } else {
      addCheck('Blueprints', 'OK', 'Blueprints present');
    }
  }

  // 9. Links and pointer files
  let brokenLinks = [];
  let missingPointers = [];
  for (const agent of AGENTS) {
    if (agent.skillsFolder) {
      const sp = path.join(cwd, agent.skillsFolder);
      let lstat = null;
      try { lstat = fs.lstatSync(sp); } catch (e) {}
      if (lstat && lstat.isSymbolicLink()) {
        try { fs.statSync(sp); } catch (e) { brokenLinks.push(agent.skillsFolder); }
      }
    }
    if (agent.pointerFile) {
      const ptr = path.join(cwd, agent.pointerFile);
      if (!fs.existsSync(ptr)) {
        missingPointers.push(agent.pointerFile);
      }
    }
  }
  if (brokenLinks.length > 0) {
    addCheck('Agent links', 'FAIL', `${brokenLinks.length} broken symlink(s): ${brokenLinks.join(', ')}`, 'Run: npx @v1006/build-forge link');
  } else if (missingPointers.length > 0) {
    addCheck('Agent links', 'WARN', `${missingPointers.length} agent pointer file(s) not created`, 'Run: npx @v1006/build-forge link --agents auto');
  } else {
    addCheck('Agent links', 'OK', 'All agent links and pointer files valid');
  }

  // 10. AGENTS.md exists
  const agentsMd = path.join(cwd, 'AGENTS.md');
  if (fs.existsSync(agentsMd)) {
    addCheck('AGENTS.md', 'OK', 'AGENTS.md present in project root');
  } else {
    addCheck('AGENTS.md', 'WARN', 'AGENTS.md not found in project root', 'Run project-bootstrap or render.py to generate AGENTS.md');
  }

  // 11. Legacy parity status (if a ledger exists)
  const ledgerPath = path.join(cwd, '.agents', 'legacy-parity.md');
  if (!fs.existsSync(ledgerPath)) {
    addCheck('Legacy parity', 'OK', 'No legacy parity ledger found');
  } else {
    let legScript = path.join(cwd, '.agents', 'skills', 'project-bootstrap', 'scripts', 'legacy_import.py');
    if (!fs.existsSync(legScript)) {
      legScript = path.join(__dirname, '..', 'skills', 'project-bootstrap', 'scripts', 'legacy_import.py');
    }
    if (python && fs.existsSync(legScript)) {
      try {
        const resLeg = spawnSync(python.cmd, [...python.args, legScript, 'status', '--root', cwd], {
          encoding: 'utf8',
          timeout: 10000
        });
        if (resLeg.status === 0) {
          addCheck('Legacy parity', 'OK', 'Legacy parity complete (0 pending items)');
        } else {
          addCheck('Legacy parity', 'WARN', 'Legacy parity has pending items', 'Run: python3 .agents/skills/project-bootstrap/scripts/legacy_import.py batch --area <area>');
        }
      } catch (e) {
        addCheck('Legacy parity', 'OK', 'Legacy parity ledger present');
      }
    } else {
      addCheck('Legacy parity', 'OK', 'Legacy parity ledger present');
    }
  }

  // 12. Dual-home skills
  const vendorDir = path.join(cwd, '.agents', 'vendor');
  const collisions = [];
  if (fs.existsSync(vendorDir) && fs.existsSync(targetSkillsDir)) {
    try {
      const vendorFolders = fs.readdirSync(vendorDir).filter(f => {
        try { return fs.statSync(path.join(vendorDir, f)).isDirectory() && !f.startsWith('.'); } catch (e) { return false; }
      });
      for (const vf of vendorFolders) {
        if (fs.existsSync(path.join(targetSkillsDir, vf))) {
          collisions.push(vf);
        }
      }
    } catch (e) {}
  }
  if (fs.existsSync(refsYaml) && fs.existsSync(targetSkillsDir)) {
    try {
      const refsContent = fs.readFileSync(refsYaml, 'utf8');
      const lines = refsContent.split('\n');
      let inRefs = false;
      let curName = null;
      let curAct = 'pipeline-only';
      for (const line of lines) {
        if (line.trim().startsWith('references:')) { inRefs = true; continue; }
        if (!inRefs) continue;
        const nameMatch = line.match(/^\s*-\s*name:\s*([a-zA-Z0-9_-]+)/) || line.match(/^\s*name:\s*([a-zA-Z0-9_-]+)/);
        if (nameMatch) {
          curName = nameMatch[1];
          curAct = 'pipeline-only';
        }
        const actMatch = line.match(/^\s*activation:\s*([a-zA-Z0-9_-]+)/);
        if (actMatch) {
          curAct = actMatch[1];
        }
        if (curName && curAct === 'pipeline-only') {
          if (fs.existsSync(path.join(targetSkillsDir, curName)) && !collisions.includes(curName)) {
            collisions.push(curName);
          }
        }
      }
    } catch (e) {}
  }
  if (collisions.length > 0) {
    addCheck('Dual-home skills', 'WARN', `${collisions.length} dual-homed skill(s) detected: ${collisions.join(', ')}`, 'Run: python3 .agents/skills/extend-pipeline/scripts/refs.py dedupe');
  } else {
    addCheck('Dual-home skills', 'OK', 'No dual-homed skills found');
  }

  // 13. Orphan vendor folders
  const orphans = [];
  if (fs.existsSync(vendorDir)) {
    try {
      const refNames = new Set();
      if (fs.existsSync(refsYaml)) {
        const refsContent = fs.readFileSync(refsYaml, 'utf8');
        const matches = refsContent.matchAll(/name:\s*([a-zA-Z0-9_-]+)/g);
        for (const m of matches) {
          refNames.add(m[1]);
        }
      }
      const vendorFolders = fs.readdirSync(vendorDir).filter(f => {
        try { return fs.statSync(path.join(vendorDir, f)).isDirectory() && !f.startsWith('.'); } catch (e) { return false; }
      });
      for (const vf of vendorFolders) {
        if (!refNames.has(vf)) {
          orphans.push(vf);
        }
      }
    } catch (e) {}
  }
  if (orphans.length > 0) {
    addCheck('Orphan vendor folders', 'WARN', `${orphans.length} orphan folder(s) in .agents/vendor: ${orphans.join(', ')}`, 'Remove unused vendor folder or register it in .agents/references.yaml');
  } else {
    addCheck('Orphan vendor folders', 'OK', 'No orphan vendor folders found');
  }

  // 14. Rule runner version
  const runnerPath = path.join(cwd, '.agents', 'checks', 'run_rule_checks.py');
  if (fs.existsSync(runnerPath)) {
    try {
      const runnerContent = fs.readFileSync(runnerPath, 'utf8');
      const m = runnerContent.match(/RUNNER_VERSION\s*=\s*(\d+)/);
      const runnerVer = m ? parseInt(m[1], 10) : 0;
      if (runnerVer < 1) {
        addCheck('Rule runner', 'WARN', `Project run_rule_checks.py runner v${runnerVer} is older than v1`, 'Refresh .agents/checks/run_rule_checks.py from skills/rules-to-tests/scripts/run_rule_checks.py');
      } else {
        addCheck('Rule runner', 'OK', `run_rule_checks.py runner is up to date (v${runnerVer})`);
      }
    } catch (e) {
      addCheck('Rule runner', 'WARN', 'Could not read runner version from .agents/checks/run_rule_checks.py');
    }
  } else {
    addCheck('Rule runner', 'OK', 'No project rule runner configured');
  }

  // 15. Pending upgrade actions
  const upgradeNotesPath = path.join(__dirname, '..', 'upgrade-notes.json');
  const upgradeStatePath = path.join(cwd, '.agents', 'upgrade-state.json');
  if (fs.existsSync(upgradeNotesPath)) {
    let notes = [];
    try { notes = JSON.parse(fs.readFileSync(upgradeNotesPath, 'utf8')); } catch (e) {}
    let state = { completed: [] };
    if (fs.existsSync(upgradeStatePath)) {
      try { state = JSON.parse(fs.readFileSync(upgradeStatePath, 'utf8')); } catch (e) {}
    }
    const completedSet = new Set(Array.isArray(state.completed) ? state.completed : []);
    const pending = [];
    for (const entry of notes) {
      for (const action of entry.actions || []) {
        if (!completedSet.has(action.id)) {
          pending.push(action);
        }
      }
    }
    if (pending.length > 0) {
      addCheck(
        'Upgrade actions',
        'WARN',
        `${pending.length} pending upgrade action(s): ${pending.map(p => p.id).join(', ')}`,
        'Run pending actions then mark done with: npx @v1006/build-forge upgrade done <id>'
      );
    } else {
      addCheck('Upgrade actions', 'OK', 'All upgrade actions completed');
    }
  }

  // 16. Branch workflow (stale state, merged uncleaned branches, missing default branch)
  if (fs.existsSync(path.join(cwd, '.git'))) {
    // A. Default branch
    let defBranch = 'main';
    if (fs.existsSync(profilePath)) {
      try {
        const pText = fs.readFileSync(profilePath, 'utf8');
        const m = pText.match(/^\s*default_branch:\s*([a-zA-Z0-9_.-]+)/m);
        if (m) {
          defBranch = m[1].trim();
        }
      } catch (e) {}
    }
    const resDefChk = spawnSync('git', ['rev-parse', '--verify', `refs/heads/${defBranch}`], {
      cwd, encoding: 'utf8', timeout: 5000
    });
    if (resDefChk.status !== 0) {
      const resRemChk = spawnSync('git', ['rev-parse', '--verify', `refs/remotes/origin/${defBranch}`], {
        cwd, encoding: 'utf8', timeout: 5000
      });
      if (resRemChk.status !== 0) {
        addCheck(
          'Default branch',
          'WARN',
          `Default branch '${defBranch}' does not exist locally or on remote`,
          'Set git.workflow.default_branch in .agents/project-profile.yaml to your active branch'
        );
      } else {
        addCheck('Default branch', 'OK', `Default branch '${defBranch}' verified on remote`);
      }
    } else {
      addCheck('Default branch', 'OK', `Default branch '${defBranch}' verified`);
    }

    // B. Stale state files
    const bStatePath = path.join(cwd, '.agents', 'work', 'branch-state.json');
    if (fs.existsSync(bStatePath)) {
      let bState = null;
      try { bState = JSON.parse(fs.readFileSync(bStatePath, 'utf8')); } catch (e) {}
      if (!bState || typeof bState !== 'object') {
        addCheck(
          'Branch state',
          'WARN',
          'Corrupted branch state file in .agents/work/branch-state.json',
          'Delete .agents/work/branch-state.json or run branchflow cleanup'
        );
      } else if (bState.branch) {
        const resBranchChk = spawnSync('git', ['rev-parse', '--verify', `refs/heads/${bState.branch}`], {
          cwd, encoding: 'utf8', timeout: 5000
        });
        if (resBranchChk.status !== 0) {
          addCheck(
            'Branch state',
            'WARN',
            `Stale branch state file: branch '${bState.branch}' no longer exists in git`,
            'Run: python3 .agents/skills/feature-delivery/scripts/branchflow.py cleanup or remove .agents/work/branch-state.json'
          );
        } else if (bState.status === 'cleaned' || bState.status === 'abandoned') {
          addCheck(
            'Branch state',
            'WARN',
            `Inactive branch state file (status: ${bState.status})`,
            'Remove .agents/work/branch-state.json'
          );
        } else {
          addCheck('Branch state', 'OK', `Active task branch '${bState.branch}' (${bState.status})`);
        }
      }
    } else {
      addCheck('Branch state', 'OK', 'No active or stale branch state file');
    }

    // C. Merged but uncleaned local branches
    try {
      const resMerged = spawnSync('git', ['branch', '--merged', defBranch], {
        cwd, encoding: 'utf8', timeout: 5000
      });
      if (resMerged.status === 0) {
        const mergedLines = (resMerged.stdout || '').split('\n')
          .map(l => l.replace('*', '').trim())
          .filter(b => b && b !== defBranch && b !== 'main' && b !== 'master' && !b.startsWith('(HEAD'));
        if (mergedLines.length > 0) {
          addCheck(
            'Merged branches',
            'WARN',
            `${mergedLines.length} merged local branch(es) not cleaned up: ${mergedLines.join(', ')}`,
            'Run: git branch -d <branch> or python3 .agents/skills/feature-delivery/scripts/branchflow.py cleanup'
          );
        } else {
          addCheck('Merged branches', 'OK', 'No uncleaned merged branches');
        }
      }
    } catch (e) {}
  }

  const okCount = checks.filter(c => c.status === 'OK').length;
  const warnCount = checks.filter(c => c.status === 'WARN').length;
  const failCount = checks.filter(c => c.status === 'FAIL').length;
  const hasFail = failCount > 0;

  if (isJson) {
    console.log(JSON.stringify({
      status: hasFail ? 'FAIL' : (warnCount > 0 ? 'WARN' : 'OK'),
      checks,
      summary: { ok: okCount, warn: warnCount, fail: failCount }
    }, null, 2));
  } else {
    console.log('Build Forge Doctor\n');
    for (const c of checks) {
      const tag = c.status === 'OK' ? '[OK]  ' : (c.status === 'WARN' ? '[WARN]' : '[FAIL]');
      console.log(`  ${tag} ${c.name}: ${c.message}`);
      if (c.hint && c.status !== 'OK') {
        console.log(`         Hint: ${c.hint}`);
      }
    }
    console.log(`\nResult: ${okCount} passed, ${warnCount} warning(s), ${failCount} failure(s).`);
  }

  if (hasFail) {
    process.exit(1);
  }
}

function compareSemver(v1, v2) {
  const p1 = (v1 || '0.0.0').split('.').map(n => parseInt(n, 10) || 0);
  const p2 = (v2 || '0.0.0').split('.').map(n => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i++) {
    if (p1[i] < p2[i]) return -1;
    if (p1[i] > p2[i]) return 1;
  }
  return 0;
}

function outdatedCommand(cwd, isJson) {
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  let installedVersion = '0.1.0';
  if (fs.existsSync(lockFilePath)) {
    try {
      const lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
      if (lockData._version) {
        installedVersion = lockData._version;
      } else if (lockData.version) {
        installedVersion = lockData.version;
      }
    } catch (e) {}
  } else {
    try {
      const pkgJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
      installedVersion = pkgJson.version || installedVersion;
    } catch (e) {}
  }

  let latestVersion = null;
  try {
    const res = spawnSync('npm', ['view', '@v1006/build-forge', 'version'], {
      encoding: 'utf8',
      timeout: 4000
    });
    if (res.status === 0 && res.stdout) {
      latestVersion = res.stdout.trim();
    }
  } catch (e) {
    latestVersion = null;
  }

  if (!latestVersion) {
    if (isJson) {
      console.log(JSON.stringify({
        installed: installedVersion,
        latest: null,
        offline: true,
        note: 'Offline: skipped version check (network unavailable).'
      }, null, 2));
    } else {
      console.log('Offline: skipped version check (network unavailable).');
      console.log(`Installed version in lock: ${installedVersion}`);
    }
    return;
  }

  const isOutdated = compareSemver(installedVersion, latestVersion) < 0;
  if (isJson) {
    console.log(JSON.stringify({
      installed: installedVersion,
      latest: latestVersion,
      outdated: isOutdated
    }, null, 2));
  } else {
    if (isOutdated) {
      console.log(`@v1006/build-forge is outdated: installed ${installedVersion}, latest ${latestVersion}.`);
      console.log('Run: npx @v1006/build-forge update');
    } else {
      console.log(`@v1006/build-forge is up to date (version ${installedVersion}).`);
    }
  }
}

function updateCommand(cwd, options = {}) {
  const dryRun = !!options.dryRun;
  const adopt = !!options.adopt;
  const keepModified = options.keepModified || new Set();
  const restore = options.restore || new Set();

  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const integrityPath = path.join(__dirname, '..', 'integrity.json');
  const tiersPath = path.join(__dirname, '..', 'tiers.json');
  const upgradeNotesPath = path.join(__dirname, '..', 'upgrade-notes.json');

  let integrity = {};
  if (fs.existsSync(integrityPath)) {
    try { integrity = JSON.parse(fs.readFileSync(integrityPath, 'utf8')); } catch (e) {}
  }
  let tiers = { core: [] };
  if (fs.existsSync(tiersPath)) {
    try { tiers = JSON.parse(fs.readFileSync(tiersPath, 'utf8')); } catch (e) {}
  }
  const coreSkills = new Set(tiers.core || []);

  let pkgVersion = '0.1.0';
  try {
    const pkgJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
    pkgVersion = pkgJson.version || pkgVersion;
  } catch (e) {}

  // Case 1: No lock file
  if (!fs.existsSync(lockFilePath)) {
    if (!adopt) {
      console.error('Update error: Lock file not found at .agents/build-forge.lock.json.');
      console.error('Run npx @v1006/build-forge update --adopt to adopt existing skills.');
      process.exit(1);
    }

    const installedSkills = [];
    if (fs.existsSync(targetSkillsDir)) {
      for (const name of fs.readdirSync(targetSkillsDir)) {
        if (fs.existsSync(path.join(packageSkillsDir, name)) && fs.statSync(path.join(targetSkillsDir, name)).isDirectory()) {
          installedSkills.push(name);
        }
      }
    }

    const matchingSkills = [];
    const differingSkills = [];
    const diffFilesBySkill = {};

    for (const name of installedSkills) {
      const manifest = computeSkillsManifest(targetSkillsDir, new Set([name]));
      const pkgFiles = Object.keys(integrity).filter(k => k.startsWith(`skills/${name}/`));
      let differs = false;
      const diffList = [];

      for (const relFile of pkgFiles) {
        if (!manifest[relFile] || manifest[relFile] !== integrity[relFile]) {
          differs = true;
          diffList.push(relFile);
        }
      }
      for (const relFile of Object.keys(manifest)) {
        if (!integrity[relFile]) {
          differs = true;
          diffList.push(relFile);
        }
      }

      if (differs) {
        differingSkills.push(name);
        diffFilesBySkill[name] = diffList;
      } else {
        matchingSkills.push(name);
      }
    }

    const unresolved = [];
    for (const name of differingSkills) {
      if (!keepModified.has(name) && !restore.has(name) && !restore.has('all')) {
        unresolved.push(name);
      }
    }

    if (unresolved.length > 0 && !dryRun) {
      console.error('Adopt aborted: The following skill(s) differ from the package:');
      for (const name of unresolved) {
        console.error(`  differs: ${name} (${diffFilesBySkill[name].length} file(s) differ)`);
        for (const f of diffFilesBySkill[name].slice(0, 3)) {
          console.error(`    - .agents/${f}`);
        }
      }
      console.error('\nPass --keep-modified <skill> to keep your version, or --restore <skill> (or --restore all) to overwrite with package version.');
      process.exit(1);
    }

    if (dryRun) {
      console.log('DRY RUN: update --adopt plan:');
      console.log(`  Matching skills: ${matchingSkills.join(', ') || 'none'}`);
      console.log(`  Kept modified:   ${Array.from(keepModified).join(', ') || 'none'}`);
      console.log(`  Restoring:       ${restore.has('all') ? 'all differing skills' : (Array.from(restore).join(', ') || 'none')}`);
      console.log(`  Would write:     .agents/build-forge.lock.json (version ${pkgVersion})`);
      if (unresolved.length > 0) {
        console.log('\nBlocked by:');
        for (const name of unresolved) {
          console.log(`  - ${name}: differs from package in ${diffFilesBySkill[name].length} file(s); pass --keep-modified ${name} or --restore ${name}`);
        }
      }
      console.log('\nDRY RUN: No files were changed.');
      process.exit(unresolved.length > 0 ? 1 : 0);
    }

    // Apply restore
    const skillsToRestore = new Set(restore);
    if (skillsToRestore.has('all')) {
      skillsToRestore.delete('all');
      for (const name of differingSkills) {
        if (!keepModified.has(name)) {
          skillsToRestore.add(name);
        }
      }
    }
    if (skillsToRestore.length > 0) {
      const workDir = path.join(cwd, '.agents', 'work');
      fs.mkdirSync(workDir, { recursive: true });
      for (const name of skillsToRestore) {
        const targetSkillDir = path.join(targetSkillsDir, name);
        const pkgSkillDir = path.join(packageSkillsDir, name);
        if (fs.existsSync(targetSkillDir)) {
          const pDiff = generateSkillPatch(pkgSkillDir, targetSkillDir, name);
          if (pDiff) {
            const patchFile = path.join(workDir, `overwritten-${name}.patch`);
            fs.writeFileSync(patchFile, pDiff, 'utf8');
            console.log(`  saved patch: .agents/work/overwritten-${name}.patch`);
          }
        }
        fs.cpSync(pkgSkillDir, targetSkillDir, { recursive: true, force: true });
        console.log(`  restored skill: ${name}`);
      }
    }

    // Install missing core tier skills
    for (const coreSkill of coreSkills) {
      if (!fs.existsSync(path.join(targetSkillsDir, coreSkill))) {
        fs.cpSync(path.join(packageSkillsDir, coreSkill), path.join(targetSkillsDir, coreSkill), { recursive: true, force: true });
        console.log(`  installed missing core skill: ${coreSkill}`);
      }
    }

    // Write lock file from package expected integrity hashes
    const allInstalledPkgSkills = new Set(
      fs.readdirSync(targetSkillsDir).filter(n => fs.existsSync(path.join(packageSkillsDir, n)))
    );
    const newManifest = {};
    for (const skillName of allInstalledPkgSkills) {
      for (const [relFile, hash] of Object.entries(integrity)) {
        if (relFile.startsWith(`skills/${skillName}/`)) {
          newManifest[relFile] = hash;
        }
      }
    }
    newManifest['_version'] = pkgVersion;
    newManifest['_installed'] = Array.from(allInstalledPkgSkills).sort();
    fs.writeFileSync(lockFilePath, JSON.stringify(newManifest, null, 2) + '\n', 'utf8');
    console.log(`Adopt complete: .agents/build-forge.lock.json written with version ${pkgVersion}.`);
    return;
  }

  // Case 2: Lock file exists
  let lockData = {};
  try {
    lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
  } catch (err) {
    console.error('Update error: Invalid JSON in .agents/build-forge.lock.json.');
    process.exit(1);
  }

  const installedVersion = lockData._version || lockData.version || '0.1.0';

  const installedSkills = getInstalledSkills(cwd, lockData);
  const currentManifest = computeSkillsManifest(targetSkillsDir, installedSkills);

  // Check local modifications against lockData for installed skills only
  const modifiedSkills = new Map();
  for (const [relFile, expectedHash] of Object.entries(lockData)) {
    if (relFile.startsWith('_') || relFile === 'version') continue;
    const parts = relFile.split('/');
    if (parts.length >= 2 && parts[0] === 'skills') {
      const skillName = parts[1];
      if (!installedSkills.has(skillName)) continue;
    }
    const curHash = currentManifest[relFile];
    if (!curHash || curHash !== expectedHash) {
      const skillName = relFile.split('/')[1];
      if (!modifiedSkills.has(skillName)) modifiedSkills.set(skillName, []);
      modifiedSkills.get(skillName).push(relFile);
    }
  }

  const unapproved = [];
  for (const [skillName, files] of modifiedSkills.entries()) {
    if (!keepModified.has(skillName) && !restore.has(skillName) && !restore.has('all')) {
      unapproved.push({ skillName, files });
    }
  }

  if (unapproved.length > 0 && !dryRun) {
    console.error('Update aborted: The following pipeline skill(s) have local modifications:');
    for (const { skillName, files } of unapproved) {
      console.error(`  modified skill: ${skillName}`);
      for (const f of files) {
        console.error(`    .agents/${f}`);
      }
    }
    console.error('\nTo keep your local edits, pass --keep-modified <skill>. To discard and overwrite, pass --restore <skill> or run install --force.');
    process.exit(1);
  }

  // Missing core tier skills
  const missingCore = [];
  for (const coreSkill of coreSkills) {
    if (!fs.existsSync(path.join(targetSkillsDir, coreSkill))) {
      missingCore.push(coreSkill);
    }
  }

  // Pipeline skills that differ from integrity.json
  const differingSkills = [];
  if (fs.existsSync(targetSkillsDir)) {
    for (const name of fs.readdirSync(targetSkillsDir)) {
      if (!fs.existsSync(path.join(packageSkillsDir, name))) continue;
      if (keepModified.has(name)) continue;

      if (restore.has(name) || restore.has('all')) {
        differingSkills.push(name);
        continue;
      }

      const pkgFiles = Object.keys(integrity).filter(k => k.startsWith(`skills/${name}/`));
      let differs = false;
      for (const relFile of pkgFiles) {
        if (!currentManifest[relFile] || currentManifest[relFile] !== integrity[relFile]) {
          differs = true;
          break;
        }
      }
      if (!differs) {
        for (const relFile of Object.keys(currentManifest)) {
          if (relFile.startsWith(`skills/${name}/`) && !integrity[relFile]) {
            differs = true;
            break;
          }
        }
      }
      if (differs) {
        differingSkills.push(name);
      }
    }
  }

  // Available non-core skills
  const nonCoreTiers = ['new-app', 'module'];
  const availableNonCore = [];
  for (const tierKey of nonCoreTiers) {
    for (const name of (tiers[tierKey] || [])) {
      if (!fs.existsSync(path.join(targetSkillsDir, name))) {
        availableNonCore.push(name);
      }
    }
  }

  // Upgrade notes check
  let pendingUpgradeActions = [];
  if (fs.existsSync(upgradeNotesPath)) {
    let notes = [];
    try { notes = JSON.parse(fs.readFileSync(upgradeNotesPath, 'utf8')); } catch (e) {}
    const upgradeStatePath = path.join(cwd, '.agents', 'upgrade-state.json');
    let state = { completed: [] };
    if (fs.existsSync(upgradeStatePath)) {
      try { state = JSON.parse(fs.readFileSync(upgradeStatePath, 'utf8')); } catch (e) {}
    }
    const completedSet = new Set(Array.isArray(state.completed) ? state.completed : []);

    for (const entry of notes) {
      for (const action of entry.actions || []) {
        if (!completedSet.has(action.id)) {
          pendingUpgradeActions.push(action);
        }
      }
    }
  }

  if (dryRun) {
    console.log(`DRY RUN: update plan for Build Forge ${pkgVersion}:`);
    if (keepModified.size > 0) {
      console.log(`  Keeping modified skill(s): ${Array.from(keepModified).join(', ')}`);
    }
    if (restore.size > 0) {
      console.log(`  Restoring skill(s): ${Array.from(restore).join(', ')}`);
    }
    if (missingCore.length > 0) {
      console.log(`  Would install missing core skill(s): ${missingCore.join(', ')}`);
    }
    if (differingSkills.length > 0) {
      console.log(`  Would update differing skill(s): ${differingSkills.join(', ')}`);
    }
    if (availableNonCore.length > 0) {
      console.log(`  Available optional skill(s) to add: ${availableNonCore.join(', ')}`);
    }
    if (pendingUpgradeActions.length > 0) {
      console.log(`  Pending upgrade action(s): ${pendingUpgradeActions.map(a => a.id).join(', ')}`);
    }
    if (unapproved.length > 0) {
      console.log('\nBlocked by:');
      for (const { skillName, files } of unapproved) {
        console.log(`  - ${skillName}: has local modifications in ${files.length} file(s); pass --keep-modified ${skillName} to preserve or --restore ${skillName} to overwrite`);
      }
    }
    console.log('\nDRY RUN: No files were changed.');
    process.exit(unapproved.length > 0 ? 1 : 0);
  }

  fs.mkdirSync(targetSkillsDir, { recursive: true });

  // 1. Install missing core tier skills
  for (const coreSkill of missingCore) {
    fs.cpSync(path.join(packageSkillsDir, coreSkill), path.join(targetSkillsDir, coreSkill), { recursive: true, force: true });
    console.log(`  installed missing core skill: ${coreSkill}`);
  }

  // 2. Reinstall differing pipeline skills (saving patch first)
  if (differingSkills.length > 0) {
    const workDir = path.join(cwd, '.agents', 'work');
    fs.mkdirSync(workDir, { recursive: true });
    for (const name of differingSkills) {
      const targetSkillDir = path.join(targetSkillsDir, name);
      const pkgSkillDir = path.join(packageSkillsDir, name);
      pruneObsoleteSkillFiles(pkgSkillDir, targetSkillDir, name, lockData, workDir);
      if (fs.existsSync(targetSkillDir)) {
        const pDiff = generateSkillPatch(pkgSkillDir, targetSkillDir, name, lockData);
        if (pDiff) {
          const patchFile = path.join(workDir, `overwritten-${name}.patch`);
          fs.writeFileSync(patchFile, pDiff, 'utf8');
          console.log(`  saved patch: .agents/work/overwritten-${name}.patch`);
        }
      }
      fs.cpSync(pkgSkillDir, targetSkillDir, { recursive: true, force: true });
      console.log(`  updated skill: ${name}`);
    }
  }

  // 3. Update lockfile: keep package integrity hashes for installed skills
  const allInstalledPkgSkills = new Set(
    fs.readdirSync(targetSkillsDir).filter(n => fs.existsSync(path.join(packageSkillsDir, n)))
  );
  const newManifest = {};
  for (const skillName of allInstalledPkgSkills) {
    for (const [relFile, hash] of Object.entries(integrity)) {
      if (relFile.startsWith(`skills/${skillName}/`)) {
        newManifest[relFile] = hash;
      }
    }
  }
  newManifest['_version'] = pkgVersion;
  newManifest['_installed'] = Array.from(allInstalledPkgSkills).sort();
  fs.writeFileSync(lockFilePath, JSON.stringify(newManifest, null, 2) + '\n', 'utf8');
  console.log(`Build Forge: Updated pipeline skills and lockfile to version ${pkgVersion}.`);

  // 4. List available non-core skills
  if (availableNonCore.length > 0) {
    console.log('\nAvailable optional skills:');
    for (const name of availableNonCore) {
      console.log(`  ${name} (add with: npx @v1006/build-forge add ${name})`);
    }
  }

  // 5. Print pending upgrade actions
  if (pendingUpgradeActions.length > 0) {
    console.log(`\nPending upgrade actions for Build Forge ${pkgVersion}:`);
    for (const action of pendingUpgradeActions) {
      console.log(`  - [${action.id}] ${action.title}`);
      console.log(`    Command: ${action.command}`);
      console.log(`    Mark done: npx @v1006/build-forge upgrade done ${action.id}`);
    }
    console.log('See UPGRADING.md for instructions.');
  }

  // 6. Dual-home collisions check
  const vendorDir = path.join(cwd, '.agents', 'vendor');
  if (fs.existsSync(vendorDir) && fs.existsSync(targetSkillsDir)) {
    try {
      const vendorFolders = fs.readdirSync(vendorDir).filter(f => {
        try { return fs.statSync(path.join(vendorDir, f)).isDirectory() && !f.startsWith('.'); } catch (e) { return false; }
      });
      const collisions = vendorFolders.filter(vf => fs.existsSync(path.join(targetSkillsDir, vf)));
      if (collisions.length > 0) {
        console.log(`\nNote: ${collisions.length} dual-homed skill collision(s) detected: ${collisions.join(', ')}.`);
        console.log('Run python3 .agents/skills/extend-pipeline/scripts/refs.py dedupe to inspect and reconcile.');
      }
    } catch (e) {}
  }

  // 7. Print migrate plan and command to apply it
  const profilePath = path.join(cwd, '.agents', 'project-profile.yaml');
  let migrateScript = path.join(cwd, '.agents', 'skills', 'project-bootstrap', 'scripts', 'migrate_profile.py');
  if (!fs.existsSync(migrateScript)) {
    migrateScript = path.join(packageSkillsDir, 'project-bootstrap', 'scripts', 'migrate_profile.py');
  }

  const python = findPythonCommand();
  if (fs.existsSync(profilePath) && fs.existsSync(migrateScript) && python) {
    try {
      const resPlan = spawnSync(python.cmd, [...python.args, migrateScript, 'plan', '--profile', profilePath, '--root', cwd], {
        encoding: 'utf8',
        timeout: 10000
      });
      if (resPlan.stdout && resPlan.stdout.includes('Migration plan:')) {
        console.log('\n--- Profile Migration Plan ---');
        console.log(resPlan.stdout.trim());
        console.log('\nTo apply this profile migration, run:');
        console.log('  python3 .agents/skills/project-bootstrap/scripts/migrate_profile.py apply --apply');
      } else {
        console.log('\nProject profile is up to date.');
      }
    } catch (e) {
      // Non-fatal
    }
  }
}

function upgradeCommand(cwd, subcmd, actionId) {
  if (subcmd !== 'done' || !actionId) {
    console.error('Usage: npx @v1006/build-forge upgrade done <action-id>');
    process.exit(1);
  }
  const statePath = path.join(cwd, '.agents', 'upgrade-state.json');
  let state = { completed: [] };
  if (fs.existsSync(statePath)) {
    try {
      state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    } catch (e) {
      state = { completed: [] };
    }
  }
  if (!Array.isArray(state.completed)) {
    state.completed = [];
  }
  if (!state.completed.includes(actionId)) {
    state.completed.push(actionId);
  }
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2) + '\n', 'utf8');
  console.log(`Upgrade action '${actionId}' marked as completed in .agents/upgrade-state.json.`);
}

function addCommand(cwd, skillName) {
  if (!skillName) {
    console.error('Usage: npx @v1006/build-forge add <skill-name>');
    process.exit(1);
  }
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const src = path.join(packageSkillsDir, skillName);
  const dest = path.join(targetSkillsDir, skillName);

  if (!fs.existsSync(src) || !fs.statSync(src).isDirectory()) {
    console.error(`Skill '${skillName}' not found in package.`);
    process.exit(1);
  }
  if (fs.existsSync(dest)) {
    console.log(`Skill '${skillName}' is already installed at .agents/skills/${skillName}.`);
    return;
  }
  fs.mkdirSync(dest, { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
  console.log(`Added skill '${skillName}' to .agents/skills/${skillName}.`);

  if (fs.existsSync(lockFilePath)) {
    try {
      const lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
      const skillManifest = computeSkillsManifest(targetSkillsDir, new Set([skillName]));
      for (const [k, v] of Object.entries(skillManifest)) {
        lockData[k] = v;
      }
      const installedSet = getInstalledSkills(cwd, lockData);
      installedSet.add(skillName);
      lockData._installed = Array.from(installedSet).sort();
      fs.writeFileSync(lockFilePath, JSON.stringify(lockData, null, 2) + '\n', 'utf8');
      console.log(`Updated .agents/build-forge.lock.json with '${skillName}'.`);
    } catch (e) {}
  }
}

function removeCommand(cwd, skillName, options = {}) {
  if (!skillName) {
    console.error('Usage: npx @v1006/build-forge remove <skill-name> [--force]');
    process.exit(1);
  }
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const skillDir = path.join(targetSkillsDir, skillName);
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const tiersPath = path.join(__dirname, '..', 'tiers.json');

  let tiers = { core: [] };
  if (fs.existsSync(tiersPath)) {
    try { tiers = JSON.parse(fs.readFileSync(tiersPath, 'utf8')); } catch (e) {}
  }
  const coreSkills = new Set(tiers.core || []);

  let lockData = null;
  if (fs.existsSync(lockFilePath)) {
    try {
      lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
    } catch (e) {}
  }

  const installedSkills = getInstalledSkills(cwd, lockData);
  if (!installedSkills.has(skillName) && !fs.existsSync(skillDir)) {
    console.error(`Skill '${skillName}' is not installed.`);
    process.exit(1);
  }

  if (coreSkills.has(skillName) && !options.force) {
    console.error(`Cannot remove core skill '${skillName}' without --force.`);
    process.exit(1);
  }

  if (fs.existsSync(skillDir)) {
    fs.rmSync(skillDir, { recursive: true, force: true });
  }

  if (lockData) {
    const prefix = `skills/${skillName}/`;
    for (const key of Object.keys(lockData)) {
      if (key.startsWith(prefix)) {
        delete lockData[key];
      }
    }
    installedSkills.delete(skillName);
    lockData._installed = Array.from(installedSkills).sort();
    fs.writeFileSync(lockFilePath, JSON.stringify(lockData, null, 2) + '\n', 'utf8');
  }

  console.log(`Removed skill '${skillName}'.`);
}

function listCommand(cwd) {
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const tiersPath = path.join(__dirname, '..', 'tiers.json');
  let tiers = { core: [], 'new-app': [], module: [] };
  if (fs.existsSync(tiersPath)) {
    try { tiers = JSON.parse(fs.readFileSync(tiersPath, 'utf8')); } catch (e) {}
  }

  console.log('Build Forge Skills:\n');
  for (const [tier, skills] of Object.entries(tiers)) {
    console.log(`${tier.toUpperCase()}:`);
    for (const name of skills) {
      const installed = fs.existsSync(path.join(targetSkillsDir, name));
      if (installed) {
        console.log(`  [installed]     ${name}`);
      } else {
        console.log(`  [not installed] ${name} (add with: npx @v1006/build-forge add ${name})`);
      }
    }
    console.log('');
  }
}

function main() {
  const args = process.argv.slice(2);
  const { command, positional, force, all, agentsArg, json, dryRun, adopt, yes, keepModified, restore, patch, noGitignore } = parseArgs(args);
  const cwd = process.cwd();

  if (command === 'install') {
    installCommand(cwd, { force, all, agentsArg, noGitignore });
  } else if (command === 'link') {
    linkCommand(cwd, agentsArg);
  } else if (command === 'unlink') {
    unlinkCommand(cwd, agentsArg);
  } else if (command === 'verify') {
    verifyCommand(cwd);
  } else if (command === 'status') {
    statusCommand(cwd);
  } else if (command === 'diff') {
    diffCommand(cwd, { patch });
  } else if (command === 'doctor') {
    doctorCommand(cwd, json);
  } else if (command === 'outdated') {
    outdatedCommand(cwd, json);
  } else if (command === 'update') {
    updateCommand(cwd, { dryRun, adopt, keepModified, restore });
  } else if (command === 'upgrade') {
    const subcmd = positional[1];
    const actionId = positional[2];
    upgradeCommand(cwd, subcmd, actionId);
  } else if (command === 'add') {
    const skillName = positional[1];
    addCommand(cwd, skillName);
  } else if (command === 'remove') {
    const skillName = positional[1];
    removeCommand(cwd, skillName, { force });
  } else if (command === 'list') {
    listCommand(cwd);
  } else if (command === 'help') {
    console.log('Build Forge CLI');
    console.log('Usage: npx @v1006/build-forge <command> [options]\n');
    console.log('Commands:');
    console.log('  install [--all] [--force] [--agents <ids|auto|all>] [--no-gitignore]');
    console.log('  link [--agents <ids|auto|all>]');
    console.log('  unlink [--agents <ids|auto|all>]');
    console.log('  verify');
    console.log('  status');
    console.log('  diff [--patch]');
    console.log('  doctor [--json]');
    console.log('  outdated [--json]');
    console.log('  update [--dry-run] [--adopt] [--keep-modified <skill>] [--restore <skill>]');
    console.log('  upgrade done <action-id>');
    console.log('  add <skill-name>');
    console.log('  remove <skill-name> [--force]');
    console.log('  list');
    console.log('  help, --help, -h');
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  AGENTS,
  POINTER_CONTENT,
  parseArgs,
  compareSemver,
  installCommand,
  linkCommand,
  unlinkCommand,
  verifyCommand,
  statusCommand,
  diffCommand,
  doctorCommand,
  outdatedCommand,
  updateCommand,
  upgradeCommand,
  addCommand,
  removeCommand,
  listCommand
};
