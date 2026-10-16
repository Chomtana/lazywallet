# Sandbox: Anvil forks (Ethereum :8545, Avalanche :8546) + faucet (:8547). Build context: repo root.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git ca-certificates \
  && rm -rf /var/lib/apt/lists/*
ENV FOUNDRY_DIR=/opt/foundry PATH=/opt/foundry/bin:$PATH
RUN curl -L https://foundry.paradigm.xyz | bash && foundryup

WORKDIR /app
# forge deploys the SwapScheduler on start; build now so startup doesn't compile (needs the lib/ submodules).
COPY contracts contracts
RUN cd contracts && forge build

COPY anvil/pyproject.toml anvil/uv.lock anvil/
RUN uv sync --directory anvil --frozen --no-dev --no-install-project
COPY anvil anvil
RUN uv sync --directory anvil --frozen --no-dev

ENV BIND_HOST=0.0.0.0
EXPOSE 8545 8546 8547
CMD ["uv", "run", "--directory", "anvil", "--no-sync", "sandbox"]
