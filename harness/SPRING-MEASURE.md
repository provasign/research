# Spring support — measure first, kill criteria fixed in advance

Decision contract (agreed 2026-08-29): build Spring semantics ONLY if the
measurements below show a real completeness gap, and keep it ONLY if the
built edges close that gap. Otherwise it's off the plate.

## M1 — mechanism mass (free): which Spring semantics carry references
Count, on real Spring corpora, the reference mass per mechanism:
@Autowired/@Qualifier/bean names, @Value("${...}") <-> properties/yaml keys,
JPA repository derived methods (interfaces with no bodies), @EventListener
dispatch, @RequestMapping routes, Thymeleaf/JSP template expressions.
A mechanism with trivial mass is not worth an edge builder regardless of M2.

## M2 — ground truth (free): does change_impact miss gold sites TODAY
From merged PRs in the corpora that change a symbol whose gold diff spans
code + config/templates/annotation-strings: run change_impact at the base
commit, score gold-file recall, and record the completeness claim.

KILL 1: if median gold recall >= 0.85 already (the type graph covers it),
Spring-specific edges are off the plate — ship only the honesty qualifier
if completeness over-claims.

## M3 — build to the measured gaps only, then re-run M2
KILL 2: if built edges do not lift M2 recall by >= 0.15 median on the same
tasks, revert and off the plate. Gates as always: suites, invariants, gin
byte-identical, ab_gate.

## Honesty floor (ships regardless of kill decisions)
change_impact on a repo with detected-but-unmodeled framework reference
mechanisms must not claim "closed" — qualified completeness with the
mechanism named. This is a bug fix to the calibration claim, not Spring
support.

Corpora: spring-projects/spring-petclinic (canonical small),
apache/fineract (large real estate). Mining via mine_wide_sweeps +
targeted git-log scan for symbol changes with cross-artifact gold diffs.


## Results (2026-08-29)

M1: templates dominate MVC apps (petclinic: 272 EL/th refs vs 50 java
files); string-borne DI is ~1-2% of a large estate (fineract); typed
@Autowired resolves through the existing interface graph.

M2 before: petclinic Person.getFirstName claimed CLOSED at 2 sites with
4+ template files of live bindings; fineract LoanOriginatorMapping.loanId
UNANCHORABLE (Lombok — no getter symbol) with findByLoanId invisible.
DI-by-type: covered (Guarantor case) -> KILL 1 applied to the DI slice,
nothing built there.

Build (to measured gaps only): Lombok accessor synthesis (astkit —
a JAVA completeness fix, not framework machinery); JPA derived-query
edges (findByLoanIdAndStatus -> entity accessors, entity-scoped, 0.7);
template EL edges (.html/.jsp/.ftl indexed as plaintext, ${...}/*{...}
identifiers -> accessors estate-wide, 0.6); completeness honesty:
heuristic-source callers append "+heuristic-refs" — never plain
"closed" with name-derived edges in the set.

M2 after: getFirstName 2->7 sites, ALL 5 template files as callers;
getLoanId unanchorable -> 6 sites incl. all five derived-query methods.
KILL 2 not triggered (lift ~0 -> ~1.0 on framework-crossing gold).
gin byte-identical (no html); chained-receiver Lombok attribution
(x.getValue().getFirst().getLoanId()) remains a known deep-chain gap.
