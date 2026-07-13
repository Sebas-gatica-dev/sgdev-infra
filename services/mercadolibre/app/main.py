from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field


class Settings:
    database_url = os.getenv("DATABASE_URL", "")
    service_token = os.getenv("SERVICE_TOKEN", "")
    public_base_url = os.getenv("PUBLIC_BASE_URL", "https://sgdev.com.ar/mercadolibre").rstrip("/")
    mercadopago_access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    mercadopago_webhook_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")
    mercadopago_notification_url = os.getenv("MERCADOPAGO_NOTIFICATION_URL", "")
    mercadopago_api_base_url = os.getenv("MERCADOPAGO_API_BASE_URL", "https://api.mercadopago.com").rstrip("/")
    mercadolibre_client_id = os.getenv("MERCADOLIBRE_CLIENT_ID", "")
    mercadolibre_client_secret = os.getenv("MERCADOLIBRE_CLIENT_SECRET", "")
    mercadolibre_redirect_uri = os.getenv("MERCADOLIBRE_REDIRECT_URI", "")
    mercadolibre_auth_base_url = os.getenv("MERCADOLIBRE_AUTH_BASE_URL", "https://auth.mercadolibre.com.ar").rstrip("/")
    mercadolibre_api_base_url = os.getenv("MERCADOLIBRE_API_BASE_URL", "https://api.mercadolibre.com").rstrip("/")
    http_timeout_seconds = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))


settings = Settings()
app = FastAPI(title="SGDEV MercadoLibre API", version="0.1.0")


def json_clean(value: Any) -> Any:
    return json.loads(json.dumps(jsonable_encoder(value), default=str))


def drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [drop_none(item) for item in value]
    return value


def db_connect():
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def require_service_token(
    authorization: str | None = Header(default=None),
    x_sgdev_service_token: str | None = Header(default=None),
) -> None:
    if not settings.service_token:
        return

    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:]

    provided = x_sgdev_service_token or bearer
    if not provided or not secrets.compare_digest(provided, settings.service_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


def assert_mercadopago_configured() -> None:
    if not settings.mercadopago_access_token:
        raise HTTPException(status_code=503, detail="MERCADOPAGO_ACCESS_TOKEN is not configured")


def assert_mercadolibre_configured() -> None:
    if not settings.mercadolibre_client_id or not settings.mercadolibre_client_secret:
        raise HTTPException(status_code=503, detail="MercadoLibre OAuth credentials are not configured")


async def mp_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    assert_mercadopago_configured()
    headers = {"Authorization": f"Bearer {settings.mercadopago_access_token}"}
    async with httpx.AsyncClient(base_url=settings.mercadopago_api_base_url, timeout=settings.http_timeout_seconds) as client:
        response = await client.request(method, path, headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=safe_response(response))
    return response.json()


async def ml_form(path: str, data: dict[str, str]) -> dict[str, Any]:
    assert_mercadolibre_configured()
    async with httpx.AsyncClient(base_url=settings.mercadolibre_api_base_url, timeout=settings.http_timeout_seconds) as client:
        response = await client.post(path, data=data, headers={"accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=safe_response(response))
    return response.json()


def safe_response(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"status": response.status_code, "body": response.text[:1000]}


@app.on_event("startup")
def startup() -> None:
    if settings.database_url:
        init_schema()


def init_schema() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ml_oauth_tokens (
                id BIGSERIAL PRIMARY KEY,
                provider VARCHAR(60) NOT NULL,
                owner_key VARCHAR(160) NOT NULL,
                user_id VARCHAR(120),
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                scope TEXT,
                token_type VARCHAR(40),
                expires_at TIMESTAMPTZ,
                raw_response JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (provider, owner_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mp_payment_preferences (
                id BIGSERIAL PRIMARY KEY,
                preference_id VARCHAR(160) NOT NULL UNIQUE,
                external_reference VARCHAR(180),
                init_point TEXT,
                sandbox_init_point TEXT,
                request_json JSONB NOT NULL,
                response_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mp_subscription_plans (
                id BIGSERIAL PRIMARY KEY,
                provider_plan_id VARCHAR(180) NOT NULL UNIQUE,
                external_reference VARCHAR(180),
                status VARCHAR(80),
                request_json JSONB NOT NULL,
                response_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mp_subscriptions (
                id BIGSERIAL PRIMARY KEY,
                provider_subscription_id VARCHAR(180) NOT NULL UNIQUE,
                provider_plan_id VARCHAR(180),
                external_reference VARCHAR(180),
                payer_email VARCHAR(255),
                status VARCHAR(80),
                init_point TEXT,
                current_period_end TIMESTAMPTZ,
                request_json JSONB NOT NULL,
                response_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_webhook_events (
                id BIGSERIAL PRIMARY KEY,
                provider VARCHAR(60) NOT NULL,
                event_type VARCHAR(120),
                external_event_id VARCHAR(255),
                headers_json JSONB NOT NULL,
                payload_json JSONB NOT NULL,
                signature_valid BOOLEAN,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_webhook_events_unique
            ON provider_webhook_events(provider, external_event_id)
            WHERE external_event_id IS NOT NULL
            """
        )
        conn.commit()


class CheckoutItem(BaseModel):
    title: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    currency_id: str = "ARS"
    id: str | None = None
    description: str | None = None


class CheckoutPreferenceRequest(BaseModel):
    items: list[CheckoutItem] = Field(min_length=1)
    payer_email: str | None = None
    external_reference: str | None = None
    success_url: str | None = None
    failure_url: str | None = None
    pending_url: str | None = None
    notification_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_return: str | None = "approved"
    binary_mode: bool | None = None


class SubscriptionPlanRequest(BaseModel):
    reason: str
    amount: Decimal = Field(gt=0)
    back_url: str
    currency_id: str = "ARS"
    external_reference: str | None = None
    frequency: int = Field(default=1, gt=0)
    frequency_type: str = "months"
    repetitions: int | None = None
    billing_day: int | None = None
    billing_day_proportional: bool | None = None
    free_trial: dict[str, Any] | None = None
    payment_methods_allowed: dict[str, Any] | None = None


class SubscriptionRequest(BaseModel):
    payer_email: str
    reason: str | None = None
    provider_plan_id: str | None = None
    external_reference: str | None = None
    back_url: str | None = None
    status: str | None = "pending"
    auto_recurring: dict[str, Any] | None = None
    card_token_id: str | None = None


class OAuthExchangeRequest(BaseModel):
    code: str
    redirect_uri: str | None = None
    owner_key: str | None = None
    code_verifier: str | None = None


class OAuthRefreshRequest(BaseModel):
    refresh_token: str
    owner_key: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    db = "disabled"
    if settings.database_url:
        try:
            with db_connect() as conn:
                conn.execute("SELECT 1")
            db = "ok"
        except Exception:
            db = "error"
    return {"status": "ok", "database": db}


@app.post("/v1/payments/checkout/preferences", dependencies=[Depends(require_service_token)])
async def create_checkout_preference(request: CheckoutPreferenceRequest) -> dict[str, Any]:
    notification_url = request.notification_url or settings.mercadopago_notification_url or None
    back_urls = drop_none(
        {
            "success": request.success_url,
            "failure": request.failure_url,
            "pending": request.pending_url,
        }
    )
    payload = drop_none(
        {
            "items": [item.model_dump(mode="json", exclude_none=True) for item in request.items],
            "payer": {"email": request.payer_email} if request.payer_email else None,
            "external_reference": request.external_reference,
            "back_urls": back_urls if back_urls else None,
            "auto_return": request.auto_return if back_urls.get("success") else None,
            "notification_url": notification_url,
            "metadata": request.metadata or None,
            "binary_mode": request.binary_mode,
        }
    )
    response = await mp_request("POST", "/checkout/preferences", payload)

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO mp_payment_preferences
                (preference_id, external_reference, init_point, sandbox_init_point, request_json, response_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (preference_id) DO UPDATE SET
                external_reference = EXCLUDED.external_reference,
                init_point = EXCLUDED.init_point,
                sandbox_init_point = EXCLUDED.sandbox_init_point,
                request_json = EXCLUDED.request_json,
                response_json = EXCLUDED.response_json
            """,
            (
                response.get("id"),
                request.external_reference,
                response.get("init_point"),
                response.get("sandbox_init_point"),
                Jsonb(json_clean(payload)),
                Jsonb(json_clean(response)),
            ),
        )
        conn.commit()

    return {
        "provider": "mercadopago",
        "preference_id": response.get("id"),
        "external_reference": request.external_reference,
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
    }


@app.get("/v1/payments/checkout/preferences/{preference_id}", dependencies=[Depends(require_service_token)])
async def get_checkout_preference(preference_id: str) -> dict[str, Any]:
    return await mp_request("GET", f"/checkout/preferences/{preference_id}")


@app.post("/v1/payments/subscription-plans", dependencies=[Depends(require_service_token)])
async def create_subscription_plan(request: SubscriptionPlanRequest) -> dict[str, Any]:
    auto_recurring = drop_none(
        {
            "frequency": request.frequency,
            "frequency_type": request.frequency_type,
            "repetitions": request.repetitions,
            "billing_day": request.billing_day,
            "billing_day_proportional": request.billing_day_proportional,
            "transaction_amount": request.amount,
            "currency_id": request.currency_id,
            "free_trial": request.free_trial,
        }
    )
    payload = drop_none(
        {
            "reason": request.reason,
            "auto_recurring": auto_recurring,
            "payment_methods_allowed": request.payment_methods_allowed,
            "back_url": request.back_url,
            "external_reference": request.external_reference,
        }
    )
    response = await mp_request("POST", "/preapproval_plan", payload)

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO mp_subscription_plans
                (provider_plan_id, external_reference, status, request_json, response_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (provider_plan_id) DO UPDATE SET
                external_reference = EXCLUDED.external_reference,
                status = EXCLUDED.status,
                request_json = EXCLUDED.request_json,
                response_json = EXCLUDED.response_json
            """,
            (
                response.get("id"),
                request.external_reference,
                response.get("status"),
                Jsonb(json_clean(payload)),
                Jsonb(json_clean(response)),
            ),
        )
        conn.commit()

    return {
        "provider": "mercadopago",
        "provider_plan_id": response.get("id"),
        "external_reference": request.external_reference,
        "status": response.get("status"),
        "init_point": response.get("init_point"),
    }


@app.post("/v1/payments/subscriptions", dependencies=[Depends(require_service_token)])
async def create_subscription(request: SubscriptionRequest) -> dict[str, Any]:
    payload = drop_none(
        {
            "preapproval_plan_id": request.provider_plan_id,
            "reason": request.reason,
            "external_reference": request.external_reference,
            "payer_email": request.payer_email,
            "back_url": request.back_url,
            "status": request.status,
            "auto_recurring": request.auto_recurring,
            "card_token_id": request.card_token_id,
        }
    )
    response = await mp_request("POST", "/preapproval", payload)
    next_payment_date = parse_datetime(response.get("next_payment_date"))

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO mp_subscriptions
                (provider_subscription_id, provider_plan_id, external_reference, payer_email, status,
                 init_point, current_period_end, request_json, response_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider_subscription_id) DO UPDATE SET
                provider_plan_id = EXCLUDED.provider_plan_id,
                external_reference = EXCLUDED.external_reference,
                payer_email = EXCLUDED.payer_email,
                status = EXCLUDED.status,
                init_point = EXCLUDED.init_point,
                current_period_end = EXCLUDED.current_period_end,
                request_json = EXCLUDED.request_json,
                response_json = EXCLUDED.response_json
            """,
            (
                response.get("id"),
                request.provider_plan_id,
                request.external_reference,
                request.payer_email,
                response.get("status"),
                response.get("init_point"),
                next_payment_date,
                Jsonb(json_clean(payload)),
                Jsonb(json_clean(response)),
            ),
        )
        conn.commit()

    return {
        "provider": "mercadopago",
        "provider_subscription_id": response.get("id"),
        "provider_plan_id": request.provider_plan_id,
        "external_reference": request.external_reference,
        "status": response.get("status"),
        "init_point": response.get("init_point"),
        "current_period_end": next_payment_date.isoformat() if next_payment_date else None,
    }


@app.get("/v1/payments/subscriptions/{subscription_id}", dependencies=[Depends(require_service_token)])
async def get_subscription(subscription_id: str) -> dict[str, Any]:
    return await mp_request("GET", f"/preapproval/{subscription_id}")


@app.get("/v1/mercadolibre/oauth/authorize-url", dependencies=[Depends(require_service_token)])
def mercadolibre_authorize_url(
    state: str | None = None,
    redirect_uri: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
) -> dict[str, str]:
    if not settings.mercadolibre_client_id:
        raise HTTPException(status_code=503, detail="MERCADOLIBRE_CLIENT_ID is not configured")

    final_state = state or secrets.token_urlsafe(24)
    final_redirect_uri = redirect_uri or settings.mercadolibre_redirect_uri
    params = {
        "response_type": "code",
        "client_id": settings.mercadolibre_client_id,
        "state": final_state,
        "redirect_uri": final_redirect_uri,
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
    if code_challenge_method:
        params["code_challenge_method"] = code_challenge_method

    return {"url": f"{settings.mercadolibre_auth_base_url}/authorization?{urlencode(params)}", "state": final_state}


@app.get("/v1/mercadolibre/oauth/callback")
def mercadolibre_oauth_callback(code: str, state: str | None = None) -> dict[str, str | None]:
    return {
        "message": "Callback received. Exchange this code from an internal service with POST /v1/mercadolibre/oauth/exchange.",
        "code": code,
        "state": state,
    }


@app.post("/v1/mercadolibre/oauth/exchange", dependencies=[Depends(require_service_token)])
async def mercadolibre_oauth_exchange(request: OAuthExchangeRequest) -> dict[str, Any]:
    redirect_uri = request.redirect_uri or settings.mercadolibre_redirect_uri
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.mercadolibre_client_id,
        "client_secret": settings.mercadolibre_client_secret,
        "code": request.code,
        "redirect_uri": redirect_uri,
    }
    if request.code_verifier:
        data["code_verifier"] = request.code_verifier
    response = await ml_form("/oauth/token", data)
    owner_key = request.owner_key or str(response.get("user_id") or "default")
    save_oauth_token("mercadolibre", owner_key, response)
    return public_token_response(owner_key, response)


@app.post("/v1/mercadolibre/oauth/refresh", dependencies=[Depends(require_service_token)])
async def mercadolibre_oauth_refresh(request: OAuthRefreshRequest) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.mercadolibre_client_id,
        "client_secret": settings.mercadolibre_client_secret,
        "refresh_token": request.refresh_token,
    }
    response = await ml_form("/oauth/token", data)
    owner_key = request.owner_key or str(response.get("user_id") or "default")
    save_oauth_token("mercadolibre", owner_key, response)
    return public_token_response(owner_key, response)


@app.get("/v1/mercadolibre/users/me", dependencies=[Depends(require_service_token)])
async def mercadolibre_users_me(owner_key: str = "default") -> dict[str, Any]:
    token = load_oauth_token("mercadolibre", owner_key)
    async with httpx.AsyncClient(base_url=settings.mercadolibre_api_base_url, timeout=settings.http_timeout_seconds) as client:
        response = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=safe_response(response))
    return response.json()


@app.post("/webhooks/mercadopago")
async def mercadopago_webhook(request: Request) -> dict[str, Any]:
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    payload = await parse_json_body(body)
    event_type = request.query_params.get("type") or request.query_params.get("topic") or payload.get("type")
    data_id = request.query_params.get("data.id") or request.query_params.get("id") or nested(payload, "data", "id") or payload.get("id")
    external_event_id = data_id
    signature_valid = validate_mp_signature(headers, data_id)

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO provider_webhook_events
                (provider, event_type, external_event_id, headers_json, payload_json, signature_valid)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider, external_event_id) WHERE external_event_id IS NOT NULL DO NOTHING
            """,
            (
                "mercadopago",
                event_type,
                str(external_event_id) if external_event_id is not None else None,
                Jsonb(json_clean(headers)),
                Jsonb(json_clean(payload)),
                signature_valid,
            ),
        )
        conn.commit()

    return {"received": True, "event_type": event_type, "external_event_id": external_event_id}


@app.get("/v1/events", dependencies=[Depends(require_service_token)])
def list_events(provider: str = "mercadopago", limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT id, provider, event_type, external_event_id, signature_valid, received_at
            FROM provider_webhook_events
            WHERE provider = %s
            ORDER BY received_at DESC
            LIMIT %s
            """,
            (provider, limit),
        ).fetchall()
    return {"events": rows}


def save_oauth_token(provider: str, owner_key: str, response: dict[str, Any]) -> None:
    expires_in = response.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO ml_oauth_tokens
                (provider, owner_key, user_id, access_token, refresh_token, scope, token_type, expires_at, raw_response, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (provider, owner_key) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, ml_oauth_tokens.refresh_token),
                scope = EXCLUDED.scope,
                token_type = EXCLUDED.token_type,
                expires_at = EXCLUDED.expires_at,
                raw_response = EXCLUDED.raw_response,
                updated_at = NOW()
            """,
            (
                provider,
                owner_key,
                str(response.get("user_id")) if response.get("user_id") is not None else None,
                response["access_token"],
                response.get("refresh_token"),
                response.get("scope"),
                response.get("token_type"),
                expires_at,
                Jsonb(json_clean(response)),
            ),
        )
        conn.commit()


def load_oauth_token(provider: str, owner_key: str) -> str:
    with db_connect() as conn:
        row = conn.execute(
            "SELECT access_token FROM ml_oauth_tokens WHERE provider = %s AND owner_key = %s",
            (provider, owner_key),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="OAuth token not found for owner_key")
    return row["access_token"]


def public_token_response(owner_key: str, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "mercadolibre",
        "owner_key": owner_key,
        "user_id": response.get("user_id"),
        "token_type": response.get("token_type"),
        "expires_in": response.get("expires_in"),
        "scope": response.get("scope"),
        "has_refresh_token": bool(response.get("refresh_token")),
    }


async def parse_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": body.decode("utf-8", errors="replace")}


def validate_mp_signature(headers: dict[str, str], data_id: Any) -> bool | None:
    signature_header = headers.get("x-signature")
    if not settings.mercadopago_webhook_secret or not signature_header:
        return None

    parts = {
        key.strip(): value.strip()
        for key, value in (part.split("=", 1) for part in signature_header.split(",") if "=" in part)
    }
    timestamp = parts.get("ts")
    expected_signature = parts.get("v1")
    request_id = headers.get("x-request-id", "")
    if not timestamp or not expected_signature or data_id is None or not request_id:
        return False

    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(settings.mercadopago_webhook_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected_signature)


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
