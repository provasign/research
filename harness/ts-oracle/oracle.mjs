/**
 * Change-impact oracle for a TypeScript method signature change.
 *
 * The TS sibling of java-oracle/Oracle.java: given Type#method, emits every
 * site that must change — the declaration, every implementation/override
 * (compiler-resolved via the language service, NOT name matching), and every
 * call site that binds to a family member, attributed to its enclosing
 * method/function. Ground truth is production sources only (src/).
 *
 * Usage:
 *   node oracle.mjs --project <tsconfig.json> --repo <root> \
 *        --target 'QueryRunner#addColumn' --out out.json
 *   node oracle.mjs --project <tsconfig.json> --repo <root> --index idx.json
 *     (line->name index for rescore_java.py, same JSON shape as the Spoon one)
 */
import { Project, Node } from "ts-morph";
import { writeFileSync } from "node:fs";
import path from "node:path";

const args = {};
for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i].startsWith("--")) args[process.argv[i].slice(2)] = process.argv[++i];
}
const need = (k) => { if (!args[k]) { console.error(`missing --${k}`); process.exit(1); } return args[k]; };

const repo = path.resolve(need("repo"));
const project = new Project({ tsConfigFilePath: need("project") });
const rel = (fp) => path.relative(repo, fp);
const inSrc = (fp) => {
    const r = rel(fp);
    return !r.startsWith("..") && !r.startsWith("node_modules") &&
        !r.includes("/test/") && !r.startsWith("test/") &&
        !/\.(spec|test)\.ts$/.test(r);
};

/** Name of the enclosing method/function/class-member for a node. */
function enclosingSite(node) {
    let cur = node;
    while (cur) {
        if (Node.isMethodDeclaration(cur) || Node.isMethodSignature(cur) ||
            Node.isFunctionDeclaration(cur) || Node.isGetAccessorDeclaration(cur) ||
            Node.isSetAccessorDeclaration(cur)) {
            const n = cur.getName();
            if (n) return n;
        }
        if (Node.isConstructorDeclaration(cur)) {
            const cls = cur.getParent();
            return (Node.isClassDeclaration(cls) && cls.getName()) || "constructor";
        }
        // Class fields (arrow-function members) are terminal — the method-like
        // unit. Variable declarations inside bodies are NOT: keep climbing to
        // the enclosing method, matching the Java oracle's attribution.
        if (Node.isPropertyDeclaration(cur)) {
            const n = cur.getName();
            if (n) return n;
        }
        cur = cur.getParent();
    }
    return "<module>";
}

// ---- index mode: relpath -> [[startLine, endLine, name], ...] --------------
if (args.index) {
    const idx = {};
    for (const sf of project.getSourceFiles()) {
        if (!inSrc(sf.getFilePath())) continue;
        const spans = [];
        sf.forEachDescendant((n) => {
            if (Node.isMethodDeclaration(n) || Node.isFunctionDeclaration(n) ||
                Node.isConstructorDeclaration(n) ||
                Node.isGetAccessorDeclaration(n) || Node.isSetAccessorDeclaration(n)) {
                const name = Node.isConstructorDeclaration(n)
                    ? (n.getParent()?.getName?.() ?? "constructor")
                    : n.getName();
                if (name) spans.push([n.getStartLineNumber(), n.getEndLineNumber(), name]);
            }
        });
        if (spans.length) idx[rel(sf.getFilePath())] = spans;
    }
    writeFileSync(args.index, JSON.stringify(idx));
    console.log(`[index] files=${Object.keys(idx).length} -> ${args.index}`);
    process.exit(0);
}

// ---- change-impact mode -----------------------------------------------------
const target = need("target");
const [typeName, methodName] = target.split("#");
if (!methodName) { console.error("--target must be Type#method"); process.exit(1); }

// 1. Declaration: the named interface/class member.
let decl = null;
for (const sf of project.getSourceFiles()) {
    if (!inSrc(sf.getFilePath())) continue;
    for (const t of [...sf.getInterfaces(), ...sf.getClasses()]) {
        if (t.getName() !== typeName) continue;
        const m = t.getMember?.(methodName) ?? t.getMethod?.(methodName);
        if (m) decl = m;
    }
}
if (!decl) { console.error(`target ${target} not found in project sources`); process.exit(1); }

const ls = project.getLanguageService();
const familySites = new Set();
const familyNodes = [decl];
familySites.add(`${rel(decl.getSourceFile().getFilePath())}:${methodName}`);

// 2. Family: compiler-resolved implementations of the member.
for (const impl of ls.getImplementations(decl.getNameNode() ?? decl)) {
    const node = impl.getNode();
    const fp = impl.getSourceFile().getFilePath();
    if (!inSrc(fp)) continue;
    familySites.add(`${rel(fp)}:${methodName}`);
    familyNodes.push(node);
}

// 3. Callers: references to the declaration or any family member that occur
// in call position, attributed to the enclosing method/function.
const callerSites = new Set();
const seenRefPos = new Set();
for (const fam of familyNodes) {
    const nameNode = fam.getNameNode?.() ?? fam;
    let refs;
    try { refs = ls.findReferencesAsNodes(nameNode); } catch { continue; }
    for (const ref of refs) {
        const fp = ref.getSourceFile().getFilePath();
        if (!inSrc(fp)) continue;
        const key = fp + ":" + ref.getStart();
        if (seenRefPos.has(key)) continue;
        seenRefPos.add(key);
        // Call position: obj.method(...) or method(...)
        const parent = ref.getParent();
        let isCall = false;
        if (Node.isPropertyAccessExpression(parent)) {
            const gp = parent.getParent();
            isCall = Node.isCallExpression(gp) && gp.getExpression() === parent;
        } else if (Node.isCallExpression(parent)) {
            isCall = parent.getExpression() === ref;
        }
        if (!isCall) continue;
        const site = `${rel(fp)}:${enclosingSite(ref)}`;
        // A family member calling a sibling is still a caller site only if the
        // enclosing method is not itself in the family for the same file:name.
        if (!familySites.has(site)) callerSites.add(site);
    }
}

const gt = [...new Set([...familySites, ...callerSites])].sort();
const out = {
    target,
    family: [...familySites].sort(),
    callers: [...callerSites].sort(),
    ground_truth: gt,
    stats: { family: familySites.size, resolved_call_hits: callerSites.size, gt_sites: gt.length },
};
writeFileSync(need("out"), JSON.stringify(out, null, 2) + "\n");
console.log(JSON.stringify(out.stats));
