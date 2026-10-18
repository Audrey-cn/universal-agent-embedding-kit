import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { posix } from 'node:path'
import test from 'node:test'

const root = new URL('../', import.meta.url)
const manifest = JSON.parse(readFileSync(new URL('SOURCE_MANIFEST.json', root), 'utf8'))

test('every recovered file matches its recorded original SHA-256', () => {
  assert.equal(manifest.source_commit, 'cf452607d917a895b8428758cafcb172a1a5ce6c')
  assert.equal(manifest.files.length, 7)
  for (const file of manifest.files) {
    const bytes = readFileSync(new URL(file.path, root))
    assert.equal(createHash('sha256').update(bytes).digest('hex'), file.sha256, file.path)
    assert.equal(file.source_path, `BaiLongma/${file.path}`)
  }
  assert.ok(readFileSync(new URL('LICENSE', root), 'utf8').includes(manifest.source_copyright))
})

test('the recovered static import closure contains only included modules and Node built-ins', () => {
  const included = new Set(manifest.files.map(file => file.path))
  const edges = []
  for (const file of manifest.files.filter(file => file.path.endsWith('.js'))) {
    const source = readFileSync(new URL(file.path, root), 'utf8')
    for (const [, specifier] of source.matchAll(/\bfrom\s+['"]([^'"]+)['"]/g)) {
      if (specifier.startsWith('node:')) continue
      assert.ok(specifier.startsWith('.'), `${file.path}: external import ${specifier}`)
      const resolved = posix.normalize(posix.join(posix.dirname(file.path), specifier))
      assert.ok(included.has(resolved), `${file.path}: missing ${resolved}`)
      edges.push(`${file.path} -> ${resolved}`)
    }
    assert.equal(/\b(?:import\s*\(|require\s*\()/.test(source), false, file.path)
  }
  assert.deepEqual(edges.sort(), [
    'src/memory/threads.js -> src/memory/keywords.js',
    'src/memory/threads.js -> src/privacy/write-policy.js',
    'src/test-background-budget.js -> src/runtime/background-budget.js',
  ])
  const pkg = JSON.parse(readFileSync(new URL('package.json', root), 'utf8'))
  assert.equal(pkg.type, 'module')
  assert.equal(pkg.private, true)
  assert.deepEqual(pkg.dependencies || {}, {})
})
