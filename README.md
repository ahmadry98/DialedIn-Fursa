# ☕ DialedIn

### AI-Powered Espresso Companion

DialedIn is a mobile espresso companion designed to help home baristas understand their shots and make better dialing decisions.

Instead of relying only on trial and error, DialedIn combines equipment information, shot parameters, taste feedback, media analysis, and AI-assisted conversation to guide users toward better espresso.

---

## 🚀 What DialedIn Does

DialedIn guides the user through an espresso shot using **DialChat**, an AI-assisted workflow that collects information such as:

- Espresso machine and grinder
- Grind setting
- Coffee dose
- Roast information
- Shot timing
- Taste feedback
- Photos and videos

When a shot video is provided, DialedIn can analyze the espresso machine's audio to estimate extraction timing.

The collected information is combined with equipment profiles and shot context to recommend what the user should adjust for the next extraction.

---

## ✨ Key Features

### 🤖 AI-Assisted Dialing
DialChat collects shot context conversationally and helps determine what information is still needed before providing a recommendation.

### 🎧 Audio Shot Analysis
Shot videos can be processed to estimate extraction timing from espresso-machine audio, reducing the need for manual timing.

### ⚙️ Equipment Profiles
Machine and grinder profiles provide equipment-specific context when analyzing shots and generating recommendations.

### 📸 Media Support
Users can provide photos, videos, and extracted audio as part of the shot-analysis workflow.

### ☁️ Cloud-Native Backend
DialedIn uses AWS services for media storage, equipment profiles, shot history, AI inference, and content delivery.

### 📊 Monitoring & Observability
The backend exposes application metrics that can be monitored using Prometheus and Grafana.

---

## 🏗️ System Architecture

DialedIn is built as a multi-service system connecting the mobile application, backend APIs, AI services, storage, and cloud infrastructure.

```text
React Native / Expo Mobile App
              │
              │ HTTPS / REST
              ▼
        FastAPI Backend
              │
       ┌──────┴──────┐
       │             │
       ▼             ▼
   DialChat      Espresso MCP
   AI Agent        Tools
       │             │
       └──────┬──────┘
              │
     ┌────────┼─────────┐
     ▼        ▼         ▼
 AWS Bedrock  S3     DynamoDB
     │
     ▼
 AI / Vision Analysis

Infrastructure
      │
      ├── Docker
      ├── Kubernetes
      ├── Terraform
      ├── GitHub Actions
      └── Prometheus / Grafana
