"""Quantum catalog — symbolic function chain for the Collibra chip MCP surface.

Implements the full symbolic chain:

    dirac() · einstein() · knuth() · tex() · latex() · jd() · refData()
    collibra().init() · loadCodeTableFromBaseFromShiva()
    bubbleLeader().builder().piotr().groovy().clojure().c().f()
                  .math().godel().escher().pg().pg().paulGraham()
    cosine().similarity().complex().resolve().xml().catalog().collibra()

Quantum redefinition of stack and queue on the complex Cartesian plane.
LaTeX source: docs/quantum/chip-quantum-catalog.tex
SVG diagram:  docs/quantum/complex-plane.svg
"""

from __future__ import annotations

import cmath
import json
import math
import operator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Generic, List, Optional, TypeVar

T = TypeVar("T")
S = TypeVar("S")

# ── Primitive symbols ─────────────────────────────────────────────────────────


def dirac(x: float, x0: float = 0.0, eps: float = 1e-6) -> float:
    """Dirac delta approximation: δ(x − x₀) via Gaussian kernel."""
    return math.exp(-((x - x0) ** 2) / eps**2) / (eps * math.sqrt(math.pi))


def einstein() -> Dict[str, str]:
    """Einstein field equation and mass-energy equivalence in symbolic form."""
    return {
        "field_equation": "G_μν + Λ g_μν = (8πG/c⁴) T_μν",
        "mass_energy":    "E = mc²",
        "data_gravity":   "G_μν^info = (8π G_info / c_latency⁴) T_μν^usage",
        "ultimate_metric": "𝒰 = α·U_usage + β·V_business − γ·C_platform",
        "latex": r"G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4} T_{\mu\nu}",
    }


def knuth() -> Dict[str, str]:
    """Knuth asymptotic notation and up-arrow tower."""
    return {
        "big_O":     "f(n) = O(g(n)) ⟺ ∃c>0,n₀: |f(n)| ≤ c|g(n)| ∀n≥n₀",
        "big_Omega": "f(n) = Ω(g(n)) ⟺ g(n) = O(f(n))",
        "big_Theta": "f(n) = Θ(g(n)) ⟺ f=O(g) ∧ g=O(f)",
        "up_arrow":  "a↑b = aᵇ  |  a↑↑b = aᵃ·ᵇ (tower)  |  a↑↑↑b = ...",
        "taocp":     "The Art of Computer Programming, Vol. 1–4A",
    }


def tex() -> str:
    """TeX typesetting badness formula."""
    return r"b_i = \left(\frac{l_i - L}{L}\right)^3 \cdot 10{,}000"


def latex(expr: Any) -> str:
    """Generate a LaTeX string from any symbolic expression."""
    if isinstance(expr, complex):
        return rf"{expr.real:.4g} + {expr.imag:.4g}i"
    if isinstance(expr, float):
        return rf"{expr:.6g}"
    if isinstance(expr, dict) and "latex" in expr:
        return expr["latex"]
    return str(expr)


def jd(year: int, month: int, day: float) -> float:
    """Julian Day Number JD(Y,M,D) — temporal lineage key.

    JD 2451545.0 = J2000.0 = 2000-01-01 12:00 TT.
    Used in date-elements for catalog temporal keys.
    """
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return float(jdn)


# ── Reference data / code tables ─────────────────────────────────────────────


@dataclass
class CodeEntry:
    code: str
    label: str
    domain: str
    sbvr: str = ""
    collibra_asset_type: str = "Business Term"
    collibra_id: str = ""


def loadCodeTableFromBaseFromShiva(                             # noqa: N802
    db: Path = Path("/tmp/humble-idp.db"),
    shiva_base: str = "urn:singine:base:shiva",
) -> Dict[str, CodeEntry]:
    """Load the canonical code table from the Shiva base layer.

    Code table (AAAA → FFFFF):
      AAAA  — Axiom Alpha        (Mathematics)
      BBBB  — Basis Bundle Beta  (Quantum)
      CCCC  — Catalog Code       (Collibra)
      DDDD  — Dirac Domain       (Physics)
      EEEE  — Einstein Epsilon   (Relativity)
      FFFFF — Formal Field Fiber (Category Theory)
    """
    return {
        "AAAA":  CodeEntry("AAAA",  "Axiom Alpha",        "Mathematics",     "sbvr:Fact",      "Business Term"),
        "BBBB":  CodeEntry("BBBB",  "Basis Bundle Beta",  "Quantum",         "sbvr:Term",      "Data Element"),
        "CCCC":  CodeEntry("CCCC",  "Catalog Code",       "Collibra",        "odrl:Agreement", "Data Asset"),
        "DDDD":  CodeEntry("DDDD",  "Dirac Domain",       "Physics",         "prov:Entity",    "Data Set"),
        "EEEE":  CodeEntry("EEEE",  "Einstein Epsilon",   "Relativity",      "owl:Class",      "Business Process"),
        "FFFFF": CodeEntry("FFFFF", "Formal Field Fiber", "Category Theory", "skos:Concept",   "Reference Data"),
    }


def refData(code: str) -> Optional[CodeEntry]:
    """Look up a code entry from the Shiva base layer."""
    return loadCodeTableFromBaseFromShiva().get(code)


# ── Collibra init ─────────────────────────────────────────────────────────────


class CollibraInit:
    """``collibra().init()`` — catalog initialisation chain."""

    def __init__(self) -> None:
        self._code_table: Dict[str, CodeEntry] = {}
        self._registered: List[str] = []

    def init(self) -> "CollibraInit":
        self._code_table = loadCodeTableFromBaseFromShiva()
        self._registered = list(self._code_table.keys())
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "registered": self._registered,
            "code_table": {k: v.__dict__ for k, v in self._code_table.items()},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def collibra() -> CollibraInit:
    return CollibraInit()


# ── Quantum stack ─────────────────────────────────────────────────────────────


@dataclass
class QuantumStack:
    """Stack as quantum superposition |S⟩ = Σ αₖ|k⟩.

    Push:   â†|n⟩ = √(n+1)|n+1⟩   (creation operator)
    Pop:    â|n⟩  = √n|n−1⟩        (annihilation operator)
    Number: N̂|n⟩  = n|n⟩
    CCR:    [â, â†] = 1̂
    """
    _amplitudes: List[complex] = field(default_factory=lambda: [complex(1, 0)])

    @property
    def depth(self) -> int:
        return len(self._amplitudes) - 1

    @property
    def norm(self) -> float:
        return math.sqrt(sum(abs(a) ** 2 for a in self._amplitudes))

    def normalize(self) -> "QuantumStack":
        n = self.norm
        if n > 0:
            self._amplitudes = [a / n for a in self._amplitudes]
        return self

    def push(self, alpha: complex = complex(1, 0)) -> "QuantumStack":
        """â†: extend superposition by one basis state."""
        n = len(self._amplitudes)
        self._amplitudes.append(alpha / math.sqrt(n + 1))
        return self.normalize()

    def pop(self) -> "QuantumStack":
        """â: collapse top basis state (annihilate)."""
        if len(self._amplitudes) <= 1:
            return self  # |0⟩ is annihilated to 0
        self._amplitudes.pop()
        return self.normalize()

    def number_expectation(self) -> float:
        """⟨N̂⟩ = Σₖ k |αₖ|²"""
        return sum(k * abs(a) ** 2 for k, a in enumerate(self._amplitudes))

    def ket(self) -> str:
        terms = [f"({a.real:.3f}{a.imag:+.3f}i)|{k}⟩"
                 for k, a in enumerate(self._amplitudes)]
        return "|S⟩ = " + " + ".join(terms)


# ── Quantum queue ─────────────────────────────────────────────────────────────


@dataclass
class QuantumQueue:
    """Queue as density matrix ρ_Q = Σᵢ pᵢ|ψᵢ⟩⟨ψᵢ|.

    Enqueue: U_enq ρ U_enq†  ⊗  |new⟩⟨new|
    Dequeue: Tr₁[ρ]  (partial trace over first register)
    """
    _states: List[complex] = field(default_factory=list)
    _probs: List[float] = field(default_factory=list)

    def enqueue(self, state: complex, prob: float = 1.0) -> "QuantumQueue":
        self._states.append(state)
        self._probs.append(prob)
        self._normalize_probs()
        return self

    def dequeue(self) -> Optional[complex]:
        """Partial trace over first register — returns front element."""
        if not self._states:
            return None
        state = self._states.pop(0)
        self._probs.pop(0)
        self._normalize_probs()
        return state

    def _normalize_probs(self) -> None:
        total = sum(self._probs)
        if total > 0:
            self._probs = [p / total for p in self._probs]

    @property
    def purity(self) -> float:
        """Tr[ρ²] = Σᵢ pᵢ² — 1 for pure state, 1/n for maximally mixed."""
        return sum(p ** 2 for p in self._probs) if self._probs else 0.0

    def density_repr(self) -> str:
        terms = [f"{p:.3f}|ψ_{i}⟩⟨ψ_{i}|"
                 for i, p in enumerate(self._probs)]
        return "ρ_Q = " + " + ".join(terms) if terms else "ρ_Q = 0"


# ── Complex cosine similarity ─────────────────────────────────────────────────


def cosine_similarity_complex(
    u: List[complex], v: List[complex]
) -> complex:
    """Complex inner-product cosine similarity.

    cos_sim(u,v) = Re(⟨u,v⟩) / (|u|·|v|)

    On the complex Cartesian plane:
        z = r e^{iθ}  →  cos θ = Re(e^{iθ}) = cos(arg(z))
    """
    dot = sum(a.conjugate() * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(abs(a) ** 2 for a in u))
    norm_v = math.sqrt(sum(abs(b) ** 2 for b in v))
    if norm_u == 0 or norm_v == 0:
        return complex(0, 0)
    return dot / (norm_u * norm_v)


# ── Fluent cosine → Collibra chain ───────────────────────────────────────────


class CosineChain:
    """cosine().similarity().complex().resolve().xml().catalog().collibra()"""

    def __init__(self, u: List[complex], v: List[complex]) -> None:
        self._u = u
        self._v = v
        self._sim: Optional[complex] = None
        self._angle: Optional[float] = None
        self._iri: Optional[str] = None
        self._xml_node: Optional[str] = None
        self._catalog_entry: Optional[Dict[str, Any]] = None
        self._collibra_result: Optional[Dict[str, Any]] = None

    def similarity(self) -> "CosineChain":
        self._sim = cosine_similarity_complex(self._u, self._v)
        return self

    def complex(self) -> "CosineChain":  # noqa: A003
        if self._sim is not None:
            self._angle = cmath.phase(self._sim)
        return self

    def resolve(self) -> "CosineChain":
        if self._angle is not None:
            code = list(loadCodeTableFromBaseFromShiva().keys())[
                int(abs(self._angle) / (math.pi / 6)) % 6
            ]
            entry = refData(code)
            self._iri = f"urn:singine:quantum:{entry.domain.lower()}:{code}" if entry else ""
        return self

    def xml(self) -> "CosineChain":  # noqa: A003
        self._xml_node = (
            f'<cosine-similarity iri="{self._iri or ""}"'
            f' re="{self._sim.real:.6f}" im="{self._sim.imag:.6f}"'
            f' angle_rad="{self._angle:.6f}"'
            f' cos_theta="{math.cos(self._angle or 0):.6f}"/>'
        )
        return self

    def catalog(self) -> "CosineChain":
        self._catalog_entry = {
            "dcat:Dataset": self._iri,
            "dct:description": "Cosine similarity on complex Cartesian plane",
            "cos_sim": self._sim.real if self._sim else 0,
            "angle_rad": self._angle,
            "xml_node": self._xml_node,
        }
        return self

    def collibra(self) -> Dict[str, Any]:
        self._collibra_result = {
            "ok": True,
            "command": "cosine().similarity().complex().resolve().xml().catalog().collibra()",
            "asset_iri": self._iri,
            "catalog": self._catalog_entry,
            "xml": self._xml_node,
            "mcp_tool": "collibra/code_lookup",
        }
        return self._collibra_result


def cosine() -> "_CosineFactory":
    class _CosineFactory:
        def __call__(self, u: List[complex], v: List[complex]) -> CosineChain:
            return CosineChain(u, v)
    return _CosineFactory()


# ── BubbleLeader builder chain ────────────────────────────────────────────────


class BubbleLeaderChain:
    """Ξ = bubbleLeader().builder().piotr().groovy().clojure()
              .c().f().math().godel().escher().pg().pg().paulGraham()

    As function composition (right-to-left):
        Ξ = bubbleLeader ∘ builder ∘ piotr ∘ ... ∘ paulGraham

    As monad bind (left-to-right):
        x >>= bubbleLeader >>= builder >>= ... >>= paulGraham
    """

    def __init__(self, data: Any = None) -> None:
        self._data = data
        self._trace: List[str] = []

    def _step(self, name: str, transform: Callable[[Any], Any]) -> "BubbleLeaderChain":
        self._trace.append(name)
        self._data = transform(self._data)
        return self

    # ── chain steps ──────────────────────────────────────────────────────────

    def builder(self) -> "BubbleLeaderChain":
        """GoF Builder: accumulate config."""
        return self._step("builder", lambda d: {"built": True, "input": d, "config": {}})

    def piotr(self) -> "BubbleLeaderChain":
        """Cross-language coordination point."""
        return self._step("piotr", lambda d: {**d, "coordinated": True, "langs": []})

    def groovy(self) -> "BubbleLeaderChain":
        """Groovy JVM DSL layer (JProfiler target: chip.profiler.groovy)."""
        return self._step("groovy", lambda d: {**d, "langs": d.get("langs", []) + ["groovy"]})

    def clojure(self) -> "BubbleLeaderChain":
        """Clojure pure-function pass (persistence.core)."""
        return self._step("clojure", lambda d: {**d, "langs": d.get("langs", []) + ["clojure"]})

    def c(self) -> "BubbleLeaderChain":
        """C layer: zero-copy, cache-aligned structs."""
        return self._step("c", lambda d: {**d, "langs": d.get("langs", []) + ["c"]})

    def f(self) -> "BubbleLeaderChain":
        """F-algebra / fixed-point functor."""
        return self._step("f", lambda d: {**d, "algebra": "F-algebra", "fix": "μF"})

    def math(self) -> "BubbleLeaderChain":
        """Symbolic algebra — SymPy / Mathematica layer."""
        return self._step("math", lambda d: {**d, "symbolic": True, "cas": "sympy"})

    def godel(self) -> "BubbleLeaderChain":
        """Gödel encoding: ⌈Ξ⌉ = Π pⱼ^aⱼ  (incompleteness check)."""
        def _encode(d: Any) -> Any:
            primes = [2, 3, 5, 7, 11, 13, 17]
            tokens = list(str(d))[:7]
            gnum = reduce(operator.mul, (p ** ord(t) for p, t in zip(primes, tokens)), 1)
            return {**d, "godel_number": gnum, "incomplete": True}
        return self._step("godel", _encode)

    def escher(self) -> "BubbleLeaderChain":
        """Escher fixed-point: Y = λf.(λx.f(xx))(λx.f(xx))."""
        def _fixed(d: Any) -> Any:
            return {**d, "fixed_point": True, "combinator": "Y", "self_ref": "f∘f"}
        return self._step("escher", _fixed)

    def pg(self) -> "BubbleLeaderChain":
        """PostgreSQL query layer — or Paul Graham (second call)."""
        calls = self._trace.count("pg")
        if calls == 0:
            return self._step("pg", lambda d: {**d, "storage": "postgresql", "sql": True})
        else:
            return self._step("pg", lambda d: {**d, "lisp_wisdom": "pg/arc", "pg_quote": "Succinctness is power."})

    def paulGraham(self) -> "BubbleLeaderChain":  # noqa: N802
        """Terminal evaluation: LISP primitives — atom, eq, car, cdr, cons, cond, lambda."""
        def _eval(d: Any) -> Any:
            return {
                **d,
                "terminal": "paulGraham",
                "lisp_primitives": ["atom", "eq", "car", "cdr", "cons", "cond", "lambda"],
                "thesis": "Succinctness is power.",
                "arc_eval": f"(eval '{json.dumps(d)[:40]}... nil)",
            }
        return self._step("paulGraham", _eval)

    def build(self) -> Dict[str, Any]:
        return {"chain": self._trace, "result": self._data}


def bubbleLeader(items: Optional[List[Any]] = None) -> BubbleLeaderChain:
    """Elect leader via bubble-up: float max to top.

    In quantum terms: â†|max⟩ → collapses superposition to max eigenstate.
    """
    if items is None:
        items = []
    # Bubble sort pass — O(n²) classical, O(n^{3/2}) quantum
    arr = list(items)
    for i in range(len(arr) - 1):
        for j in range(len(arr) - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return BubbleLeaderChain(data={"leader": arr[-1] if arr else None, "sorted": arr})
