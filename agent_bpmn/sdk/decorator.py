import functools
import inspect
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Type,
    TypeVar,
    get_type_hints,
)
from pydantic import BaseModel

from agent_bpmn.sdk.models import DomainBlockContract, DomainBlockMetadata
from agent_bpmn.sdk.registry import CapabilityRegistry, registry as default_registry

F = TypeVar("F", bound=Callable[..., Any])


def domain_block(
    id: str,
    name: str,
    department: str,
    description: str,
    icon: str = "cpu",
    estimated_cost_usd: float = 0.0,
    p95_latency_ms: int = 0,
    tags: Optional[List[str]] = None,
    version: str = "1.0.0",
    registry: Optional[CapabilityRegistry] = None,
) -> Callable[[F], F]:
    """
    Developer SDK decorator to certify and publish an engineering capability as a
    Domain Block on the AgentBPMN canvas.

    Requirements:
    1. The decorated function must take exactly one primary input parameter annotated
       with a Pydantic `BaseModel` subclass.
    2. The return type annotation must be a Pydantic `BaseModel` subclass.
    3. The function can be either synchronous or asynchronous.
    """
    target_registry = registry if registry is not None else default_registry

    def decorator(fn: F) -> F:
        # 1. Signature introspection
        sig = inspect.signature(fn)
        type_hints = get_type_hints(fn)

        params = list(sig.parameters.values())
        if len(params) == 0:
            raise TypeError(
                f"Domain block '{id}' function '{fn.__name__}' must accept an input payload annotated with a Pydantic BaseModel."
            )

        # We inspect the first parameter (skipping 'self' or 'cls' if inside a class)
        first_param = params[0]
        if first_param.name in ("self", "cls") and len(params) > 1:
            first_param = params[1]

        input_type = type_hints.get(first_param.name)
        if input_type is None or not (isinstance(input_type, type) and issubclass(input_type, BaseModel)):
            raise TypeError(
                f"Domain block '{id}' parameter '{first_param.name}' must be annotated with a Pydantic BaseModel subclass. Got: {input_type}"
            )

        # 2. Return type introspection
        return_type = type_hints.get("return")
        if return_type is None or not (isinstance(return_type, type) and issubclass(return_type, BaseModel)):
            raise TypeError(
                f"Domain block '{id}' return type must be annotated with a Pydantic BaseModel subclass. Got: {return_type}"
            )

        # 3. Build contract & clean JSON schemas
        metadata = DomainBlockMetadata(
            id=id,
            name=name,
            department=department,
            description=description,
            icon=icon,
            estimated_cost_usd=estimated_cost_usd,
            p95_latency_ms=p95_latency_ms,
            tags=tags or [],
            version=version,
        )

        contract = DomainBlockContract(
            metadata=metadata,
            input_model_name=input_type.__name__,
            output_model_name=return_type.__name__,
            input_schema=input_type.model_json_schema(),
            output_schema=return_type.model_json_schema(),
        )

        # 4. Register with the Capability Registry
        target_registry.register(
            contract=contract,
            handler=fn,
            input_model=input_type,
            output_model=return_type,
        )

        # 5. Attach metadata directly to the function object for developer inspection
        setattr(fn, "__domain_block_contract__", contract)
        setattr(fn, "__domain_block_metadata__", metadata)
        setattr(fn, "__input_model__", input_type)
        setattr(fn, "__output_model__", return_type)

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if inspect.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            return fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        # Preserve the sync/async nature of the original function for direct caller
        chosen_wrapper = async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper
        setattr(chosen_wrapper, "__domain_block_contract__", contract)
        return chosen_wrapper  # type: ignore

    return decorator

