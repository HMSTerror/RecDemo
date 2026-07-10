from __future__ import annotations

from typing import Any


def compose_optimizer_parameters(model: Any, graph: Any, noise: Any) -> list[Any]:
    """Build one deterministic optimizer parameter list with canonical graph p1 ownership.

    The host graph owns ``p1`` while the text-side v2 builder owns the same
    logical proposal parameter in full/global-p arms.  Including graph ``p1``
    exactly once when it is not already registered in the model makes optimizer
    membership explicit and comparable without adding a second copy.
    """

    parameters: list[Any] = []
    seen: set[int] = set()
    for parameter in model.parameters():
        if id(parameter) not in seen:
            parameters.append(parameter)
            seen.add(id(parameter))
    graph_p1 = getattr(graph, "p1", None)
    if graph_p1 is not None and id(graph_p1) not in seen:
        parameters.append(graph_p1)
        seen.add(id(graph_p1))
    for parameter in noise.parameters():
        if id(parameter) not in seen:
            parameters.append(parameter)
            seen.add(id(parameter))
    return parameters

