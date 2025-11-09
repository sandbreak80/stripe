Centralized Billing & Entitlements Service (Stripe) — Requirements README

This document is a complete, implementation-ready specification for an AI agent (and humans) to design, build, test, and operate a reusable payments and access-control platform for a portfolio of micro-applications. It intentionally contains no source code. It defines scope, rationale, critical functionality, interaction patterns, architecture, data, security, operational requirements, quality gates, and acceptance criteria.

1. Executive Summary

Purpose: Provide a single, shared service that handles payments, subscriptions, and entitlements for 10–20 Python micro-applications. The service integrates with Stripe for one-time purchases and recurring subscriptions, maintains an authoritative record of who is entitled to which features in which project, and exposes a simple API for micro-apps to create checkouts and verify access. US-only, with no tax collection at launch.

Problem: Each micro-app recreating billing logic causes inconsistent user experiences, revenue leakage, maintenance burden, and security risk.

Solution: Centralize billing and entitlement logic into a dedicated service. Stripe remains the system of record for transactions; this service becomes the system of record for entitlements. Micro-apps delegate checkout and access checks to this service, which reduces code duplication and ensures consistent paywall behavior, self-serve billing, and clear observability.

Outcomes: Faster delivery of new micro-apps, consistent monetization across products, clean revenue reporting by project, and reliable access enforcement.

2. Scope and Non-Goals

In scope:

Payments and subscriptions using Stripe for US customers.

Unified checkout session creation and Stripe Customer Portal sessions.

Webhook ingestion from Stripe to reflect subscription and payment state.

Entitlement computation and retrieval per user and per project.

Support for both one-time purchases and recurring plans.

Simple administrative functions: manual grant or revoke of access, read-only reporting.

Shared integration approach for 10–20 projects with independent pricing and user bases.

Out of scope (initial release):

Merchant of record responsibilities, global tax handling, or VAT collection.

Complex metered billing or usage-based pricing.

Direct user authentication; each micro-app owns user identity and session management.

Fraud prevention beyond what Stripe provides.

Detailed BI dashboards; only essential metrics are required at launch.

3. Stakeholders and Actors

Business owner: Defines pricing, plans, and go-to-market for each micro-app.

Developers: Build micro-apps and integrate to monetize premium features via this service.

Billing service operators: Maintain the centralized service, configuration, environments, and webhooks.

End users (customers): Purchase one-time access or subscribe to plans tied to a specific project.

External system: Stripe (payments, checkout, customer portal, subscriptions, events, invoices/receipts).

4. Core Concepts and Rationale

Project: A logical container representing a single micro-application. Each project has its own products, prices, customers, and entitlements and is isolated for config and reporting.

Product: A sellable capability within a project (e.g., “Pro”, “Lifetime”). Maps to one or more Stripe prices.

Price: A commercial term for a product (monthly, yearly, one-time).

Entitlement: The effective access rights for a user in a project, derived from active subscriptions, valid one-time purchases, and manual grants. This is the source of truth that micro-apps check.

Why needed: Centralizing Stripe integration and entitlement logic yields a consistent paywall experience, reduces tech debt, prevents access after cancellations, and accelerates new micro-app launches.

5. High-Level System Overview

A centralized web service plus a small client integration used by each micro-app. Stripe provides hosted checkout and the billing portal; Stripe webhooks drive lifecycle updates. The service maintains a database of projects, catalog definitions, users, transactions, and computed entitlements. It exposes a minimal HTTP surface for creating checkout sessions, opening the billing portal, and retrieving entitlements. Webhooks are signature-verified, stored, processed idempotently, and used to recompute entitlements and invalidate caches. A scheduled job reconciles local records with Stripe to prevent drift.

6. Detailed Interaction Flows

6.1 User purchase via hosted checkout
• Micro-app requests a checkout session from the service with user id, project id, price id, mode (subscription or one-time), and success/cancel URLs.
• Service ensures a Stripe customer exists, creates a checkout session for that price, returns a redirect URL.
• User completes payment on Stripe and is redirected back to the micro-app.

6.2 Webhook-driven state update
• Stripe sends events (e.g., checkout session completed, invoice payment succeeded/failed, subscription created/updated/deleted, charge succeeded/refunded).
• Service verifies signature, stores the raw event for audit/idempotency, updates purchases/subscriptions, recomputes entitlements, and invalidates cache entries.

6.3 Entitlement check by a micro-app
• When a user signs in or accesses a gated feature, the micro-app requests the user’s entitlements for that project.
• Service returns feature list with active flags and validity. App gates UX and API calls accordingly.

6.4 Customer self-service
• Micro-app requests a billing portal session.
• Service returns a URL to Stripe’s customer portal for card updates, plan changes, cancellation, and invoice history.

6.5 Administrative override
• Authorized operators can grant or revoke entitlements manually. These appear as a separate source in entitlement computation and are fully auditable.

6.6 Reconciliation
• On a schedule, the service queries Stripe for recent subscription/payment changes, compares to local state, and corrects drift. Differences are logged and optionally alerted.

7. Functional Requirements

7.1 Payments and subscriptions
• Create hosted checkout sessions for one-time and recurring purchases.
• Maintain mapping between internal users and Stripe customers.
• Track subscription states: trialing, active, past due, canceled; store period end timestamps.
• Record one-time purchases including succeeded, failed, and refunded outcomes.

7.2 Catalog and pricing
• Maintain project-scoped products and prices.
• Prices support monthly, yearly, and one-time cadences.
• Project id and feature code metadata associate prices with entitlements.

7.3 Entitlements and access control
• Compute effective entitlements from subscriptions, one-time purchases, and manual overrides.
• Check entitlements by user and project; multiple features may be returned.
• Provide low-latency entitlement retrieval with cache; invalidate on relevant changes.

7.4 Webhook ingestion
• Verify Stripe signature before processing.
• Store raw events and ids for idempotent processing and audit trails.
• Replaying an event must not duplicate side effects.
• Support full subscription and payment lifecycle event set.

7.5 Administrative and operational
• Manual grant/revoke with audit trail.
• Basic metrics per project: active subs, high-level revenue indicators.
• Health, readiness, and liveness endpoints for orchestration.

7.6 Client integration
• Per-app credentials scoped to a project.
• Minimal endpoints: checkout session, portal session, entitlements, admin grant/revoke.
• Stable, versioned responses; changelog guidance for micro-app teams.

8. Non-Functional Requirements

Performance
• Entitlement retrieval: average < 100 ms from cache; < 300 ms from database.

Reliability
• Idempotent webhooks; resilient to retries and ordering.
• Nightly reconciliation to detect and resolve data drift.
• Graceful backlog recovery after transient outages.

Security
• TLS for all external surfaces.
• Stripe webhook signature verification required.
• Project-scoped credentials for micro-apps; least-privilege database roles.
• No secrets in logs; no raw card data ever stored.
• Administrative actions fully logged.

Scalability
• At least 20 projects, 50k total users, 10k active subscriptions without architecture changes.
• Stateless API replicas behind a reverse proxy/load balancer.

Maintainability
• Clear configuration per environment.
• Structured logging, metrics, and trace identifiers by default.

Compliance
• US-only payments at launch; no tax collection.
• Stripe receipts/invoices are authoritative.

9. System Architecture and Components

Service layer
• API gateway/authentication enforcing per-app credentials and project scoping.
• Payments module creating Stripe customers, checkout sessions, and portal sessions.
• Webhook processor verifying signatures, storing raw events, updating state, recomputing entitlements, invalidating caches.
• Entitlements engine merging subscription, purchase, and manual sources into efficient, denormalized entitlements.
• Caching layer serving recent entitlement responses.
• Administrative layer for manual adjustments and high-level metrics.

Data layer
• Relational database for projects, apps, users, Stripe customers, catalog items, prices, purchases, subscriptions, entitlements, and raw webhook events.
• Project scoping enforced at query boundaries for isolation.

External integrations
• Stripe REST and webhooks for checkout, billing portal, subscriptions, and payment lifecycle events.
• Optional integrations (future): Discord role assignment or other downstream systems can subscribe to internal “entitlement changed” events.

10. Data Model Overview (conceptual)

Projects: Logical micro-app containers, with active status and metadata.

Apps: Client integrations authorized to call the service, bound to one project and carrying a scoped credential.

Users: Provided by micro-apps’ identity; stored with an id and contact address for receipts.

Stripe customers: Mapping from internal users to Stripe customer ids.

Products and prices: The sellable catalog; prices link to products and carry cadence and currency; Stripe price ids bridge external and internal configuration.

Purchases: One-time payment records including status and Stripe payment intent ids.

Subscriptions: Recurring plan records including status and current period end timestamps; linked to Stripe subscription ids.

Entitlements: Flattened, fast-read permissions by user and project with feature codes, source attribution, and validity windows.

Webhook events: Stored raw Stripe event payloads with ids for audit and idempotency.

11. Entitlements Semantics

Source precedence: Effective entitlements are the union of all active sources. Subscription features derive from price metadata; one-time purchases grant lifetime or time-boxed access by configuration; manual grants can supersede or complement paid access and are explicitly labeled.

Validity: Entitlements include valid-from and valid-to timestamps. Lifetime access omits valid-to. Subscription entitlements use Stripe’s current period end and deactivate on cancellation or prolonged payment failure.

Consistency: Cache entries are invalidated on relevant webhook events. Given the same inputs, entitlement computation is deterministic.

12. External Interfaces (described without code)

Checkout session creation
Inputs: user id, project id, price id, mode (subscription or one-time), success and cancel URLs.
Output: hosted checkout URL for redirection.
Behavior: ensures Stripe customer exists, sets project and feature metadata, idempotent for repeated attempts.

Billing portal session
Inputs: user id.
Output: Stripe portal URL for plan changes, payment method updates, cancellations, and invoices.

Entitlement retrieval
Inputs: user id, project id.
Output: list of features with active status and validity.
Behavior: served from cache when fresh; falls back to database; invalidates cache upon relevant events.

Administrative grant or revoke
Inputs: user id, project id, feature code, optional validity.
Output: acknowledgment and updated effective state.
Constraints: only available to authorized operators; logged with actor and reason.

Health, readiness, and liveness
Purpose: orchestration and monitoring of process and dependencies.

Stripe webhook receiver
Inputs: signed event requests from Stripe.
Behavior: signature verification, raw event storage, idempotent processing, state update, entitlement recompute, cache invalidation, and observable outcomes.

13. Configuration and Environment Management

Environments: development, test, and production with distinct secrets.

Configuration includes database connection, cache location, Stripe keys, webhook secret, allowed origins, and per-app API credentials.

Administrative features and logging verbosity are configurable without redeployment.

14. Security Requirements

Transport security via HTTPS for all external endpoints.

Micro-app authentication with per-app secrets scoped to a single project; scheduled rotation and revocation procedures.

Authorization enforced by project scope for every request.

Stripe webhook verification using the configured signing secret; unverified requests are rejected.

Minimal data storage: no card data; store only Stripe ids and billing metadata necessary for entitlements.

Full audit trail for administrative actions and manual entitlement changes.

15. Observability and Operations

Logging: Structured logs with correlation id; no secret values or cardholder data; include contextual metadata on errors.

Metrics: Webhook processing lag and success rate, entitlement cache hit ratio, processed events total, active subscriptions per project.

Health checks: Liveness (process), readiness (dependencies), and overall health endpoints used by orchestration.

Reconciliation: Scheduled comparison of recent Stripe changes vs. local state with correction of drift.

Backups: Nightly database backups with retention and a documented restore process, including periodic restore tests.

Scaling: Stateless API replicas behind a proxy; cache and database sized to targets.

16. Performance Targets and SLOs

Entitlement retrieval: median < 100 ms; p95 < 300 ms.

Webhook processing: median end-to-end < 2 s per event in steady state; backlog recovery for 10,000 events < 10 minutes.

Availability: 99.9% monthly for public API surfaces, excluding planned maintenance.

17. Quality Gates and Acceptance Criteria

Build and test gates:

Linting, static type checks, unit and integration tests must pass.

Integration tests verify health endpoints, entitlement correctness, webhook idempotency with sample events.

Coverage thresholds for core entitlement logic and webhook processing are met.

Operational acceptance:

Health checks green in target environment.

Stripe webhook path reachable and signature verification confirmed.

Cache invalidation occurs on subscription change scenarios.

Manual overrides are auditable and reflected in retrieval responses.

Business acceptance:

Checkout and portal flows function for at least one project with at least two plans.

Revenue and active subscriber counts align with Stripe summaries.

Developer and operator documentation is complete and usable.

18. Risks and Mitigations

Stripe dependency: Degraded mode handling, retries with backoff, reconciliation after outages.

Data drift: Idempotent webhooks, durable raw event storage, scheduled reconciliation.

Security exposure: Secret rotation, least-privilege access, environment isolation, webhook signature verification.

Cache staleness: Event-driven invalidation, short TTLs, retrieval fallback to database.

19. Rollout Plan

Phase 1: Single project; one subscription plan and one one-time price; validate end-to-end flows.

Phase 2: Add more projects; enable manual grants; expose basic metrics; verify isolation.

Phase 3: Harden operations with reconciliation, dashboards, alerts; document integration for all micro-apps; scale to 10–20 projects.

20. Documentation Deliverables

Operator guide: Environment, secrets, deployment, backup/restore.

Developer guide: How micro-apps integrate, request/response formats, error handling, versioning policy.

Runbook: Incidents involving webhooks, drift, cache outages, Stripe disruptions.

Changelog: Versioned notes and migration instructions.

21. Success Metrics

Integration time: A new micro-app can monetize in under one day using the shared service.

Access consistency: < 1% entitlement discrepancies in periodic audits.

Reliability: ≤ 1 missed or failed webhook per 10,000 after retries, monthly.

Support load: Fewer billing-change tickets due to hosted portal use.

22. Glossary

Project: Distinct micro-application that uses the billing service.

Product: Sellable plan, feature set, or lifetime access within a project.

Price: Commercial term and cadence for a product (monthly, yearly, one-time).

Entitlement: Effective access permissions for a user in a project.

Checkout session: Hosted Stripe page for payment that creates a purchase or subscription.

Customer portal: Hosted Stripe page for payment methods, plan changes, cancellations, invoices.

Webhook: Signed event notification from Stripe describing payment or subscription changes.
