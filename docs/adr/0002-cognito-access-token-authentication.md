# Authenticate API Requests with Cognito Access Tokens

All `/api/...` endpoints require a Cognito User Pool access token. The API validates the token signature against the User Pool JWKS, then verifies its issuer, expiration, `token_use` is `access`, and `client_id` matches the configured App Client. It returns `401` for a missing or invalid token. If Cognito's JWKS cannot be reached, the API returns `503` rather than treating valid credentials as invalid.

The verified `sub` claim is the User ID. This is the value that will own Tailoring Sessions when persistence is introduced. The API does not accept a client-supplied User ID.

The frontend uses Cognito Hosted UI and redirects after receiving a `401`; the API does not perform browser redirects. All authenticated users currently have the same permissions.

## Consequences

The application requires `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, and `COGNITO_APP_CLIENT_ID` at startup. No Cognito app-client secret is required because the API only validates bearer tokens; it does not sign users in or exchange authorization codes. FastAPI documentation and OpenAPI endpoints are disabled.
