from __future__ import annotations

from typing import Any


def compose_named_training_parameters(
    model: Any,
    graph: Any,
) -> list[tuple[str, Any]]:
    """Return the production EMA/update order for model and graph-owned p1."""

    named: list[tuple[str, Any]] = []
    seen: set[int] = set()
    if hasattr(model, "named_parameters"):
        model_parameters = model.named_parameters()
    else:
        model_parameters = (
            (f"parameter_{index}", parameter)
            for index, parameter in enumerate(model.parameters())
        )
    for name, parameter in model_parameters:
        if id(parameter) not in seen:
            named.append((f"model.{name}", parameter))
            seen.add(id(parameter))
    graph_p1 = getattr(graph, "p1", None)
    if graph_p1 is not None and id(graph_p1) not in seen:
        named.append(("graph.p1", graph_p1))
    return named


def compose_training_parameters(model: Any, graph: Any) -> list[Any]:
    return [
        parameter
        for _, parameter in compose_named_training_parameters(model, graph)
    ]


def compose_optimizer_parameters(model: Any, graph: Any, noise: Any) -> list[Any]:
    """Build one deterministic optimizer parameter list with canonical graph p1 ownership.

    The host graph owns ``p1`` while the text-side v2 builder owns the same
    logical proposal parameter in full/global-p arms.  Including graph ``p1``
    exactly once when it is not already registered in the model makes optimizer
    membership explicit and comparable without adding a second copy.
    """

    parameters = compose_training_parameters(model, graph)
    seen = {id(parameter) for parameter in parameters}
    for parameter in noise.parameters():
        if id(parameter) not in seen:
            parameters.append(parameter)
            seen.add(id(parameter))
    return parameters
