# Functional Specification

## Current scope

- Provide an HTTP health-check endpoint.

## Health endpoint

- `GET /health`
- Returns HTTP `200` and JSON body:
  - `status`: `"ok"`
  - `service`: `"review-robin-web"`
