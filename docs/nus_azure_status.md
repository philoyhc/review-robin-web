# NUS Azure deployment status

**Status date:** 1 October 2026 (handoff revision 7)

This is the current infrastructure/deployment handoff for moving Review Robin Web into the NUS Azure landing zone. It records verified Azure state, the current responsibility split, and the remaining external blockers.

## Current architecture

Public ingress is designed as:

```text
Internet
  -> public IP 137.132.48.31
  -> NUS perimeter DNAT
  -> Application Gateway 10.9.0.196
  -> App Service Private Endpoint 10.9.0.132
  -> Review Robin Web
```

The Web App remains private-only. PostgreSQL and Key Vault are also private. App Service outbound traffic and the future runner's Internet-bound traffic are forced through the NUS network path via `10.0.0.38`.

## Completed / verified

- VNet expanded to `10.9.0.128/25`.
- Application Gateway subnet: `10.9.0.192/28`.
- GitHub runner subnet: `10.9.0.208/28`.
- The remaining two /28 blocks in the added /26 are intentionally reserved and not configured as subnets.
- App Service Plan and private Web App are provisioned.
- App Service Private Endpoint is at `10.9.0.132`.
- App Service regional VNet integration and Route All are enabled.
- PostgreSQL Flexible Server is provisioned privately; application database `reviewrobin` exists.
- Key Vault and its Private Endpoint are provisioned.
- Log Analytics and Application Insights are provisioned.
- Easy Auth v2 is enabled; NUS tenant admin consent for `openid`, `profile`, and `email` is complete.
- GitHub OIDC deployment identity exists and has Website Contributor on the Web App.
- Public IP `137.132.48.31` is provisioned.
- NUS DNAT to Application Gateway private frontend `10.9.0.196` is configured.
- Application Gateway is running and its backend pool targets `10.9.0.132`.
- Gateway-to-backend reachability is demonstrated: the default probe receives HTTP 404 rather than a network failure.
- Runner NSG `nsg-nrrw-prd-runner-01` exists with an explicit deny-all-inbound rule.
- Runner NIC `nic-nrrw-prd-runner-01` exists at private IP `10.9.0.212`, with no public IP.
- Project RBAC and subscription quota are sufficient to create the runner VM once a deployable SKU is available.

## Application Gateway work remaining

NUS IT provisioned the gateway frontend/backend plumbing but left application-specific listener and routing configuration to the project.

Generic defaults currently exist:

- HTTP listener on port 80;
- basic routing rule;
- no production hostname;
- no TLS certificate;
- default probe returning 404.

Project work still includes:

- production hostname;
- HTTPS listener and TLS certificate;
- production routing rule;
- backend HTTP settings / host-header handling for App Service;
- application-specific health probe, likely `/health`;
- end-to-end public ingress validation.

## External blocker 1 — runner VM regional capacity

The intended runner is a private Ubuntu self-hosted GitHub Actions runner inside `net-nrrw-prd-inte-runner-01`, used for deployment, Key Vault data-plane work, PostgreSQL administration/migrations, and related CI/CD.

The subscription has ample compute quota. However, actual VM deployment preflight in Southeast Asia has repeatedly failed with `SkuNotAvailable`.

Confirmed failures include:

- `Standard_B2ms`;
- `Standard_B2s_v2`;
- `Standard_D2as_v7`;
- `Standard_D2s_v3`.

On 22 September, Azure SKU metadata showed several ordinary 2-vCPU / 8-GiB sizes as nominally unrestricted, but real deployment still failed. This is therefore a regional capacity/allocation issue rather than project quota or RBAC.

**Current status:** NUS IT is waiting for Microsoft Support to advise on a deployable/approved SKU or capacity path. No further VM creation attempts are planned until that advice arrives.

## External blocker 2 — production domain / hostname

The production hostname is deliberately not being guessed or hard-coded.

NUS is considering this as an opportunity to rationalize naming across analogous citizen-developed applications. The decision affects:

- public DNS;
- TLS certificate issuance/binding;
- Application Gateway production HTTPS listener;
- hostname-specific routing;
- final public Easy Auth redirect URI;
- consistency for future related applications.

Until the NUS domain/hostname decision is made, the project should not finalize those public-facing values.

The default App Service `azurewebsites.net` hostname remains useful as a backend identity, but it is not a replacement for the production public DNS/TLS hostname in this architecture.

## Remaining project-side work after blockers clear

When a deployable runner SKU is available:

1. create the private Ubuntu runner VM;
2. register the self-hosted GitHub Actions runner;
3. verify outbound connectivity through the NUS firewall path;
4. validate private Key Vault access;
5. create the least-privilege PostgreSQL application role;
6. finalize/store production secrets;
7. set `NUS_DATABASE_URL`;
8. change `.github/workflows/deploy_nus.yml` from GitHub-hosted to the private self-hosted runner;
9. run migrations and test GitHub OIDC deployment.

When the production hostname is decided:

10. create/confirm public DNS;
11. obtain/configure the TLS certificate;
12. configure the production Application Gateway HTTPS listener and routing rule;
13. configure backend host-header behavior and health probe;
14. finalize the Easy Auth redirect URI;
15. deploy RRW;
16. perform end-to-end off-campus NUS sign-in and application testing.

## End target

**GitHub repository -> OIDC-authenticated deployment through an in-VNet runner -> private Azure Web App -> private PostgreSQL/Key Vault -> NUS public publishing path through Application Gateway -> NUS Entra sign-in -> usable Review Robin Web application.**
