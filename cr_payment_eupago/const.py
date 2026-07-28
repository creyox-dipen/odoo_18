# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

# =============================================================================
# euPago REST API — Base URLs
# Pattern: replace 'sandbox' with 'clientes' to switch to production.
# =============================================================================

# Old REST API (Body Auth) — used by Multibanco
SANDBOX_REST_URL = "https://sandbox.eupago.pt/clientes/rest_api"
PRODUCTION_REST_URL = "https://clientes.eupago.pt/clientes/rest_api"

# New API v1.02 (ApiKey Header Auth) — used by MB WAY and Credit Card
SANDBOX_API_URL = "https://sandbox.eupago.pt/api"
PRODUCTION_API_URL = "https://clientes.eupago.pt/api"

# =============================================================================
# API Versions
# =============================================================================
MBWAY_API_VERSION = "v1.02"
CC_API_VERSION = "v1.02"

# =============================================================================
# Endpoint paths (relative to their base URL)
# =============================================================================
ENDPOINT_MULTIBANCO = "/multibanco/create"
ENDPOINT_MBWAY = "/v1.02/mbway/create"
ENDPOINT_CC = "/v1.02/creditcard/create"
ENDPOINT_AUTH_TOKEN = "/api/auth/token"
ENDPOINT_MANAGEMENT_REFUND = "/management/v1.02/refund/{}"

# =============================================================================
# Provider codes — each payment method is a separate provider in Odoo
# =============================================================================
PROVIDER_CODE_MBREF = "eupago_mbref"
PROVIDER_CODE_MBWAY = "eupago_mbway"
PROVIDER_CODE_CC = "eupago_cc"

ALL_PROVIDER_CODES = {PROVIDER_CODE_MBREF, PROVIDER_CODE_MBWAY, PROVIDER_CODE_CC}

# =============================================================================
# Supported currencies — euPago is EUR-only
# =============================================================================
SUPPORTED_CURRENCIES = ["EUR"]

# =============================================================================
# Default payment method codes to activate when each provider is installed
# =============================================================================
DEFAULT_PAYMENT_METHOD_CODES_MBREF = {"multibanco"}
DEFAULT_PAYMENT_METHOD_CODES_MBWAY = {"mbway"}
DEFAULT_PAYMENT_METHOD_CODES_CC = {"card"}

# =============================================================================
# Webhook / Callback field names (Webhooks 1.0 — GET params)
# The 'identificador' field carries our internal self.reference
# =============================================================================
WEBHOOK_FIELD_REFERENCE = "identificador"  # our internal reference (self.reference)
WEBHOOK_FIELD_AMOUNT = "valor"  # paid amount
WEBHOOK_FIELD_TRANSACTION_ID = "transacao"  # euPago's internal transaction ID (TRID)
WEBHOOK_FIELD_MB_REFERENCE = "referencia"  # ATM reference number (Multibanco)
WEBHOOK_FIELD_ENTITY = "entidade"  # ATM entity (Multibanco)
WEBHOOK_FIELD_PAYMENT_METHOD = "mp"  # payment method code

# euPago payment method codes in webhook
EUPAGO_MP_MULTIBANCO = "PC:PT"
EUPAGO_MP_MBWAY = "MW:PT"
EUPAGO_MP_CC = "CC:PT"

# =============================================================================
# Response field names
# =============================================================================
# Multibanco create response fields
MB_RESP_SUCCESS = "sucesso"
MB_RESP_ENTITY = "entidade"
MB_RESP_REFERENCE = "referencia"
MB_RESP_AMOUNT = "valor"
MB_RESP_DEADLINE = "data_fim"
MB_RESP_STATUS_CODE = "estado"
MB_RESP_MESSAGE = "resposta"

# MB WAY / CC create response fields
MBWAY_RESP_STATUS = "transactionStatus"
MBWAY_RESP_TRANSACTION_ID = "transactionID"
MBWAY_RESP_REFERENCE = "reference"

# Credit Card specific
CC_RESP_REDIRECT_URL = "redirectUrl"

# =============================================================================
# Multibanco request field names (Body Auth)
# =============================================================================
MB_REQ_API_KEY = "chave"  # API Key (sent in body for old REST)
MB_REQ_AMOUNT = "valor"  # float amount
MB_REQ_IDENTIFIER = "id"  # our internal reference
MB_REQ_DEADLINE = "data_fim"  # YYYY-MM-DD
MB_REQ_ALLOW_MULTI = "per_dup"  # 0 = single payment, 1 = multiple

# =============================================================================
# MB WAY request field names (ApiKey Header Auth)
# =============================================================================
MBWAY_REQ_IDENTIFIER = "identifier"
MBWAY_REQ_AMOUNT_VALUE = "value"
MBWAY_REQ_AMOUNT_CURRENCY = "currency"
MBWAY_REQ_PHONE = "customerPhone"
MBWAY_REQ_COUNTRY_CODE = "countryCode"
MBWAY_DEFAULT_COUNTRY_CODE = "+351"  # Portugal

# =============================================================================
# Credit Card request field names (ApiKey Header Auth)
# =============================================================================
CC_REQ_IDENTIFIER = "identifier"
CC_REQ_SUCCESS_URL = "successUrl"
CC_REQ_FAIL_URL = "failUrl"
CC_REQ_BACK_URL = "backUrl"
CC_REQ_LANG = "lang"
CC_DEFAULT_LANG = "PT"

# =============================================================================
# Multibanco limits
# =============================================================================
MB_MIN_AMOUNT = 1.0  # EUR
MB_MAX_AMOUNT = 99999.0  # EUR

# Credit Card limit
CC_MAX_AMOUNT = 3999.0  # EUR

# MB WAY limit
MBWAY_MAX_AMOUNT = 99999.0  # EUR
