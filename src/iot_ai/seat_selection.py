# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
"""Auditable provider/model and dashboard-agent seat resolution."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .licensing import current
from .meeting_integration import list_agent_seats
from .providers import load as load_routes, static_status
from .readiness import discover_ollama_cloud_models, provider_candidates
from .settings import load as load_settings

CODER_PROVIDERS = ("claude", "codex", "gemini", "grok")
ALL_WITH_OLLAMA_SELECTORS = {"all", "all-coders+ollama-clouds", "all-coders-and-ollama-clouds", "all-coders+ollama", "coders+ollama"}
ALL_CODER_SELECTORS = {"all-coders", "coders", "all-coder"}
OLLAMA_CLOUD_SELECTORS = {"ollama-clouds", "all-ollama-clouds", "ollama-cloud"}
ALL_QUALIFIED_SELECTORS = {"all-qualified-cloud-models", "all-qualified-models", "qualified-cloud-models"}

@dataclass(frozen=True)
class SeatPlan:
    selector: str
    requested_seats: tuple[str, ...]
    resolved_seats: tuple[str, ...]
    candidate_status: tuple[dict[str, Any], ...]
    excluded: tuple[dict[str, Any], ...]
    ollama_cloud_available: bool
    ollama_cloud_included: bool
    max_seats: int
    decision: str
    reason: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return {"schema":"iot-ai.meeting-seat-plan.v2","selector":self.selector,"requested_seats":list(self.requested_seats),"resolved_seats":list(self.resolved_seats),"candidate_status":[dict(item) for item in self.candidate_status],"excluded":[dict(item) for item in self.excluded],"ollama_cloud_available":self.ollama_cloud_available,"ollama_cloud_included":self.ollama_cloud_included,"max_seats":self.max_seats,"decision":self.decision,"reason":self.reason}

def _split(value: str) -> list[str]: return [item.strip().lower() for item in value.split(",") if item.strip()]

def _provider_routes(user_home: Path) -> list[dict[str, Any]]:
    settings = load_settings(user_home); result=[]
    for route in load_routes(user_home).get("routes", []):
        provider=str(route.get("provider") or "")
        if not route.get("enabled", False): continue
        if not settings.get("providers", {}).get(provider, {}).get("enabled", True): continue
        if bool(route.get("cloud", True)) and not settings.get("cloud", {}).get("enabled", False): continue
        result.append({**route, **static_status(route)})
    return result

def _coder_seats(user_home: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """Return every exact configured cloud model for coder families.

    When no exact model is known for a family, retain one generic provider seat
    so the runtime records an honest authentication/quota/model failure instead
    of silently omitting that family.
    """
    routes=_provider_routes(user_home); seats=[]; status=[]
    candidates=[
        item for item in provider_candidates(user_home,require_live=False,cloud_only=True)
        if item.get("provider") in CODER_PROVIDERS
    ]
    for provider in CODER_PROVIDERS:
        matching=[route for route in routes if route.get("provider")==provider]
        exact=[]
        for item in candidates:
            if item.get("provider") != provider: continue
            model=str(item.get("model") or "").strip()
            if not model or model.startswith("auto"): continue
            if model not in [row[0] for row in exact]: exact.append((model,item))
        if exact:
            for model,item in exact:
                seat=f"{provider}@{model}"
                seats.append(seat)
                status.append({
                    "seat":seat,"seat_type":"provider-model","provider":provider,
                    "route_id":item.get("route_id"),"model":model,"installed":True,
                    "live_ready":bool(item.get("live_ready")),
                    "status_basis":"fresh-live-receipt" if item.get("live_ready") else "configured-exact-model-unverified",
                    "cloud":True,
                })
            continue
        if not matching: continue
        best=sorted(matching,key=lambda row:int(row.get("priority",100)))[0]
        seats.append(provider); status.append({"seat":provider,"seat_type":"provider","provider":provider,"route_id":best.get("route_id"),"installed":bool(best.get("installed")),"live_ready":False,"status_basis":best.get("status_basis","static-only"),"cloud":bool(best.get("cloud",True))})
    return seats,status

def _ollama_cloud_seats(user_home: Path) -> tuple[list[str], list[dict[str, Any]]]:
    settings=load_settings(user_home)
    if not settings.get("cloud",{}).get("enabled",False) or not settings.get("providers",{}).get("ollama",{}).get("enabled",True): return [],[]
    routes=[route for route in _provider_routes(user_home) if route.get("provider")=="ollama" and route.get("cloud")]
    if not routes: return [],[]
    candidates=[item for item in provider_candidates(user_home,require_live=False,cloud_only=True) if item.get("provider")=="ollama" and item.get("cloud")]
    models=list(dict.fromkeys([str(item.get("model")) for item in candidates if item.get("model") and not str(item.get("model")).startswith("auto")]+discover_ollama_cloud_models()))
    if not models: models=["auto:cloud"]
    by_model={str(item.get("model")):item for item in candidates if item.get("model")}; seats=[]; status=[]
    for model in models:
        seat=f"ollama@{model}"; item=by_model.get(model,{})
        seats.append(seat); status.append({"seat":seat,"seat_type":"provider-model","provider":"ollama","route_id":item.get("route_id") or routes[0].get("route_id"),"model":model,"installed":bool(item.get("candidate_id") or routes[0].get("installed")),"live_ready":bool(item.get("live_ready")),"status_basis":"fresh-live-receipt" if item.get("live_ready") else "static-or-discovered","cloud":True})
    return seats,status

def _qualified_cloud_seats(user_home: Path) -> tuple[list[str], list[dict[str, Any]]]:
    candidates=provider_candidates(user_home,require_live=True,cloud_only=True); seats=[]; status=[]
    for item in candidates:
        model=str(item.get("model") or "")
        if not model or model.startswith("auto"): continue
        seat=f"{item.get('provider')}@{model}"
        if seat in seats: continue
        seats.append(seat); status.append({"seat":seat,"seat_type":"provider-model","provider":item.get("provider"),"route_id":item.get("route_id"),"model":model,"installed":True,"live_ready":True,"status_basis":"fresh-live-receipt","cloud":True})
    return seats,status

def _agent_candidates(user_home: Path, surface: str | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    records=list_agent_seats(user_home,surface=surface,reachable_only=False); seats=[]; status=[]
    for record in records:
        seats.append(record["seat"]); status.append({"seat":record["seat"],"seat_type":"agent","surface":record["surface"],"agent_id":record["agent_id"],"model":record.get("model_binding"),"live_ready":bool(record.get("reachable")),"risk_class":record.get("risk_class"),"status_basis":"agent-live-probe" if record.get("reachable") else "agent-registry-cache"})
    return seats,status

def _explicit_seats(selector: str, ollama: list[str], agents: dict[str,list[str]]) -> list[str]:
    output=[]
    for item in _split(selector):
        if item in OLLAMA_CLOUD_SELECTORS or item=="ollama": output.extend(ollama or ["ollama@auto:cloud"])
        elif item=="all-agents": output.extend(agents.get("all",[]))
        elif item.startswith("agents:"): output.extend(agents.get(item.split(":",1)[1],[]))
        else: output.append(item)
    return list(dict.fromkeys(output))

def resolve_meeting_seats(user_home: Path, selector: str="auto", *, exclude_ollama: bool=False, allow_missing_ollama: bool=False, max_seats: int|None=None) -> SeatPlan:
    normalized=(selector or "auto").strip().lower(); limit=int(max_seats or current().max_providers)
    if limit<1: raise ValueError("max_seats must be positive")
    coders,coder_status=_coder_seats(user_home); ollama,ollama_status=_ollama_cloud_seats(user_home); qualified,qualified_status=_qualified_cloud_seats(user_home)
    all_agents,all_agent_status=_agent_candidates(user_home); agent_map={"all":all_agents}; agent_status=list(all_agent_status)
    for surface in ("pmd","fcc","hid","healthlab","cws","dgx"):
        seats,records=_agent_candidates(user_home,surface); agent_map[surface]=seats; agent_status.extend(records)
    if normalized in ALL_QUALIFIED_SELECTORS: requested=list(qualified)
    elif normalized=="all-agents": requested=list(all_agents)
    elif normalized.startswith("agents:") and "," not in normalized and "+" not in normalized: requested=list(agent_map.get(normalized.split(":",1)[1],[]))
    elif normalized.startswith("all-coders+agents:"):
        surface=normalized.split(":",1)[1]; requested=[*coders,*ollama,*agent_map.get(surface,[])]
    elif normalized in ALL_WITH_OLLAMA_SELECTORS: requested=[*coders,*ollama]
    elif normalized in ALL_CODER_SELECTORS: requested=list(coders)
    elif normalized in OLLAMA_CLOUD_SELECTORS: requested=list(ollama)
    elif normalized=="auto":
        requested=[]; reserve=1 if ollama and not exclude_ollama else 0
        # Preserve provider-family diversity even when one provider exposes many exact models.
        seen_providers=set()
        for seat in coders:
            provider=seat.split("@",1)[0]
            if provider in seen_providers: continue
            if len(requested) >= max(0,limit-reserve): break
            requested.append(seat); seen_providers.add(provider)
        if ollama and not exclude_ollama:
            live=[row["seat"] for row in ollama_status if row.get("live_ready")]; requested.append((live or ollama)[0])
    else: requested=_explicit_seats(normalized,ollama,agent_map)
    requested=list(dict.fromkeys(requested)); ollama_available=bool(ollama)
    if exclude_ollama: requested=[seat for seat in requested if not seat.startswith("ollama@") and seat!="ollama"]
    contains_ollama=any(seat.startswith("ollama@") or seat=="ollama" for seat in requested)
    settings=load_settings(user_home); require_ollama=bool(settings.get("meeting",{}).get("require_ollama_cloud_when_available",True))
    if normalized in ALL_WITH_OLLAMA_SELECTORS and not ollama_available and not allow_missing_ollama:
        return SeatPlan(normalized,tuple(requested),(),tuple([*coder_status,*ollama_status,*qualified_status,*agent_status]),(),False,False,limit,"block","NO_OLLAMA_CLOUD_SEAT_DISCOVERED")
    literal=set(_split(normalized))
    if ollama_available and require_ollama and not contains_ollama and not exclude_ollama and set(CODER_PROVIDERS).issubset(literal):
        return SeatPlan(normalized,tuple(requested),(),tuple([*coder_status,*ollama_status,*qualified_status,*agent_status]),(),True,False,limit,"block","OLLAMA_CLOUD_FIRST_CLASS_SEAT_OMITTED")
    if not requested:
        return SeatPlan(normalized,(),(),tuple([*coder_status,*ollama_status,*qualified_status,*agent_status]),(),ollama_available,False,limit,"block","NO_ELIGIBLE_SEATS")
    if len(requested)>limit:
        return SeatPlan(normalized,tuple(requested),(),tuple([*coder_status,*ollama_status,*qualified_status,*agent_status]),tuple({"seat":seat,"reason":"edition-seat-limit"} for seat in requested[limit:]),ollama_available,contains_ollama,limit,"block",f"SEAT_LIMIT_EXCEEDED:{len(requested)}>{limit}")
    status_by={item["seat"]:item for item in [*coder_status,*ollama_status,*qualified_status,*agent_status]}
    candidates=[status_by.get(seat,{"seat":seat,"seat_type":"agent" if seat.startswith("agent:") else "provider","provider":seat.split("@",1)[0],"status_basis":"explicit"}) for seat in requested]
    return SeatPlan(normalized,tuple(requested),tuple(requested),tuple(candidates),(),ollama_available,contains_ollama,limit,"pass")
