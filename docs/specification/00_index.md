# Cortex QA Platform — Complete Technical Specification

**Version**: 2.0
**Date**: 2026-06-18
**Status**: Implementation-Ready

---

## Document Index

| # | Document | Purpose | Audience |
|---|---|---|---|
| 01 | [Product Requirements Document](01_PRD.md) | What to build and why | Product, Engineering, Stakeholders |
| 02 | [Technical Design Document](02_TDD.md) | How the system works end-to-end | Engineering Leads, Architects |
| 03 | [System Architecture Document](03_system_architecture.md) | Component structure, data flow, deployment | Architects, DevOps |
| 04 | [AI Agent Architecture Document](04_ai_agent_architecture.md) | Agent design, orchestration, safety | AI Engineers, Architects |
| 05 | [Domain Model Documentation](05_domain_model.md) | Business domains, entities, boundaries | All Engineers |
| 06 | [Class-Level Design Documentation](06_class_design.md) | Every class, method, interface | Implementing Engineers |
| 07 | [API Design Guidelines](07_api_design.md) | Internal interfaces, contracts, schemas | All Engineers |
| 08 | [Data Model Documentation](08_data_model.md) | Database schema, storage, audit trail | Backend Engineers, DBAs |
| 09 | [Infrastructure Documentation](09_infrastructure.md) | Deployment, containers, CI/CD, monitoring | DevOps, SRE |
| 10 | [Security Documentation](10_security.md) | Auth, secrets, audit-only enforcement, compliance | Security Engineers, Architects |
| 11 | [Developer Implementation Guide](11_developer_guide.md) | Conventions, patterns, step-by-step build order | All Engineers |
| 12 | [Coding Agent Instructions](12_coding_agent_instructions.md) | Unambiguous spec for autonomous coding agent | Coding Agents (Claude, Copilot) |

## Research Foundation

All design decisions are grounded in evidence from 7 research papers:

| Paper | Venue | Key Contribution |
|---|---|---|
| SAST-Genius | IEEE S&P 2025 | SAST+LLM hybrid pipeline, 91% FP reduction |
| RADAR | Meta Production (535K diffs) | Multi-stage funnel, risk scoring, production validation |
| QASecClaw | arXiv 2026 | Mission Orchestrator, fail-open safety, 88.6% FP reduction |
| Automated CR in Practice | ICSE 2025 | 73.8% resolution rate, precision > recall for trust |
| AgenticSCR | FSE 2026 | Detector-validator chain, semantic memory (+5.7%), agentic tool use |
| RevAgent | arXiv 2025 | Category-specific agents, critic = most impactful component |
| Rethinking Agentic CR | TOSEM/ICSE-JAWs 2026 | 5-stage lifecycle, reviewers as supervisory operators |
