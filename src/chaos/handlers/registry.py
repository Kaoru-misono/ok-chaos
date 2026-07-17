from __future__ import annotations

from src.chaos.handlers.system import (
    ChaosCraftHandler,
    CodexSearchHandler,
    DataCollectedHandler,
    ExpeditionUnlockedHandler,
    GoToChaosCoreHandler,
    MemoryEliminationHandler,
    MentalBreakdownHandler,
    NewDifficultyHandler,
    SafeConfirmDialogHandler,
    TreatmentApproveHandler,
    TreatmentMethodHandler,
    ZeroSystemHomeHandler,
)


def create_default_handlers() -> list[object]:
    # Order does not define behavior. Engine scores every handler and then applies
    # score + explicit priority, which keeps additions from silently stealing pages.
    return [
        ZeroSystemHomeHandler(),
        CodexSearchHandler(),
        MemoryEliminationHandler(),
        ChaosCraftHandler(),
        NewDifficultyHandler(),
        ExpeditionUnlockedHandler(),
        MentalBreakdownHandler(),
        TreatmentMethodHandler(),
        TreatmentApproveHandler(),
        GoToChaosCoreHandler(),
        DataCollectedHandler(),
        SafeConfirmDialogHandler(),
    ]
