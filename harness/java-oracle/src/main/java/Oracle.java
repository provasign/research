import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.code.CtInvocation;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.visitor.filter.TypeFilter;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

/**
 * Change-impact oracle for a Java method *signature* change.
 *
 * Given a target method (declaring-type FQN + name, optionally a parameter-type
 * arity/signature), emits every site that MUST change if that method's signature
 * changes:
 *   1. the declaration + every override/implementation across the type hierarchy
 *      (the "override family"), and
 *   2. every call site that statically resolves to a family member, attributed
 *      to its enclosing method/constructor.
 *
 * Resolution is Spoon's (full source + dependency classpath), NOT name matching:
 * a call to an unrelated same-named method on a different type is NOT included.
 * This is the discipline the bare-name oracle lacked (which polluted the
 * commons-lang tasks). Unresolvable same-name invocations are counted and
 * reported for audit, never silently added.
 *
 * Output: JSON {target, family[], callers[], ground_truth[], stats{}} where each
 * site is "<repo-relative-path>:<bareMethodName>" (the harness Site format).
 */
public final class Oracle {

    public static void main(String[] args) throws Exception {
        Map<String, String> a = parseArgsRaw(args);
        if (a.containsKey("index")) { indexMode(a); return; }
        requireArgs(a, "src", "repo", "target", "out");
        List<String> srcs = Arrays.asList(a.get("src").split(","));
        Path repo = Paths.get(a.get("repo")).toAbsolutePath().normalize();
        String target = a.get("target");          // "a.b.C#method" or "a.b.C#method(int,String)"
        Path out = Paths.get(a.get("out"));

        String[] tparts = target.split("#", 2);
        if (tparts.length != 2)
            throw new IllegalArgumentException("--target must be FQN#method[(params)]");
        String targetType = tparts[0];
        String mspec = tparts[1];
        String targetName = mspec.contains("(") ? mspec.substring(0, mspec.indexOf('(')) : mspec;
        // optional explicit param-type list to disambiguate overloads
        List<String> wantParams = null;
        if (mspec.contains("(")) {
            String inside = mspec.substring(mspec.indexOf('(') + 1, mspec.lastIndexOf(')')).trim();
            wantParams = inside.isEmpty() ? Collections.emptyList()
                    : Arrays.asList(inside.split("\\s*,\\s*"));
        }

        Launcher l = new Launcher();
        for (String s : srcs) l.addInputResource(s);
        l.getEnvironment().setNoClasspath(true);          // resilient to unresolved externals
        l.getEnvironment().setComplianceLevel(17);
        if (a.containsKey("cp")) {
            String cp = new String(Files.readAllBytes(Paths.get(a.get("cp")))).trim();
            if (!cp.isEmpty()) l.getEnvironment().setSourceClasspath(cp.split(":"));
        }
        CtModel model = l.buildModel();

        List<CtMethod<?>> allMethods = new ArrayList<>(model.getElements(new TypeFilter<>(CtMethod.class)));

        // --- find the target method(s) (overloads collapse unless params given) ---
        List<CtMethod<?>> targets = new ArrayList<>();
        for (CtMethod<?> m : allMethods) {
            CtType<?> dt = m.getDeclaringType();
            if (dt == null || !targetType.equals(dt.getQualifiedName())) continue;
            if (!targetName.equals(m.getSimpleName())) continue;
            if (wantParams != null && !paramTypesMatch(m, wantParams)) continue;
            targets.add(m);
        }
        if (targets.isEmpty())
            throw new IllegalStateException("target method not found in sources: " + target);

        // --- override family: roots (top definitions) + everything overriding a root ---
        Set<CtMethod<?>> roots = new LinkedHashSet<>();
        for (CtMethod<?> t : targets) {
            Collection<CtMethod<?>> tops = t.getTopDefinitions();
            if (tops == null || tops.isEmpty()) roots.add(t);
            else roots.addAll(tops);
        }
        // --- external-override detection: a root declared outside project sources.
        // If the target overrides a method of an external type (JDK or dependency),
        // a "signature change" task is ill-posed (the external contract can't change)
        // and the family/caller closure below is a virtual-dispatch closure through
        // that external interface, not a must-change set. Surface it for audit;
        // make_java_task.py rejects such targets.
        TreeSet<String> externalRoots = new TreeSet<>();
        for (CtMethod<?> r : roots) {
            CtType<?> dt = r.getDeclaringType();
            boolean external = dt == null || dt.isShadow()
                    || dt.getPosition() == null || !dt.getPosition().isValidPosition();
            if (external)
                externalRoots.add((dt == null ? "?" : dt.getQualifiedName())
                        + "#" + r.getSimpleName());
        }

        Set<String> familyKeys = new LinkedHashSet<>();   // declFQN#signature
        Set<CtMethod<?>> family = new LinkedHashSet<>(targets);
        family.addAll(roots);
        for (CtMethod<?> m : allMethods) {
            if (family.contains(m)) continue;
            for (CtMethod<?> r : roots) {
                try {
                    if (m.isOverriding(r)) { family.add(m); break; }
                } catch (Exception ignore) { /* unresolved super; skip */ }
            }
        }
        for (CtMethod<?> m : family) familyKeys.add(key(m));

        // --- family sites (declarations/overrides themselves must change) ---
        TreeSet<String> familySites = new TreeSet<>();
        for (CtMethod<?> m : family) {
            String site = siteOf(m, repo);
            if (site != null) familySites.add(site);
        }

        // --- caller sites: invocations resolving into the family ---
        TreeSet<String> callerSites = new TreeSet<>();
        int unresolvedSameName = 0, resolvedHits = 0;
        for (CtInvocation<?> inv : model.getElements(new TypeFilter<>(CtInvocation.class))) {
            if (inv.getExecutable() == null) continue;
            if (!targetName.equals(inv.getExecutable().getSimpleName())) continue; // cheap pre-filter
            CtExecutable<?> decl = null;
            try { decl = inv.getExecutable().getExecutableDeclaration(); } catch (Exception ignore) {}
            if (!(decl instanceof CtMethod)) { unresolvedSameName++; continue; }
            if (!familyKeys.contains(key((CtMethod<?>) decl))) continue;          // resolves elsewhere -> exclude
            resolvedHits++;
            String site = enclosingSite(inv, repo);
            if (site != null) callerSites.add(site);
        }

        TreeSet<String> gt = new TreeSet<>();
        gt.addAll(familySites);
        gt.addAll(callerSites);

        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"target\": ").append(quote(target)).append(",\n");
        sb.append("  \"overrides_external\": ").append(jsonArr(externalRoots)).append(",\n");
        sb.append("  \"family\": ").append(jsonArr(familySites)).append(",\n");
        sb.append("  \"callers\": ").append(jsonArr(callerSites)).append(",\n");
        sb.append("  \"ground_truth\": ").append(jsonArr(gt)).append(",\n");
        sb.append("  \"stats\": {")
          .append("\"family\": ").append(family.size())
          .append(", \"resolved_call_hits\": ").append(resolvedHits)
          .append(", \"unresolved_samename_calls\": ").append(unresolvedSameName)
          .append(", \"gt_sites\": ").append(gt.size())
          .append("}\n");
        sb.append("}\n");
        Files.write(out, sb.toString().getBytes());
        System.out.println(sb);
    }

    private static boolean paramTypesMatch(CtMethod<?> m, List<String> want) {
        if (m.getParameters().size() != want.size()) return false;
        for (int i = 0; i < want.size(); i++) {
            String have = m.getParameters().get(i).getType().getSimpleName();
            String w = want.get(i);
            String ws = w.contains(".") ? w.substring(w.lastIndexOf('.') + 1) : w;
            if (!ws.equals(have)) return false;
        }
        return true;
    }

    private static String key(CtMethod<?> m) {
        CtType<?> dt = m.getDeclaringType();
        String fqn = dt == null ? "?" : dt.getQualifiedName();
        return fqn + "#" + m.getSignature();
    }

    /** "<relpath>:<bareName>" for a method declaration. */
    private static String siteOf(CtMethod<?> m, Path repo) {
        SourcePosition p = m.getPosition();
        if (p == null || !p.isValidPosition() || p.getFile() == null) return null;
        return rel(repo, p.getFile().toPath()) + ":" + m.getSimpleName();
    }

    /** Attribute an invocation to its enclosing method/constructor. */
    private static String enclosingSite(CtInvocation<?> inv, Path repo) {
        CtExecutable<?> enc = inv.getParent(CtExecutable.class);
        SourcePosition p = inv.getPosition();
        Path file = (p != null && p.isValidPosition() && p.getFile() != null) ? p.getFile().toPath() : null;
        String name = null;
        while (enc != null) {
            if (enc instanceof CtMethod) { name = ((CtMethod<?>) enc).getSimpleName(); break; }
            if (enc instanceof CtConstructor) {
                CtType<?> dt = ((CtConstructor<?>) enc).getDeclaringType();
                name = dt != null ? dt.getSimpleName() : "<init>"; break;
            }
            // lambda / anonymous / initializer: climb to the next enclosing executable
            CtExecutable<?> up = ((spoon.reflect.declaration.CtElement) enc).getParent(CtExecutable.class);
            if (up == enc) break;
            enc = up;
        }
        if (name == null) name = "<clinit-or-field>";
        if (file == null && enc != null) {
            SourcePosition ep = ((spoon.reflect.declaration.CtElement) enc).getPosition();
            if (ep != null && ep.isValidPosition() && ep.getFile() != null) file = ep.getFile().toPath();
        }
        if (file == null) return null;
        return rel(repo, file) + ":" + name;
    }

    private static String rel(Path repo, Path file) {
        Path f = file.toAbsolutePath().normalize();
        return repo.relativize(f).toString();
    }

    // --- tiny JSON helpers (no dependency) ---
    private static String jsonArr(Collection<String> items) {
        if (items.isEmpty()) return "[]";
        StringBuilder b = new StringBuilder("[\n");
        int i = 0;
        for (String s : items) {
            b.append("    ").append(quote(s));
            if (++i < items.size()) b.append(",");
            b.append("\n");
        }
        b.append("  ]");
        return b.toString();
    }

    private static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static Map<String, String> parseArgsRaw(String[] args) {
        Map<String, String> m = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--")) m.put(args[i].substring(2), i + 1 < args.length ? args[++i] : "");
        }
        return m;
    }

    private static void requireArgs(Map<String, String> m, String... req) {
        for (String r : req) if (!m.containsKey(r)) throw new IllegalArgumentException("missing --" + r);
    }

    /**
     * Dump a line->method index for the whole source tree, so the scorer can map
     * an answer like "File.java:114" (prism speaks line numbers, so graph-arm
     * agents answer in lines) to its enclosing method name -- a fair comparison.
     * Output: JSON { "<relpath>": [[startLine, endLine, "name"], ...], ... }.
     */
    private static void indexMode(Map<String, String> a) throws Exception {
        requireArgs(a, "src", "repo", "index");
        Path repo = Paths.get(a.get("repo")).toAbsolutePath().normalize();
        Launcher l = new Launcher();
        for (String s : a.get("src").split(",")) l.addInputResource(s);
        l.getEnvironment().setNoClasspath(true);
        l.getEnvironment().setComplianceLevel(17);
        if (a.containsKey("cp")) {
            String cp = new String(Files.readAllBytes(Paths.get(a.get("cp")))).trim();
            if (!cp.isEmpty()) l.getEnvironment().setSourceClasspath(cp.split(":"));
        }
        CtModel model = l.buildModel();
        // relpath -> list of "start end name"
        TreeMap<String, List<String>> idx = new TreeMap<>();
        int execs = 0;
        for (CtMethod<?> m : model.getElements(new TypeFilter<>(CtMethod.class)))
            execs += addSpan(idx, repo, m, m.getSimpleName());
        for (CtConstructor<?> c : model.getElements(new TypeFilter<>(CtConstructor.class))) {
            CtType<?> dt = c.getDeclaringType();
            execs += addSpan(idx, repo, c, dt != null ? dt.getSimpleName() : "<init>");
        }
        StringBuilder sb = new StringBuilder("{\n");
        int fi = 0;
        for (Map.Entry<String, List<String>> en : idx.entrySet()) {
            sb.append("  ").append(quote(en.getKey())).append(": [");
            for (int i = 0; i < en.getValue().size(); i++) {
                String[] parts = en.getValue().get(i).split(" ", 3);
                sb.append("[").append(parts[0]).append(",").append(parts[1])
                  .append(",").append(quote(parts[2])).append("]");
                if (i + 1 < en.getValue().size()) sb.append(",");
            }
            sb.append("]");
            if (++fi < idx.size()) sb.append(",");
            sb.append("\n");
        }
        sb.append("}\n");
        Files.write(Paths.get(a.get("index")), sb.toString().getBytes());
        System.out.println("[index] files=" + idx.size() + " execs=" + execs
                + " -> " + a.get("index"));
    }

    private static int addSpan(TreeMap<String, List<String>> idx, Path repo,
                               CtExecutable<?> e, String name) {
        SourcePosition p = ((spoon.reflect.declaration.CtElement) e).getPosition();
        if (p == null || !p.isValidPosition() || p.getFile() == null) return 0;
        String rel = rel(repo, p.getFile().toPath());
        idx.computeIfAbsent(rel, k -> new ArrayList<>())
           .add(p.getLine() + " " + p.getEndLine() + " " + name);
        return 1;
    }
}
