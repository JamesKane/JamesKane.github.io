---
layout: post
title: "Vestra: a systems language you can hold in your head"
date: 2026-05-23
tags: [vestra, systems-programming, language-design, cpp, transpiler]
excerpt: "An introduction to Vestra, a Swift-flavored systems language whose grammar fits on two pages, and the v0 transpiler that lowers it to C++26."
---

Over the past year, I have been sketching out a systems language called Vestra. The work began as a way to think clearly about what a kernel-and-engine language would look like if the safety decisions were made up front rather than retrofitted, and it has now grown into a working v0 transpiler: Vestra source in, C++26 source out, host compiler turns it into a real binary. The spec is checked into the repo at `VESTRA_DRAFT.md`; the transpiler that proves the spec compiles is the rest of the tree.

This post is the introduction I have been meaning to write for a while.

## The organizing rule

Vestra has exactly one organizing rule, and every feature in the spec earns its place against it:

> Everything that matters is in the signature. Nothing that matters is hidden.

A function's type states what it can reach (its *capabilities*), how it can fail (typed errors), what it borrows versus takes (parameter modes), and whether it can suspend (`async`). If a behavior is not written in a type, the compiler guarantees it cannot happen.

That single rule does the work of three orthogonal concerns at once. It is the safety model, the security model, and the performance-predictability model. It is also what makes the language *comprehensible*, because it makes the comprehensibility claim testable. A reader looking at any line of Vestra should be able to answer six questions from local reading alone:

1. Does this allocate?
2. Does this copy a non-trivial value?
3. Does this call indirectly (dynamic dispatch)?
4. Can this fail?
5. Can this suspend?
6. What can this code reach (which capabilities)?

If answering any of them requires opening another file, the feature that hid it is a bug in the language.

## What it looks like

The surface is Swift- and Scala-3-flavored: `func`, `struct`, `enum`, `match`, argument labels, `[T]` for type parameters. Blocks are always brace-delimited; indentation is formatting, never grammar. Here is one of the small programs the end-to-end tests transpile and run on every build:

```vestra
module examples.shapes

struct Point {
    var x: Int32
    var y: Int32
}

enum Color {
    case red
    case green
    case blue
}

func channel(_ c: Color) -> Int32 {
    return match c {
        case .red:   1
        case .green: 2
        case .blue:  3
    }
}

func compute() -> Int32 {
    let p = Point(x: 10, y: 32)
    return p.x + p.y + channel(Color.green)
}
```

Nothing surprising on the surface. The interesting bits start when the program needs to express *ownership* or *authority*.

## Ownership without a borrow checker

Vestra has no surface references. There is no `&T`, and there are no lifetime annotations. Every binding names a value; mutation through a caller happens only via a parameter, and the parameter's mode is written in the signature.

| Mode | Meaning | Call site |
|---|---|---|
| `read` (default) | Immutable view. Zero-copy. Caller keeps the value. | `f(x)` |
| `inout` | Exclusive mutable view. Caller keeps the value, mutated. | `f(&x)` |
| `sink` | Ownership transfers in. Caller's binding ends. | `f(x)` |

```vestra
func consume(_ b: sink Buf) -> Int32 { return b.n }
func peek(_ b: Buf) -> Int32          { return b.n }

func compute() -> Int32 {
    let b = make_buf(7)
    let first  = peek(b)              // ok, read
    let second = peek(b)              // ok, still read
    return first + second + consume(b)  // b consumed here
}
```

A second `peek(b)` after the `consume(b)` is a compile error, with a diagnostic naming both the use and the original move site. The same affine-tracking machinery enforces the Law of Exclusivity at every call. Live borrows of a storage location must be either all `read` or exactly one `inout`, never both. So `swap(&p.x, &p.y)` is fine (disjoint fields), but `swap(&p, &p.x)` is rejected as a parent-and-child overlap.

The machinery a Rust reader would expect to see is there underneath, but it is encoded in the three parameter modes, and the rest is inferred locally. There is no lifetime grammar to learn because there is no surface reference type to attach one to.

## Capabilities: the question nobody else answers

Most modern languages can tell you what a function returns and whether it can throw. None of the mainstream ones can tell you, from the signature alone, what *authority* a function actually exercises: whether it can allocate, write to disk, send a network packet, log, or read the clock.

In Vestra every authority is named in a `using` clause:

```vestra
func handle_request(_ req: Request)
    using Alloc, Log, Net
    throws(NetError)
{
    // This function can allocate (Alloc), log (Log), and do
    // network I/O (Net), and may fail with NetError. That is
    // the complete list of side effects it can perform.
}
```

The caller must either have those capabilities in scope or supply them with a `with` block:

```vestra
with Net = ProductionNet() {
    try handle_request(req)
}
```

`async func` adds an implicit `Async`; `await` and `spawn` are well-formed only where `Async` is in scope. There is no separate coroutine type system, no `Pin`, no promise machinery. Concurrency is just one more capability.

The payoff is that `vestra audit --capabilities` prints the reachable capability set per function, mechanically. The question "could this function ever send a network packet?" has a clean answer that does not require reading the body, or its callees, or any of its transitive callees. That is the question Vestra was designed around.

## The transpiler

The v0 implementation is a Vestra-to-C++26 transpiler, written in C++26 itself. The choice of target needs a little defending (going through C++ rather than straight to LLVM is unfashionable), but it is the right shape for v0 work.

C++26 gives mature codegen, a real platform ABI, and the entire C ecosystem within reach on day one. Vestra's primitives map cleanly: `Int32` becomes `std::int32_t`, modules become nested namespaces, structs lower to structs with designated-initializer construction, bare enums to `enum class`, payloaded enums to `std::variant`, generics to C++ templates that the host compiler monomorphizes. Sink-mode parameters lower to `T&&` with `std::move(...)` inserted at the call site; `let` bindings emit as `auto` rather than `const auto` so ownership transfers are actually expressible. A `comptime { 1 << 12 }` folds to a literal `4096` in the generated header. The build pipeline is parse → resolve → check → emit `.hpp/.cpp` → invoke `clang++ -std=c++26` → run.

The architecture is a classic layered front end:

- **Lexer.** Hand-rolled, covering every keyword in §17.1: numeric literals with underscores, hex/oct/binary/exponent, strings with escapes, byte strings, nested block comments, newline-as-terminator with continuation rules.
- **Parser.** Recursive descent for declarations and statements; Pratt for expressions, with a precedence table that matches §17.7. Each error is a `Diagnostic` and the parser resynchronizes to the next top-level declaration.
- **Sema.** Two-pass name resolver builds a scope chain over the global namespace and function bodies; bidirectional type checking lets integer literals adopt annotated types; member access, struct construction, enum cases, and `match` arms all type-check with exhaustiveness verification.
- **Ownership and exclusivity.** Phase 1 of §5: affine flow tracking flags use-after-move at sink calls and `return`; `copy x` salvages a binding; reassigning a consumed `var` revives it. Per-call overlap analysis on a path-aware `Place` representation enforces exclusivity.
- **Capabilities, generics, comptime.** Phase 1 of each of §8, §7, and §12.1: `using` rows propagated and verified, generic functions type-checked once with opaque `T`s and inferred at call sites, pure-expression evaluator that folds `const Fact6: Int32 = comptime { factorial(6) }` into `inline constexpr std::int32_t Fact6 = 720;` in the generated header.
- **Codegen.** A single emitter pass that consumes the resolver's side table, so context-sensitive lowering (struct vs function call, enum case spelling, match scrutinee type) is correct without a second walk.

Seventeen tests gate the whole pipeline today. The end-to-end ones transpile a `.vst` file, invoke the host C++ compiler, run the binary, and assert on its exit code. The most useful one to read is `examples/ownership.vst`, the smallest program that exercises the move tracker, the exclusivity checker, and the C++ emitter's `std::move` placement together.

## What is intentionally stubbed

The features I have deliberately not shipped in v0, roughly in the order I plan to tackle them:

- Branch-aware ownership flow merging (phase 2 of §5).
- The audit-trail `// Safety:` mechanism, capability narrowing, and gating of actual unsafe operations once they exist.
- Const generics, generic structs and enums, where-clauses, and protocol-bound enforcement (phase 2 of §7).
- Full reflection over `Type` values, `derive(Eq, Hash, Clone, …)` via comptime defaults, and declaration macros built on a typed `quote { … }` (the rest of §12).
- `async` / `spawn` / `select` / `parallel` lowering (§11), currently parsed but emitted as `unsupported` comments.
- SIMD `[N]T` lowering (§13) and conditional compilation via `cfg` / `@when` (§12.6).

Each of these adds one §-block of the spec at a time. The acceptance test for any of them is straightforward: the relevant `examples/*.vst` file transpiles to C++ that compiles and produces the right answer.

## Why bother

The honest case for Vestra is not that modern C++ is unsafe. C++26 has reflection, contracts, `std::execution`, pattern matching, and hardened-library bounds checks, and modern C++ written in the C++26 idiom is dramatically safer than its reputation suggests. The case is that safety in C++26 is reached by *layering* (profiles opted into, hardening flags enabled, contracts written, idioms followed) on top of forty-five years of accumulated decisions. The same outcome can be reached by a language that made the safety decision in section 1 and never had a default to break.

That is the wager. The whole spec is about thirty concepts and a two-page grammar. Every signature tells the whole story. Whether that produces a language people actually want to write code in is an empirical question, and the only way to find out is to ship a compiler and write enough Vestra to discover where the design is wrong.

The v0 transpiler is the first chunk of that work. More to come as I build it out.

## Where you can find it

The project is on [GitHub](https://github.com/JamesKane/Vestra-Transpiler).  Feedback is welcome.
