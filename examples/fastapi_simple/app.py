from __future__ import annotations

from asyncio import Lock
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from pydantic import BaseModel, Field

from dogwood import native


EXAMPLE_DIR = Path(__file__).resolve().parent
POLICY_SOURCE = (EXAMPLE_DIR / "policy.dw").read_text()
QUOTA_POLICY_SOURCE = (EXAMPLE_DIR / "quota_policy.dw").read_text()
SCHEMA_SOURCE = (EXAMPLE_DIR / "schema.cedarschema").read_text()
EVENT_SCHEMA_SOURCE = (EXAMPLE_DIR / "event.dwschema").read_text()


class AuthorizationRequest(BaseModel):
    user: str = Field(examples=["alice"])
    amount: int = Field(ge=0, examples=[20])
    resource: str = Field(default='Drupe::Gateway::"trading"')


class AuthorizationResponse(BaseModel):
    decision: str
    allowed: bool
    daily_limit: int = 50


class QuotaAuthorizationResponse(BaseModel):
    decision: str
    allowed: bool
    hourly_quota: int = 2


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    native.require_available()
    app.state.authorizer = native.NativeAuthorizer(
        POLICY_SOURCE,
        SCHEMA_SOURCE,
        EVENT_SCHEMA_SOURCE,
    )
    app.state.quota_authorizer = native.NativeAuthorizer(
        QUOTA_POLICY_SOURCE,
        SCHEMA_SOURCE,
        EVENT_SCHEMA_SOURCE,
    )
    app.state.authorizer_lock = Lock()
    app.state.quota_authorizer_lock = Lock()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Dogwood Native FastAPI Example", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"native": native.available()}

    @app.post("/authorize", response_model=AuthorizationResponse)
    async def authorize(request: AuthorizationRequest) -> AuthorizationResponse:
        # Dogwood authorizers are stateful and the PyO3 wrapper mutates the
        # underlying Rust authorizer on each decision, so serialize access.
        async with app.state.authorizer_lock:
            decision = app.state.authorizer.authorize_request(
                "Drupe::Action::Transfer",
                f'Drupe::OAuthUser::"{request.user}"',
                request.resource,
                {"amount": request.amount, "user": request.user},
            )

        return AuthorizationResponse(decision=decision, allowed=decision == "Allow")

    @app.post("/authorize/quota", response_model=QuotaAuthorizationResponse)
    async def authorize_quota(request: AuthorizationRequest) -> QuotaAuthorizationResponse:
        # Separate authorizer state keeps this quota example independent from
        # the dollar-volume endpoint above.
        async with app.state.quota_authorizer_lock:
            decision = app.state.quota_authorizer.authorize_request(
                "Drupe::Action::Transfer",
                f'Drupe::OAuthUser::"{request.user}"',
                request.resource,
                {"amount": request.amount, "user": request.user},
            )

        return QuotaAuthorizationResponse(decision=decision, allowed=decision == "Allow")

    return app


app = create_app()
