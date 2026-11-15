"""Conservative correlation of adjacent cumulative observations; no prompt retention."""
from dataclasses import dataclass, field

KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def usage(values):
    result = dict(values)
    i, c = result["input_tokens"], result["cached_input_tokens"]
    result["uncached_input_tokens"] = i - c if i is not None and c is not None and i >= c else None
    return result


@dataclass
class TurnTracker:
    turns: list = field(default_factory=list)
    unassigned: list = field(default_factory=list)
    active: dict | None = None
    previous: dict | None = None
    previous_owner: dict | None = None

    def event(self, kind, payload, timestamp):
        ident = payload.get("turn_id")
        ident = ident if isinstance(ident, str) and ident else None
        if kind == "event_msg" and payload.get("type") == "task_started":
            overlap = self.active is not None
            if overlap:
                self.active["state"] = "limite_ambiguo"
                self.active["ambiguous"] = True
            turn = {"id": ident, "started_at": timestamp, "ended_at": None,
                    "state": "inicio_observado", "models": [], "efforts": [],
                    "confirmed": False, "ambiguous": overlap or ident is None or any(t["id"] == ident for t in self.turns),
                    "usage": dict.fromkeys(KEYS), "incomplete_fields": [], "intervals": 0}
            self.turns.append(turn)
            self.active = turn
        elif kind == "turn_context" and self.active is not None:
            turn = self.active
            if ident != turn["id"] or ident is None:
                turn["ambiguous"] = True
            else:
                turn["confirmed"] = True
                for key, source in (("models", "model"), ("efforts", "effort")):
                    value = payload.get(source)
                    if isinstance(value, str) and value and value not in turn[key]:
                        turn[key].append(value)
        elif kind == "event_msg" and payload.get("type") == "task_complete":
            if self.active is not None:
                self.active["ended_at"] = timestamp
                if ident == self.active["id"] and ident is not None:
                    self.active["state"] = "encerramento_observado"
                else:
                    self.active["state"] = "limite_ambiguo"
                    self.active["ambiguous"] = True
            self.active = None

    def snapshot(self, total, timestamp):
        total = {k: v if type(v) is int and v >= 0 else None for k in KEYS for v in [total.get(k)]} if isinstance(total, dict) else None
        owner = self.active if self.active and self.active["confirmed"] and not self.active["ambiguous"] else None
        if total is None or not any(v is not None for v in total.values()):
            self.previous = None
            self.previous_owner = None
            self.unassigned.append({"timestamp": timestamp, "reason": "sem_acumulado", "usage": usage(dict.fromkeys(KEYS))})
            return
        previous = self.previous
        delta = {k: total[k] - previous[k] if previous and total[k] is not None and previous[k] is not None and total[k] >= previous[k] else None for k in KEYS}
        regression = bool(previous and any(total[k] is not None and previous[k] is not None and total[k] < previous[k] for k in KEYS))
        changed = previous is None or regression or any(v for v in delta.values()) or any(total[k] is not None and previous[k] is None for k in KEYS)
        if changed:
            if previous and not regression and owner is not None and owner is self.previous_owner:
                for k, value in delta.items():
                    if value is None:
                        if k not in owner["incomplete_fields"]:
                            owner["incomplete_fields"].append(k)
                        owner["usage"][k] = None
                    elif k not in owner["incomplete_fields"]:
                        owner["usage"][k] = (owner["usage"][k] or 0) + value
                owner["intervals"] += 1
            else:
                reason = "primeira_referencia" if previous is None else "regressao" if regression else "limite_ou_associacao_insegura"
                self.unassigned.append({"timestamp": timestamp, "reason": reason, "usage": usage(dict.fromkeys(KEYS) if regression else delta)})
        self.previous = total
        self.previous_owner = owner

    def as_dict(self):
        return {"turns": [{**t, "usage": usage(t["usage"]), "metadata_changed": len(t["models"]) > 1 or len(t["efforts"]) > 1} for t in self.turns],
                "unassigned_usage": self.unassigned}
