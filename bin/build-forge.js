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
    if (!entry.isDirectory()) continue;
    if (allowedSkillNames && !allowedSkillNames.has(entry.name)) continue;
    walk(path.join(skillsDir, entry.name), path.join('skills', entry.name));
  }
  return manifest;
}

function parseArgs(args) {
  let command = 'install';
  const positional = [];
  let force = false;
  let agentsArg = null;
  let json = false;

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--force') {
      force = true;
    } else if (a === '--json') {
      json = true;
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
    if (['install', 'link', 'unlink', 'verify', 'status', 'diff', 'doctor', 'outdated', 'update', 'help'].includes(first)) {
      command = first;
    }
  }

  return { command, force, agentsArg, json };
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

  // Write lockfile scoped strictly to package pipeline skills
  const packageSkills = new Set(
    fs.readdirSync(packageSkillsDir).filter(name => fs.statSync(path.join(packageSkillsDir, name)).isDirectory())
  );
  const manifest = computeSkillsManifest(targetSkillsDir, packageSkills);
  let pkgVersion = '0.1.0';
  try {
    const pkgJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
    pkgVersion = pkgJson.version || pkgVersion;
  } catch (e) {}
  manifest['_version'] = pkgVersion;
  fs.writeFileSync(lockFilePath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');

  console.log(`Build Forge: ${added.length} skill(s) installed in .agents/skills`);
  for (const n of added) console.log(`  added  ${n}`);
  for (const n of kept) console.log(`  kept   ${n} (exists, use --force to overwrite)`);
  console.log('  lock   .agents/build-forge.lock.json written');

  // Ensure transient work and vendor directories are ignored if .gitignore exists
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
  // Scope manifest check to core package skills or skills tracked in lockData
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const allowedSkills = new Set();
  if (fs.existsSync(packageSkillsDir)) {
    for (const name of fs.readdirSync(packageSkillsDir)) {
      if (fs.statSync(path.join(packageSkillsDir, name)).isDirectory()) {
        allowedSkills.add(name);
      }
    }
  }
  for (const key of Object.keys(lockData)) {
    const parts = key.split('/');
    if (parts.length >= 2 && parts[0] === 'skills') {
      allowedSkills.add(parts[1]);
    }
  }
  const currentManifest = computeSkillsManifest(targetSkillsDir, allowedSkills);
  for (const [relFile, expectedHash] of Object.entries(lockData)) {
    if (relFile.startsWith('_') || relFile === 'version') continue;
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
    if (relFile.startsWith('_') || relFile === 'version') continue;
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

function diffCommand(cwd) {
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

  let diffs = 0;
  for (const [relFile, pkgHash] of Object.entries(pkgManifest)) {
    const curHash = currentManifest[relFile];
    if (!curHash) {
      console.log(`  missing in project: .agents/${relFile}`);
      diffs++;
    } else if (curHash !== pkgHash) {
      console.log(`  modified in project: .agents/${relFile}`);
      diffs++;
    }
  }

  for (const relFile of Object.keys(currentManifest)) {
    if (!pkgManifest[relFile]) {
      console.log(`  extra in project skill: .agents/${relFile}`);
      diffs++;
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
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');
  const targetSkillsDir = path.resolve(cwd, '.agents', 'skills');
  if (!fs.existsSync(lockFilePath)) {
    addCheck('Lock file', 'FAIL', '.agents/build-forge.lock.json not found', 'Run: npx @v1006/build-forge install');
  } else {
    let lockData = null;
    try {
      lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
    } catch (e) {
      lockData = null;
    }
    if (!lockData || typeof lockData !== 'object') {
      addCheck('Lock file', 'FAIL', 'Invalid JSON in .agents/build-forge.lock.json', 'Run: npx @v1006/build-forge install --force');
    } else {
      const packageSkillsDir = path.join(__dirname, '..', 'skills');
      const allowedSkills = new Set();
      if (fs.existsSync(packageSkillsDir)) {
        for (const name of fs.readdirSync(packageSkillsDir)) {
          if (fs.statSync(path.join(packageSkillsDir, name)).isDirectory()) {
            allowedSkills.add(name);
          }
        }
      }
      for (const key of Object.keys(lockData)) {
        const parts = key.split('/');
        if (parts.length >= 2 && parts[0] === 'skills') {
          allowedSkills.add(parts[1]);
        }
      }
      const currentManifest = computeSkillsManifest(targetSkillsDir, allowedSkills);
      let diffCount = 0;
      for (const [relFile, expectedHash] of Object.entries(lockData)) {
        if (relFile.startsWith('_') || relFile === 'version') continue;
        const curHash = currentManifest[relFile];
        if (!curHash || curHash !== expectedHash) {
          diffCount++;
        }
      }
      if (diffCount > 0) {
        addCheck('Lock file', 'FAIL', `${diffCount} skill file(s) modified or missing`, 'Run: npx @v1006/build-forge install --force');
      } else {
        addCheck('Lock file', 'OK', `All skills match lock file (${Object.keys(lockData).length} files)`);
      }
    }
  }

  // 6. Profile validity
  const profilePath = path.join(cwd, '.agents', 'project-profile.yaml');
  if (!fs.existsSync(profilePath)) {
    addCheck('Profile', 'WARN', '.agents/project-profile.yaml not found', 'Run project-bootstrap to create .agents/project-profile.yaml');
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
          addCheck('Profile', 'OK', '.agents/project-profile.yaml is valid');
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

function updateCommand(cwd) {
  const packageSkillsDir = path.join(__dirname, '..', 'skills');
  const targetSkillsDir = path.join(cwd, '.agents', 'skills');
  const lockFilePath = path.join(cwd, '.agents', 'build-forge.lock.json');

  if (!fs.existsSync(lockFilePath)) {
    console.error('Update error: Lock file not found at .agents/build-forge.lock.json. Run install first.');
    process.exit(1);
  }

  let lockData = {};
  try {
    lockData = JSON.parse(fs.readFileSync(lockFilePath, 'utf8'));
  } catch (err) {
    console.error('Update error: Invalid JSON in .agents/build-forge.lock.json.');
    process.exit(1);
  }

  // 1. Verify pipeline skills first
  const allowedSkills = new Set();
  if (fs.existsSync(packageSkillsDir)) {
    for (const name of fs.readdirSync(packageSkillsDir)) {
      if (fs.statSync(path.join(packageSkillsDir, name)).isDirectory()) {
        allowedSkills.add(name);
      }
    }
  }
  for (const key of Object.keys(lockData)) {
    const parts = key.split('/');
    if (parts.length >= 2 && parts[0] === 'skills') {
      allowedSkills.add(parts[1]);
    }
  }

  const currentManifest = computeSkillsManifest(targetSkillsDir, allowedSkills);
  const modified = [];
  for (const [relFile, expectedHash] of Object.entries(lockData)) {
    if (relFile.startsWith('_') || relFile === 'version') continue;
    const curHash = currentManifest[relFile];
    if (curHash && curHash !== expectedHash) {
      modified.push(`.agents/${relFile}`);
    }
  }

  if (modified.length > 0) {
    console.error('Update aborted: The following pipeline skill(s) have local modifications:');
    for (const f of modified) {
      console.error(`  modified  ${f}`);
    }
    console.error('\nRevert or stash your changes before updating.');
    process.exit(1);
  }

  // 2. Install --force for pipeline skills only
  fs.mkdirSync(targetSkillsDir, { recursive: true });
  const updatedSkills = [];
  for (const name of fs.readdirSync(packageSkillsDir)) {
    const from = path.join(packageSkillsDir, name);
    if (!fs.statSync(from).isDirectory()) continue;
    const to = path.join(targetSkillsDir, name);
    fs.cpSync(from, to, { recursive: true, force: true });
    updatedSkills.push(name);
  }

  // Update lockfile
  const newManifest = computeSkillsManifest(targetSkillsDir, allowedSkills);
  let pkgVersion = '0.1.0';
  try {
    const pkgJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
    pkgVersion = pkgJson.version || pkgVersion;
  } catch (e) {}
  newManifest['_version'] = pkgVersion;
  fs.writeFileSync(lockFilePath, JSON.stringify(newManifest, null, 2) + '\n', 'utf8');

  console.log(`Build Forge: Updated ${updatedSkills.length} pipeline skill(s) in .agents/skills.`);

  // Check for dual-homed collisions
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

  // 3. Print migrate plan and command to apply it
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

function main() {
  const args = process.argv.slice(2);
  const { command, force, agentsArg, json } = parseArgs(args);
  const cwd = process.cwd();

  if (command === 'install') {
    installCommand(cwd, force, agentsArg);
  } else if (command === 'link') {
    linkCommand(cwd, agentsArg);
  } else if (command === 'unlink') {
    unlinkCommand(cwd, agentsArg);
  } else if (command === 'verify') {
    verifyCommand(cwd);
  } else if (command === 'status') {
    statusCommand(cwd);
  } else if (command === 'diff') {
    diffCommand(cwd);
  } else if (command === 'doctor') {
    doctorCommand(cwd, json);
  } else if (command === 'outdated') {
    outdatedCommand(cwd, json);
  } else if (command === 'update') {
    updateCommand(cwd);
  } else if (command === 'help') {
    console.log('Build Forge CLI');
    console.log('Commands:');
    console.log('  install [--force] [--agents <ids|auto|all>]');
    console.log('  link [--agents <ids|auto|all>]');
    console.log('  unlink [--agents <ids|auto|all>]');
    console.log('  verify');
    console.log('  status');
    console.log('  diff');
    console.log('  doctor [--json]');
    console.log('  outdated [--json]');
    console.log('  update');
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
  updateCommand
};
