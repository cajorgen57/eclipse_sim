from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import math, random
from collections import Counter

# -------- utilities --------

def _logcomb(n: int, k: int) -> float:
    """log(binomial(n,k)) via lgamma; returns -inf if invalid."""
    from math import lgamma
    if k < 0 or k > n:
        return float("-inf")
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)

# -------- Discrete HMM for enemy ship-design archetypes --------

@dataclass
class DiscreteHMM:
    states: List[str]
    observations: List[str]
    start_prob: Dict[str, float]
    trans_prob: Dict[Tuple[str,str], float]  # (s->s')
    emit_prob: Dict[Tuple[str,str], float]   # (s,obs)
    _min_p: float = 1e-12

    def _norm(self, d: Dict[str,float]) -> Dict[str,float]:
        total = sum(d.values())
        if total <= 0:
            n = 1.0/len(d) if d else 0.0
            return {k:n for k in d}
        return {k:max(self._min_p, v/total) for k,v in d.items()}

    def forward(self, obs_seq: List[str]) -> List[Dict[str,float]]:
        if not obs_seq:
            return []
        alpha: List[Dict[str,float]] = []
        a0 = {}
        for s in self.states:
            a0[s] = max(self._min_p, self.start_prob.get(s, self._min_p) * self.emit_prob.get((s, obs_seq[0]), self._min_p))
        a0 = self._norm(a0)
        alpha.append(a0)
        for t in range(1, len(obs_seq)):
            at = {}
            for s in self.states:
                summ = 0.0
                for sp, ap in alpha[t-1].items():
                    summ += ap * self.trans_prob.get((sp, s), self._min_p)
                at[s] = max(self._min_p, summ * self.emit_prob.get((s, obs_seq[t]), self._min_p))
            alpha.append(self._norm(at))
        return alpha

    def viterbi(self, obs_seq: List[str]) -> List[str]:
        if not obs_seq:
            return []
        V: List[Dict[str,float]] = []
        path: Dict[str, List[str]] = {s:[s] for s in self.states}
        v0 = {}
        for s in self.states:
            v0[s] = math.log(self.start_prob.get(s, self._min_p)) + math.log(self.emit_prob.get((s, obs_seq[0]), self._min_p))
        V.append(v0)
        for t in range(1, len(obs_seq)):
            Vt: Dict[str,float] = {}
            new_path: Dict[str,List[str]] = {}
            for s in self.states:
                best, best_s = -1e300, None
                for sp in self.states:
                    score = V[t-1][sp] + math.log(self.trans_prob.get((sp, s), self._min_p))
                    if score > best:
                        best, best_s = score, sp
                Vt[s] = best + math.log(self.emit_prob.get((s, obs_seq[t]), self._min_p))
                new_path[s] = path[best_s] + [s] if best_s else [s]
            V.append(Vt); path = new_path
        last = max(self.states, key=lambda s: V[-1][s])
        return path[last]

    def posterior(self, obs_seq: List[str]) -> Dict[str,float]:
        alpha = self.forward(obs_seq)
        return alpha[-1] if alpha else {s:1.0/len(self.states) for s in self.states}

    def posterior_with_forgetting(self, obs_seq: List[str], rho: float = 0.9) -> Dict[str, float]:
        """
        Exponential forgetting (rho in [0,1]). rho=1.0 -> standard forward.
        At each step, mix previous posterior with start distribution.
        """
        if not obs_seq:
            u = 1.0 / len(self.states)
            return {s: u for s in self.states}

        alpha = {}
        for s in self.states:
            alpha[s] = max(self._min_p, self.start_prob.get(s, self._min_p) *
                           self.emit_prob.get((s, obs_seq[0]), self._min_p))
        Z = sum(alpha.values()) or 1.0
        for s in alpha:
            alpha[s] = alpha[s] / Z

        for t in range(1, len(obs_seq)):
            prev = {sp: rho * alpha[sp] + (1.0 - rho) * self.start_prob.get(sp, self._min_p) for sp in self.states}
            at = {}
            for s in self.states:
                summ = 0.0
                for sp, ap in prev.items():
                    summ += ap * self.trans_prob.get((sp, s), self._min_p)
                at[s] = max(self._min_p, summ * self.emit_prob.get((s, obs_seq[t]), self._min_p))
            Z = sum(at.values()) or 1.0
            alpha = {s: at[s] / Z for s in self.states}
        return alpha

# -------- Particle filter for hidden sector tiles / bag composition --------

@dataclass
class TileParticle:
    bag: Dict[str,int]
    hidden_hex_types: Dict[str,str] = field(default_factory=dict)
    weight: float = 1.0

@dataclass
class TileParticleFilter:
    particles: List[TileParticle]
    min_particles: int = 256
    jitter: float = 0.0
    _min_w: float = 1e-20

    @staticmethod
    def from_bag(bag: Dict[str,int], n: int = 512) -> 'TileParticleFilter':
        pts = [TileParticle(bag=dict(bag), hidden_hex_types={}, weight=1.0) for _ in range(n)]
        return TileParticleFilter(particles=pts, min_particles=n)

    def predict(self):
        return

    def update_on_draw(self, drawn_type: str):
        for p in self.particles:
            total = sum(p.bag.values()) or 1
            like = max(self._min_w, p.bag.get(drawn_type, 0) / total)
            p.weight *= like
            if p.bag.get(drawn_type, 0) > 0:
                p.bag[drawn_type] -= 1
        self._normalize_and_resample()

    def update_on_peek(self, seen: Dict[str, int]):
        """
        Update weights after seeing a multiset of categories from a draw-and-look,
        then putting them back. Uses multivariate hypergeometric likelihood.
        """
        k = sum(int(v) for v in seen.values())
        if k <= 0:
            return
        for p in self.particles:
            total = sum(p.bag.values())
            if total < k:
                p.weight *= self._min_w
                continue
            loglike = -_logcomb(total, k)
            invalid = False
            for t, c in seen.items():
                c = int(c)
                bt = int(p.bag.get(t, 0))
                if c > bt:
                    invalid = True
                    break
                loglike += _logcomb(bt, c)
            if invalid:
                p.weight *= self._min_w
            else:
                p.weight *= max(self._min_w, math.exp(loglike))
        self._normalize_and_resample()

    def update_on_reveal(self, hex_id: str, tile_type: str):
        for p in self.particles:
            if hex_id in p.hidden_hex_types and p.hidden_hex_types[hex_id] != tile_type:
                p.weight *= self._min_w
            p.hidden_hex_types[hex_id] = tile_type
            if p.bag.get(tile_type, 0) > 0:
                p.bag[tile_type] -= 1
        self._normalize_and_resample()

    def marginal_bag(self) -> Dict[str,float]:
        tot_w = sum(p.weight for p in self.particles) or 1.0
        agg: Dict[str,float] = Counter()
        for p in self.particles:
            for k,v in p.bag.items():
                agg[k] += p.weight * v
        return {k: agg[k]/tot_w for k in agg}

    def _normalize_and_resample(self):
        tot = sum(p.weight for p in self.particles) or 1.0
        for p in self.particles:
            p.weight = max(self._min_w, p.weight / tot)
        ess = 1.0 / sum(p.weight**2 for p in self.particles)
        if ess < 0.5 * len(self.particles):
            self._systematic_resample()

    def _systematic_resample(self):
        N = len(self.particles)
        positions = [(random.random() + i)/N for i in range(N)]
        cumulative = []
        csum = 0.0
        for p in self.particles:
            csum += p.weight
            cumulative.append(csum)
        new_particles: List[TileParticle] = []
        i = 0
        for pos in positions:
            while pos > cumulative[i]:
                i += 1
            src = self.particles[i]
            new_particles.append(TileParticle(bag=dict(src.bag), hidden_hex_types=dict(src.hidden_hex_types), weight=1.0/N))
        self.particles = new_particles

# -------- Belief state composer --------

@dataclass
class BeliefState:
    hmm_by_player: Dict[str, DiscreteHMM] = field(default_factory=dict)
    obs_history_by_player: Dict[str, List[str]] = field(default_factory=dict)
    pf_by_bag: Dict[str, TileParticleFilter] = field(default_factory=dict)

    def ensure_enemy_model(self, player_id: str):
        if player_id not in self.hmm_by_player:
            states = ["brawler","turtle","missile_alpha","evasion"]
            obs = ["plasma","positron","fusion","gauss","shields","missiles","drive"]
            u = 1.0/len(states)
            start = {s:u for s in states}
            trans = {}
            for s1 in states:
                for s2 in states:
                    trans[(s1,s2)] = 0.7 if s1==s2 else 0.3/(len(states)-1)
            emit = {}
            for s in states:
                for o in obs:
                    base = 1.0/len(obs)
                    if s=="brawler" and o in ("plasma","positron"): base = 0.25
                    if s=="turtle" and o in ("shields","gauss"): base = 0.25
                    if s=="missile_alpha" and o=="missiles": base = 0.35
                    if s=="evasion" and o=="drive": base = 0.25
                    emit[(s,o)] = base
                tot = sum(emit[(s,o)] for o in obs)
                for o in obs:
                    emit[(s,o)] /= tot
            self.hmm_by_player[player_id] = DiscreteHMM(states, obs, start, trans, emit)
            self.obs_history_by_player[player_id] = []

    def observe_enemy_signal(self, player_id: str, signal: str):
        self.ensure_enemy_model(player_id)
        if signal not in self.hmm_by_player[player_id].observations:
            hmm = self.hmm_by_player[player_id]
            hmm.observations.append(signal)
            for s in hmm.states:
                hmm.emit_prob[(s, signal)] = 1e-6
        self.obs_history_by_player[player_id].append(signal)

    def enemy_posterior(self, player_id: str, rho: float = 1.0) -> Dict[str,float]:
        self.ensure_enemy_model(player_id)
        obs = self.obs_history_by_player[player_id]
        if not obs:
            u = 1.0/len(self.hmm_by_player[player_id].states)
            return {s:u for s in self.hmm_by_player[player_id].states}
        hmm = self.hmm_by_player[player_id]
        if rho >= 1.0:
            return hmm.posterior(obs)
        return hmm.posterior_with_forgetting(obs, rho=rho)

    def ensure_bag(self, bag_id: str, initial_bag: Dict[str,int], particles: int = 512):
        if bag_id not in self.pf_by_bag:
            self.pf_by_bag[bag_id] = TileParticleFilter.from_bag(initial_bag, n=particles)

    def draw_from_bag(self, bag_id: str, drawn_type: str):
        pf = self.pf_by_bag.get(bag_id)
        if not pf:
            return
        pf.update_on_draw(drawn_type)

    def reveal_hex_tile(self, bag_id: str, hex_id: str, tile_type: str):
        pf = self.pf_by_bag.get(bag_id)
        if not pf:
            return
        pf.update_on_reveal(hex_id, tile_type)

    def expected_bag(self, bag_id: str) -> Dict[str,float]:
        pf = self.pf_by_bag.get(bag_id)
        return pf.marginal_bag() if pf else {}

    def to_dict(self, include_particles: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "obs_history_by_player": {k: list(v) for k, v in self.obs_history_by_player.items()},
            "bags": {}
        }
        for bag_id, pf in self.pf_by_bag.items():
            if include_particles:
                out["bags"][bag_id] = [
                    {"bag": dict(p.bag), "hidden": dict(p.hidden_hex_types), "w": float(p.weight)}
                    for p in pf.particles
                ]
            else:
                out["bags"][bag_id] = {
                    "expected": pf.marginal_bag(),
                    "n_particles": len(pf.particles)
                }
        return out

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BeliefState":
        bs = BeliefState()
        bs.obs_history_by_player = {k: list(v) for k, v in data.get("obs_history_by_player", {}).items()}
        for bag_id, v in data.get("bags", {}).items():
            if isinstance(v, list):  # full particles
                parts = []
                for rec in v:
                    parts.append(
                        TileParticle(
                            bag=dict(rec.get("bag", {})),
                            hidden_hex_types=dict(rec.get("hidden", {})),
                            weight=float(rec.get("w", 1.0))
                        )
                    )
                bs.pf_by_bag[bag_id] = TileParticleFilter(particles=parts, min_particles=len(parts))
            elif isinstance(v, dict) and "expected" in v:  # summary only
                exp = v.get("expected", {})
                approx = {k: int(round(float(val))) for k, val in exp.items()}
                n = int(v.get("n_particles", 256))
                bs.pf_by_bag[bag_id] = TileParticleFilter.from_bag(approx, n=n)
        return bs
