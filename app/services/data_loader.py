"""Load and cache all static JSON data at startup."""

import json
from pathlib import Path

from app.models.candidates import (
    Candidate,
    GovernmentPlan,
    PartyDetail,
    PartyListItem,
    PresidentialFormula,
)


class DataLoader:
    def __init__(self, data_dir: Path):
        self._candidates_raw: dict = {}
        self._positions_raw: dict = {}
        self._parties_by_id: dict[int, dict] = {}
        self._load(data_dir)

    def _load(self, data_dir: Path):
        # Load candidates
        candidates_path = data_dir / "candidatos_2026.json"
        with open(candidates_path, encoding="utf-8") as f:
            self._candidates_raw = json.load(f)

        # Index by id
        for p in self._candidates_raw["parties"]:
            self._parties_by_id[p["jne_id"]] = p

        # Load positions (used by candidate detail pages)
        positions_path = data_dir / "posiciones_candidatos.json"
        if positions_path.exists():
            with open(positions_path, encoding="utf-8") as f:
                self._positions_raw = json.load(f)

    def get_all_parties(self) -> list[PartyListItem]:
        result = []
        for p in self._candidates_raw["parties"]:
            pres = p["presidential_formula"].get("president") or {}
            result.append(
                PartyListItem(
                    id=p["jne_id"],
                    name=p["party_name"],
                    presidential_candidate=pres.get("full_name", ""),
                    photo_url=pres.get("photo_url"),
                )
            )
        return result

    def get_party_detail(self, party_id: int) -> PartyDetail | None:
        p = self._parties_by_id.get(party_id)
        if not p:
            return None

        formula = p["presidential_formula"]
        detail = PartyDetail(
            id=p["jne_id"],
            name=p["party_name"],
            presidential_formula=PresidentialFormula(
                president=_build_candidate(formula.get("president")),
                first_vice_president=_build_candidate(formula.get("first_vice_president")),
                second_vice_president=_build_candidate(formula.get("second_vice_president")),
            ),
            government_plan=_build_plan(p.get("government_plan")),
        )

        # Attach positions if available
        positions = self._positions_raw.get("parties", {})
        for _key, pos_data in positions.items():
            if pos_data.get("party_name") == p["party_name"]:
                detail.positions = pos_data.get("positions")
                break

        return detail

    def get_positions_data(self) -> dict:
        return self._positions_raw

    def get_candidates_raw(self) -> dict:
        return self._candidates_raw


def _build_candidate(raw: dict | None) -> Candidate | None:
    if not raw:
        return None
    return Candidate(
        full_name=raw.get("full_name", ""),
        position=raw.get("position", ""),
        document_number=raw.get("document_number"),
        status=raw.get("status"),
        photo_url=raw.get("photo_url"),
    )


def _build_plan(raw: dict | None) -> GovernmentPlan | None:
    if not raw:
        return None
    return GovernmentPlan(
        plan_id=raw.get("plan_id"),
        full_plan_url=raw.get("full_plan_url"),
        summary_plan_url=raw.get("summary_plan_url"),
    )
