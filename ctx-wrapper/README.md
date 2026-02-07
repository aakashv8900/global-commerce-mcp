# CommerceSignal CTX Wrapper

TypeScript wrapper for registering CommerceSignal on [CTX Protocol](https://ctxprotocol.com) marketplace.

## Quick Start

```bash
# Install dependencies
npm install

# Build
npm run build

# Run (development)
npm run dev

# Run (production)
npm start
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `3000` |
| `PYTHON_BACKEND_URL` | Python API URL | `http://localhost:8000` |
| `CTX_ENABLED` | Enable CTX middleware | `false` |

## Deploying to CTX Protocol

### 1. Deploy Your Server
```bash
# Option A: Docker
docker-compose up -d

# Option B: Single service
npm run build && npm start
```

### 2. Register on CTX
1. Go to https://ctxprotocol.com/contribute
2. Select "MCP Tool"
3. Paste your endpoint: `https://your-server.com/mcp`
4. Tools will be auto-discovered

### 3. Set Pricing
- `analyze_product` → $0.01/call
- `compare_global_prices` → $0.005/call
- `detect_trending_products` → $0.008/call
- `forecast_demand` → $0.015/call

### 4. Stake & Go Live
Stake USDC as required and your tool goes live!

## Tools Available

| Tool | Description |
|------|-------------|
| `analyze_product` | Full product intelligence |
| `compare_global_prices` | Cross-platform arbitrage |
| `detect_trending_products` | Category trends |
| `analyze_seller` | Seller competition |
| `analyze_brand` | Brand health score |
| `forecast_demand` | ML demand prediction |
| `subscribe_alert` | Alert subscription |

## Architecture

```
CTX Platform → Express+CTX Middleware → MCP Handler → Python Backend → PostgreSQL
```
