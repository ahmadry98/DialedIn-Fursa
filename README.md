# ☕ DialedIn

### AI-Powered Espresso Companion

🌐 **Website:** https://www.dialedin.me/

DialedIn is a mobile espresso companion designed to help home baristas understand their shots, diagnose extraction problems, and make better dialing decisions.

Instead of relying only on trial and error, DialedIn combines **equipment profiles, shot parameters, taste feedback, media analysis, and AI-assisted conversation** to guide users toward better espresso.

---

## 🚀 Overview

Dialing in espresso can be difficult because many variables affect the final shot:

- Espresso machine and grinder
- Grind setting
- Coffee dose
- Roast and beans
- Extraction time
- Taste
- Preparation technique

DialedIn brings this information together through **DialChat**, an AI-assisted workflow that collects shot context and helps determine what the user should change for the next extraction.

Users can also provide shot media. The system can analyze audio extracted from espresso-shot videos to estimate extraction timing and use that information as additional context during shot analysis.

---

## ✨ Key Features

### 🤖 AI-Assisted Dialing

DialChat guides the user through the dialing process conversationally, collecting relevant shot information and identifying missing context before generating recommendations.

### 🎧 Audio Shot Analysis

Shot videos can be processed to estimate espresso extraction timing from machine audio, reducing the need to manually measure every stage of the extraction.

### ⚙️ Equipment Profiles

DialedIn maintains structured profiles for espresso machines and grinders, allowing the analysis system to use equipment-specific context.

### 📸 Media Support

Users can provide photos and videos as part of the shot-analysis workflow.

### ☁️ Cloud-Native Backend

DialedIn uses AWS services for media storage, equipment profiles, shot history, AI inference, and content delivery.

### 📊 Monitoring & Observability

Application and service metrics can be monitored using **Prometheus and Grafana**.

---

## 🔄 How It Works

```text
User starts DialChat
        │
        ▼
Selects espresso machine and grinder
        │
        ▼
Provides dose, grind setting and shot information
        │
        ▼
Adds taste feedback and optional media
        │
        ▼
Video / audio timing analysis
        │
        ▼
Shot context + equipment profiles
        │
        ▼
AI-assisted interpretation
        │
        ▼
Dialing recommendation
        │
        ▼
User adjusts the next shot
```

The goal is not simply to classify a shot as good or bad. DialedIn turns information from the current extraction into an **actionable adjustment for the next shot**.

---

## 🏗️ Architecture

DialedIn is built as a multi-service system connecting the mobile client, backend APIs, AI services, tool layer, cloud storage, and infrastructure.

```text
┌─────────────────────────────┐
│   React Native / Expo App   │
└──────────────┬──────────────┘
               │
          HTTPS / REST
               │
               ▼
┌─────────────────────────────┐
│       FastAPI Backend       │
│          DialChat           │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ AI / Agent   │  │ Espresso MCP │
│   Workflow   │  │    Tools     │
└──────┬───────┘  └──────┬───────┘
       │                  │
       └────────┬─────────┘
                │
      ┌─────────┼──────────┐
      │         │          │
      ▼         ▼          ▼
 AWS Bedrock   S3      DynamoDB
```

### Infrastructure

```text
Application Services
        │
        ▼
      Docker
        │
        ▼
    Kubernetes
        │
        ▼
AWS Infrastructure
        │
        ├── Terraform
        ├── S3
        ├── DynamoDB
        ├── CloudFront
        └── CloudWatch

CI/CD
  └── GitHub Actions

Observability
  ├── Prometheus
  └── Grafana
```

---

## 🛠️ Tech Stack

| Area | Technologies |
|---|---|
| **Mobile** | React Native, Expo, TypeScript |
| **Backend** | Python, FastAPI |
| **AI / Agents** | AWS Bedrock, LangGraph |
| **Tool Layer** | Espresso MCP |
| **Storage** | Amazon S3, DynamoDB |
| **Infrastructure** | AWS, Terraform |
| **Containers** | Docker, Kubernetes |
| **CI/CD** | GitHub Actions |
| **Monitoring** | Prometheus, Grafana |
| **CDN** | Amazon CloudFront |

---

## 🧠 AI & Recommendation Workflow

DialedIn separates conversational AI from the structured espresso logic used by the application.

DialChat gathers and interprets user context, while the tool layer exposes espresso-specific functionality and equipment information.

```text
Machine
   +
Grinder
   +
Grind Setting
   +
Dose
   +
Shot Timing
   +
Taste Feedback
   +
Media Analysis
   │
   ▼
Shot Context
   │
   ▼
Recommendation
```

This structure keeps espresso-specific operations separate from the conversational interface and makes the system easier to extend and test.

---

## 🎧 Shot Timing Analysis

When supported media is provided, DialedIn can use audio from the shot to help estimate extraction timing.

```text
Mobile App
    │
    ▼
Request Upload URL
    │
    ▼
Upload Media
    │
    ▼
Register Media
    │
    ▼
Audio / Timing Analysis
    │
    ▼
Timing Result
    │
    ▼
Shot Analysis
```

---

## ⚙️ Equipment Profiles

DialedIn uses structured machine and grinder profiles to provide equipment-specific context.

Trusted equipment profiles can be stored in **DynamoDB**, with reviewed data available as a development fallback.

The system also includes a candidate/review workflow for researching equipment that is not yet part of the trusted profile dataset.

This allows the equipment database to grow without automatically treating unverified information as trusted application data.

---

## ☁️ Cloud Architecture

DialedIn uses AWS services across the application architecture:

- **Amazon S3** — shot media and equipment images
- **Amazon DynamoDB** — persistent application and equipment data
- **AWS Bedrock** — foundation models used by AI workflows
- **Amazon CloudFront** — content delivery
- **CloudWatch** — infrastructure monitoring

Infrastructure is managed using **Terraform**.

---

## 🐳 Docker & Kubernetes

DialedIn services are containerized with Docker.

The local development environment can run application services and monitoring infrastructure using Docker Compose.

Kubernetes is used for cloud deployment, including application services, ingress configuration, and horizontal scaling.

---

## 🔁 CI/CD

**GitHub Actions** is used to automate deployment workflows for the containerized application and cloud environment.

---

## 📊 Observability

DialedIn includes application-level observability covering areas such as:

- Chat requests
- Shot-analysis requests
- Audio-analysis requests
- Media uploads
- MCP tool usage and errors
- HTTP request status and latency
- Equipment-profile research
- Service health

**Prometheus** collects application metrics and **Grafana** provides dashboards for monitoring them.

---

## 🧪 Testing

Automated tests cover important workflows including:

- Chat and shot-analysis behavior
- Equipment profile validation
- Media handling
- Audio analysis
- Tool integrations
- API behavior
- Recommendation workflows

The architecture keeps AI-assisted functionality surrounded by deterministic validation and testable application logic where possible.

---

## 📱 DialedIn Repositories

DialedIn is split across multiple repositories:

### `DialedIn-Fursa`
Backend services, AI workflows, espresso tools, infrastructure, deployment configuration, and shot-analysis system.

### `dialin-app`
React Native / Expo mobile application.

### `dialedin-landing`
Web and landing experience for DialedIn.

---

## 📂 Repository Structure

```text
DialedIn-Fursa/
│
├── services/
│   ├── agent/              # DialChat / FastAPI service
│   ├── espresso_mcp/       # Espresso-specific tool layer
│   └── frontend/           # Web interface
│
├── infra/
│   ├── terraform/          # AWS infrastructure
│   └── k8s/                # Kubernetes manifests
│
├── monitoring/             # Prometheus / Grafana
├── modeling/               # Analysis components
├── scripts/                # Development utilities
├── data/                   # Development data
├── docs/                   # Technical documentation
│
├── compose.yaml
└── README.md
```

---

## 🚀 Local Development

### Requirements

- Python 3
- Node.js
- Docker
- AWS CLI for AWS-backed functionality
- Terraform for cloud infrastructure

### Clone

```bash
git clone https://github.com/ahmadry98/DialedIn-Fursa.git
cd DialedIn-Fursa
```

### Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r services/agent/requirements.txt
python -m pip install -r services/espresso_mcp/requirements.txt
python -m pip install -r modeling/requirements.txt
```

### Run the Backend

```bash
python -m uvicorn services.agent.app:app --host 0.0.0.0 --port 8000
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### Docker Compose

```bash
cp .env.compose.example .env.compose
docker compose up --build
```

Stop the stack with:

```bash
docker compose down
```

---

## ☸️ Deployment

Kubernetes manifests are located under:

```text
infra/k8s/
```

AWS infrastructure definitions are located under:

```text
infra/terraform/
```

---

## 🔐 Configuration

Cloud credentials, model configuration, storage configuration, and environment-specific values should be supplied through environment variables or deployment secrets.

Example configuration is provided in:

```text
.env.compose.example
```

**Never commit AWS credentials, API keys, or production secrets.**

---

## 🗺️ Project Status

DialedIn is under active development.

Current development focuses on improving the mobile experience, espresso-shot analysis, equipment intelligence, cloud deployment, and reliability of the recommendation workflow.

---

## 👨‍💻 Author

**Ahmad Rayan**

Computer Science graduate from Tel Aviv University.

Interested in software engineering, backend systems, cloud infrastructure, and AI-powered applications.
