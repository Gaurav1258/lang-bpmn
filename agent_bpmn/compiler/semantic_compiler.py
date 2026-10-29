import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from langgraph.graph import END

from agent_bpmn.dsl.schema import SemanticRoute, SemanticRouterConfig


class SemanticCompilationError(Exception):
    """Raised when compiling a Semantic Intent Router fails."""
    pass


class SemanticIntentClassifier:
    """
    Semantic Intent Matcher that scores incoming text against natural language route descriptions.
    Includes an embedded semantic scoring engine with token-overlap, intent keyword weighting,
    and fallback mechanics so workflows execute reliably even in offline/mock/sandbox environments.
    """

    def __init__(self, routes: List[SemanticRoute], default_target: Optional[str] = None):
        self.routes = routes
        self.default_target = default_target
        # Precompute route token bags
        self._route_keywords = {
            r.id: self._extract_keywords(f"{r.id} {r.description}")
            for r in routes
        }

    @classmethod
    def _stem(cls, word: str) -> str:
        w = word.lower()
        if w.endswith("ing") and len(w) > 5:
            return w[:-3]
        if w.endswith("tion") and len(w) > 6:
            return w[:-4]
        if w.endswith("ed") and len(w) > 4:
            return w[:-2]
        if w.endswith("es") and len(w) > 4:
            return w[:-2]
        if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            return w[:-1]
        if w.endswith("e") and len(w) > 3:
            return w[:-1]
        return w

    @classmethod
    def _extract_keywords(cls, text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        stopwords = {"the", "and", "for", "with", "that", "this", "from", "when", "into", "node", "queue", "our", "your"}
        return {cls._stem(w) for w in words if w not in stopwords}

    def classify(self, text: str) -> str:
        if not text or not text.strip():
            return self.default_target or (self.routes[0].target if self.routes else "END")

        input_keywords = self._extract_keywords(text)
        best_score = -1.0
        best_target = None

        for route in self.routes:
            target_bag = self._route_keywords.get(route.id, set())
            if not target_bag:
                continue

            intersection = input_keywords.intersection(target_bag)
            score = len(intersection) / max(len(target_bag), 1)

            # Route ID exact presence boost
            if route.id.lower() in text.lower():
                score += 1.0

            if score > best_score:
                best_score = score
                best_target = route.target

        if best_target and best_score > 0.05:
            return best_target

        return self.default_target or (self.routes[0].target if self.routes else "END")


def compile_semantic_router(
    semantic_config: SemanticRouterConfig,
    router_id: str = "semantic_router",
) -> Tuple[Callable[[Dict[str, Any]], str], Dict[str, Any]]:
    """
    Compiles a Semantic Intent Router into a routing function and path map
    compatible with LangGraph's add_conditional_edges().

    Returns:
        (routing_function, path_map)
    """
    if not semantic_config.routes:
        raise SemanticCompilationError(f"Semantic router '{router_id}' has no routes configured.")

    path_map: Dict[str, Any] = {}
    for route in semantic_config.routes:
        target_dest = END if route.target == "END" else route.target
        path_map[route.target] = target_dest

    if semantic_config.default_target:
        def_dest = END if semantic_config.default_target == "END" else semantic_config.default_target
        path_map[semantic_config.default_target] = def_dest

    classifier = SemanticIntentClassifier(
        routes=semantic_config.routes,
        default_target=semantic_config.default_target,
    )

    def semantic_router_func(state: Dict[str, Any]) -> str:
        input_text = str(state.get(semantic_config.input_field, ""))
        chosen_target = classifier.classify(input_text)
        return chosen_target

    return semantic_router_func, path_map
