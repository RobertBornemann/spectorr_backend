# Insights Backend — Asset Report Sentiment API

FastAPI backend powering the **Insights Pipeline for Asset Reports**, an AWS-based system that transforms raw analyst reports, investor feedback, and market commentary into **structured, governed AI insights**.

The backend provides clean APIs for portfolio sentiment analytics, confidence scoring, and explainable insights per asset.

---

## Overview

This service exposes RESTful endpoints that deliver:
- Aggregated **daily sentiment trends** per asset
- **Confidence scores** and contributing evidence
- Source traceability (doc → chunk → insight)
- Health and metrics endpoints for observability

The backend integrates directly with the data and processing pipeline (OCR → NLP → LLM), serving as the governed interface between AWS storage and the visual dashboard.

---

## Core Stack

| Layer | Technology |
|-------|-------------|
| Framework | **FastAPI** |
| ORM | **SQLModel / SQLAlchemy** |
| Database | **AWS RDS (PostgreSQL)** |
| Auth / Secrets | **AWS Secrets Manager** |
| Storage | **AWS S3 (curated data)** |
| Infra | **AWS Lambda / ECS Fargate / API Gateway** |
| Observability | **CloudWatch + OpenTelemetry** |

---

## API Endpoints (planned)

| Endpoint | Description |
|-----------|-------------|
| `GET /assets` | List available assets |
| `GET /assets/{id}/sentiment?from=&to=` | Retrieve sentiment trendline for an asset |
| `GET /assets/{id}/insight?day=` | Retrieve the daily LLM-generated market insight |
| `GET /health` | Health and version info |

---

## Governance & Explainability

Each insight record links back to its source:
