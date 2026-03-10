# Project Dossier: e-commerce-agent

## 1. One-Sentence Summary

An AI-powered, multi-agent e-commerce assistant that exposes the same product system through three different backends—direct SQL, REST APIs, and GraphQL—behind a FastAPI streaming service and a single comparison UI.

## 2. Executive Summary

This project is a Python-based, agentic e-commerce assistant built around FastAPI, LangChain/LangGraph, and OpenAI models. It provides three distinct agents:
- a **DB agent** that talks directly to a Microsoft SQL Server database,
- a **REST agent** that uses a REST API wrapped as MCP tools, and
- a **GraphQL agent** that uses GraphQL endpoints, also wrapped as tools.

The user interacts through a single-page, Tailwind-based HTML UI (`dpsk_bot.html`) that submits a natural-language question once and shows all three agents’ answers side by side. The FastAPI backend (`main.py`) exposes a single page route and a shared streaming endpoint that multiplexes to the chosen agent and returns streamed text tokens over HTTP. The agents themselves are created with LangChain’s `create_agent` and driven by `ChatOpenAI` models (`gpt-4` and `gpt-4o`), while tool integration is handled via LangChain’s SQL toolkit and custom MCP servers (`mcp_server.py`, `graph_mcp.py`, `graphQL_mcp.py`) that sit on top of the existing e-commerce REST and GraphQL services.

From a resume standpoint, this codebase demonstrates practical experience with multi-agent design, streaming UX, SQL Server integration, REST and GraphQL orchestration, and the MCP ecosystem. From an engineering standpoint, it is closer to a working prototype or internal demo than a fully production-hardened system, with some hard-coded credentials and minimal documentation, but it shows clear architectural intent and thoughtful tool design.

## 3. What Problem This Project Solves

- **Unified e-commerce assistant**: Allows a user to query and manage e-commerce data (products, suppliers, carts, orders, feedback, documents) using natural language.
- **Integration pattern comparison**: Makes it easy to **compare three integration approaches**—direct DB access, REST APIs, and GraphQL—by having each answer the same question in parallel.
- **Abstraction over complex backend**: Hides the details of the underlying SQL schema and HTTP/GraphQL APIs behind conversational agents and tools, so users do not need to know SQL, endpoint paths, or payload shapes.

Based on the UI text (“E-commerce Multi-Agent Comparison”) and the explicit division into DB / REST / GraphQL agents, a likely intent is to let engineers or stakeholders evaluate trade-offs between these integration styles in a concrete, interactive way.

## 4. Likely Users / Stakeholders

- **Backend / data engineers**: Exploring or validating how the e-commerce backend behaves via SQL, REST, and GraphQL, and how well an LLM can operate on top of each.
- **Solution architects / AI engineers**: Comparing agentic patterns and tool designs for enterprise e-commerce systems (SQL vs REST vs GraphQL, MCP-based integrations).
- **Business / operations staff (potentially)**: Getting insights like suppliers, inventory levels, and product information via natural language (though the implementation and UI text suggest engineers are the primary audience).

This inference is based on the architecture and UI copy; there is no explicit user-persona documentation in the repo.

## 5. What the System Actually Does

- **Serves a comparison chat UI**
  - `main.py` exposes `GET /` which serves `dpsk_bot.html`.
  - The page loads Tailwind CSS and Showdown.js, and defines three panels: **DB Agent**, **REST Agent**, and **GraphQL Agent**.
  - A single input box and “Ask all agents” button sends the same question to all three agents.

- **Streams responses from three agents**
  - `POST /stream/{agent_type}` in `main.py` accepts `agent_type` (`"db"`, `"rest"`, `"graphql"`) and a JSON body with `message` and `thread_id`.
  - For each request, it selects the appropriate `agent` object and calls `agent.astream(...)` with `stream_mode="messages"`, streaming out model tokens as they arrive.
  - The frontend uses the Fetch API and a `ReadableStream` to incrementally update each panel with markdown-rendered content.

- **DB agent (SQL Server)**
  - `db_agent.py` uses `SQLDatabase.from_uri` to connect to a **Microsoft SQL Server** `PRODUCT_DB` via pyodbc, with a connection string that includes username, password, host, and other parameters.
  - It builds a `SQLDatabaseToolkit` and prunes `QuerySQLCheckerTool` to simplify tool usage.
  - A detailed system prompt explains the e-commerce tables (`PRODUCT`, `SUPPLIER`, `PRODUCT_SUPPLIER`, `PRODUCT_INVENTORY`, `PRODUCT_CART`, `PRODUCT_FEEDBACK`, `DOCUMENT`, `PRODUCT_ORDERS`) and instructs the agent to:
    - inspect `INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS`,
    - limit results with `TOP`,
    - request only relevant columns,
    - and carefully handle SQL errors.
  - The agent is created with `ChatOpenAI(model="gpt-4", temperature=0)`.

- **REST agent**
  - `rest_agent.py` imports a large set of tools from `mcp_server.py` that wrap a REST e-commerce API at `http://192.168.210.100:6051`.
  - Tools include (non-exhaustive): `list_suppliers`, `get_product_detail`, `get_product_documents`, `get_cart_items`, `search_products`, `save_product`, `update_product`, `place_order`, `save_product_feedback`, `save_product_to_cart`, `remove_cart_item`.
  - A system prompt explains that the assistant can:
    - read/add/update products,
    - manage cart items,
    - place orders,
    - read suppliers,
    - add product feedback,
    - and informs users that the file-upload tool is currently not working.
  - The agent uses `ChatOpenAI(model="gpt-4o", temperature=0)` and LangChain’s `create_agent` with the above tools.

- **GraphQL agent**
  - `graphQL_agent.py` imports tools from `graph_mcp.py`, which targets a GraphQL endpoint at `http://192.168.210.100:6051/graphql`.
  - Tools cover capabilities similar to the REST agent: supplier listing, product search, detail retrieval, documents, cart operations, product CRUD, feedback, and order placement.
  - The system prompt explicitly says that:
    - the agent is a helpful e-commerce assistant,
    - it must use GraphQL tools for all data operations,
    - and outlines the supported capabilities in human-readable terms.
  - This agent also uses `ChatOpenAI(model="gpt-4o", temperature=0)` via `create_agent`.

- **MCP-based wrappers**
  - `mcp_server.py` uses `mcp.server.fastmcp.FastMCP` to expose REST endpoints as tools, handling both GET and POST (JSON and multipart) for the product API.
  - `graph_mcp.py` and `graphQL_mcp.py` implement different flavors of GraphQL MCP servers over the same backend, including advanced query/mutation mapping and input normalization for LLM-friendly usage.

- **Configuration and environment**
  - `.env` defines keys like `OPENAI_API_KEY`, LangSmith tracing settings, and `GRAPHQL_URL`.
  - `static/config.js` defines `window.API_BASE_URL = "http://127.0.0.1:8000";`, allowing the UI to connect to a configurable backend origin.

Note: several agent modules contain inline demo code that streams a sample query at import time, which is useful for local testing but would need to be disabled in a deployed service.

## 6. Technical Architecture

- **High-level architecture**
  - A **monolithic FastAPI application** (`main.py`) serves:
    - a static HTML/JS frontend for chat comparison, and
    - a single streaming route that fans out to three independent agents.
  - **Three agent backends** are implemented using LangChain + LangGraph:
    - **SQL agent** over MS SQL Server.
    - **REST agent** over an HTTP product API (wrapped via MCP).
    - **GraphQL agent** over a GraphQL endpoint (wrapped via MCP).
  - Agents call into either:
    - a direct database (`SQLDatabase`), or
    - **MCP servers** that mediate REST and GraphQL calls.

- **Frontend layer**
  - `dpsk_bot.html` is a static HTML file, styled via Tailwind CSS from a CDN.
  - It uses JavaScript to:
    - compute a `THREAD_ID` per browser session,
    - call `POST {API_BASE_URL}/stream/{agent_type}`,
    - process an HTTP streaming response via `ReadableStream`,
    - render incremental markdown using Showdown.js, and
    - maintain three separate content panels and status badges for the agents.

- **API/backend layer**
  - `FastAPI` app:
    - Configures CORS with `allow_origins=["*"]` (safe for demos, too permissive for production).
    - Mounts `/static` to serve static files (such as `config.js`).
    - Defines:
      - `GET /`: returns `dpsk_bot.html` as `HTMLResponse`.
      - `POST /stream/{agent_type}`: accepts a `QueryRequest` (Pydantic model) and streams responses as plain text.
  - The streaming endpoint:
    - maps `agent_type` to `db_agent`, `rest_agent`, or `graphql_agent`,
    - constructs a `config` dictionary with `thread_id` under `configurable`,
    - iterates over `agent.astream(..., stream_mode="messages")`,
    - filters events where `metadata["langgraph_node"] == "model"`,
    - extracts text from either string or list-of-blocks content, and
    - yields text chunks to `StreamingResponse`.

- **Agent layer**
  - Each agent module:
    - calls `load_dotenv()` to load `OPENAI_API_KEY` and related settings,
    - configures a `ChatOpenAI` model (gpt-4 / gpt-4o),
    - assembles a list of tools:
      - DB agent: SQL toolkit tools from `SQLDatabaseToolkit`.
      - REST agent: MCP REST tools from `mcp_server`.
      - GraphQL agent: MCP GraphQL tools from `graph_mcp`.
    - builds a LangChain `create_agent` with a purpose-specific system prompt.
  - `InMemorySaver` from `langgraph.checkpoint.memory` is instantiated but not wired up in the final `create_agent` calls (commented out), indicating experimentation with conversation state.

- **Tool / integration layer**
  - `mcp_server.py`:
    - wraps REST endpoints at `BASE_URL` (`PRODUCT_API_BASE_URL` or a default internal IP).
    - defines helpers `_get`, `_post_json`, and `_safe_json` to standardize HTTP behavior.
    - maps endpoints like:
      - `GET /api/Product/getSuppliersList`,
      - `GET /api/Product/getProductDetailById`,
      - `GET /api/Product/getDocumentListByProductId`,
      - `GET /api/Product/getCartItems`,
      - `POST /api/Product/getProductList`,
      - `POST /api/Product/saveProduct`,
      - `POST /api/Product/updateProduct`,
      - `POST /api/Product/placeOrder`,
      - `POST /api/Product/saveProductFeedback`,
      - `POST /api/Product/saveProductToCart`,
      - `POST /api/Product/removeCartItem`.
    - handles type-safe arguments for many tools (e.g. explicit parameter lists for `save_product` and `update_product`).
  - `graph_mcp.py`:
    - uses synchronous `requests` to talk to `GRAPHQL_URL` with an `ApiKey` header.
    - wraps multiple GraphQL queries and mutations into nicely named tools like:
      - `get_suppliers`, `get_product_by_id`, `search_products`, `get_cart_items`, `get_documents_by_product`,
      - `save_product`, `add_product_to_cart`, `submit_product_feedback`, `place_order`, `remove_cart_item`, `update_product`.
    - normalizes optional arguments and constructs GraphQL input objects that match the backend schema.
  - `graphQL_mcp.py`:
    - offers a more generic async GraphQL MCP server using `httpx`, with helpers to normalize LLM-friendly input dicts into schema-valid inputs (e.g. handling synonyms like `stock`, `supplier`, `supplierId`, etc.).
    - appears to be an alternative or experimental GraphQL MCP integration.

- **External dependencies**
  - **Database**: Microsoft SQL Server (`pyodbc`, connection string in `db_agent.py`).
  - **REST API**: E-commerce product API hosted at `http://192.168.210.100:6051`.
  - **GraphQL API**: Same host, `/graphql` endpoint, requiring an `ApiKey` header in `graph_mcp.py`.
  - **LLM provider**: OpenAI via `langchain-openai` with `OPENAI_API_KEY` loaded from `.env`.
  - **Observability**: LangSmith integration configured via `.env` (tracing + endpoint + project name).

## 7. Main Components

- **Entrypoint & web server**
  - `main.py`: FastAPI app definition, CORS config, static file serving, root HTML route, and `POST /stream/{agent_type}` streaming endpoint.

- **Agents**
  - `db_agent.py`: LangChain SQL agent backed by MS SQL Server (`SQLDatabaseToolkit`), with a detailed T-SQL-focused system prompt.
  - `rest_agent.py`: LangChain agent with tools imported from `mcp_server.py`, representing the REST API integration.
  - `graphQL_agent.py`: LangChain agent with tools imported from `graph_mcp.py`, representing the GraphQL integration.

- **Tool / integration modules**
  - `mcp_server.py`: FastMCP-based async MCP server wrapping the REST e-commerce API.
  - `graph_mcp.py`: FastMCP-based GraphQL MCP server using `requests`.
  - `graphQL_mcp.py`: Alternative async GraphQL MCP server using `httpx`, with more generic input handling.

- **Frontend / static assets**
  - `dpsk_bot.html`: main comparison UI with three side-by-side panels for DB, REST, and GraphQL agents, plus streaming JS logic.
  - `login.html`: a simple, Tailwind-based “Select a Chatbot” page that posts to `/select-agent` and redirects to `/chat`; this does **not** appear to be wired into the current FastAPI routes.
  - `static/config.js`: exposes `window.API_BASE_URL` for the frontend.

- **Configuration & environment**
  - `.env`: OpenAI key, LangSmith settings, and GraphQL URL (plus other potential secrets).
  - `requirements.txt`: pinned and semi-pinned dependencies, including FastAPI, LangChain, LangGraph, FastMCP, SQL Server, and observability libraries.

## 8. End-to-End Flow

### 8.1 User → Frontend → Backend

1. **User opens the app**
   - Browser loads `dpsk_bot.html` from `GET /`.
   - `config.js` sets `API_BASE_URL`, defaulting to `http://127.0.0.1:8000`.

2. **User submits a question**
   - User types a question (e.g., “Who are my suppliers?”) into the single input field.
   - On clicking “Ask all agents”, the JS handler:
     - clears the previous outputs,
     - shows a “Thinking…” typing animation in each panel,
     - sets each agent’s status badge to “Streaming…”.

3. **Frontend sends three parallel requests**
   - For each agent type (`"db"`, `"rest"`, `"graphql"`), the frontend calls:
     - `POST {API_BASE_URL}/stream/{agent_type}` with JSON body:
       ```json
       {
         "message": "<user question>",
         "thread_id": "<thread id>"
       }
       ```
   - These requests are fired in parallel so all three agents respond concurrently.

### 8.2 Backend streaming flow

4. **FastAPI route `chat_stream` handles the request**
   - Deserializes `QueryRequest` (Pydantic model).
   - Selects the agent via `get_agent(agent_type)`.
   - Builds a LangGraph config containing `thread_id`.

5. **Agent streaming**
   - Calls `agent.astream({"messages": [("user", req.message)]}, config=config, stream_mode="messages")`.
   - Asynchronous generator yields `(token, metadata)` pairs.
   - The code filters events where `metadata["langgraph_node"] == "model"`, ignoring tool-calling or other internal nodes.
   - Each `token`’s content is inspected:
     - If it is a list of blocks, find `{"type": "text"}` blocks and yield `block["text"]`.
     - If it is a string, yield the string directly.

6. **HTTP streaming to client**
   - `StreamingResponse` yields text chunks as the agent generates them.
   - On the client side:
     - `ReadableStream` is consumed with a `TextDecoder`.
     - Text is appended to a `fullText` buffer.
     - Each time new text arrives, the panel’s HTML is updated via `converter.makeHtml(fullText)` (Showdown markdown → HTML).
     - The panel scrolls to the bottom for a live-streaming effect.

7. **Completion**
   - When the stream ends, the status badge returns to “Idle”.
   - If no text was returned, the panel shows “No response.”
   - If any network or server error occurs, the user sees a small red error message and the badge goes to “Error.”

### 8.3 Data layer flow (per agent type)

- **DB agent**
  - LangChain SQL tools issue T-SQL queries over pyodbc to the `PRODUCT_DB`.
  - The model constructs queries using schema introspection (`INFORMATION_SCHEMA`) and returns summarized, structured answers.

- **REST agent**
  - MCP tools in `mcp_server.py` call the REST API via `httpx`:
    - GETs for suppliers, product details, documents, cart items.
    - POST JSON bodies for product search, product save/update, order placement, feedback, and cart changes.
  - `_safe_json` is used to normalize responses and handle cases with empty or non-JSON bodies.

- **GraphQL agent**
  - `graph_mcp.py` or `graphQL_mcp.py` tools construct queries/mutations and post them to the GraphQL endpoint.
  - They translate agent-level parameters into GraphQL input objects consistent with the backend schema and parse JSON responses.

## 9. Tech Stack

- **Languages**
  - Python 3 (backend, agents, MCP servers).
  - HTML + JavaScript (frontend).

- **Web framework**
  - FastAPI (HTTP server, routing, streaming responses).
  - Uvicorn (ASGI server, via `uvicorn` dependency).

- **LLM & orchestration**
  - OpenAI GPT models via `langchain-openai` (`ChatOpenAI`, models: `gpt-4`, `gpt-4o`).
  - LangChain (agents, SQL toolkit).
  - LangGraph (streaming, checkpoint support via `InMemorySaver`).
  - FastMCP + MCP (`mcp.server.fastmcp.FastMCP`) for tool-based integrations.

- **Data & integration**
  - Microsoft SQL Server (`pyodbc`, `SQLDatabase.from_uri`) for the `PRODUCT_DB`.
  - Product REST API at `http://192.168.210.100:6051` (e.g. `/api/Product/...` endpoints).
  - GraphQL API at `http://192.168.210.100:6051/graphql`.

- **Frontend / UI**
  - Tailwind CSS (CDN) for styling.
  - Showdown.js for markdown-to-HTML rendering.

- **Config / observability**
  - `python-dotenv` for `.env` loading.
  - LangSmith (`LANGSMITH_*` environment variables) for tracing and observability.

## 10. Notable Engineering Decisions

- **Three integration patterns side by side**
  - Explicitly implements DB, REST, and GraphQL integrations for the same domain, which is a very intentional way to compare architectural trade-offs using a single UI and API surface.

- **Agent- and tool-first design**
  - Uses LangChain agents with tools that hide backend complexity:
    - SQL tools abstract away raw T-SQL queries while still keeping them visible to the LLM.
    - MCP tools provide typed, semantically precise operations (e.g. `save_product`, `place_order`, `save_product_feedback`).

- **Streaming-first UX**
  - Backend and frontend are both designed for streaming:
    - `StreamingResponse` with an async token generator on the server.
    - Readable stream + incremental markdown rendering on the client.
  - This demonstrates understanding of low-latency conversational UX.

- **Careful GraphQL integration**
  - GraphQL wrappers handle:
    - building nested input objects (`productAdvanceSearchInput`, `productInput`, etc.),
    - ensuring only non-`None` fields are sent,
    - aligning with backend schemas for queries and mutations.

- **Input normalization for LLMs (in experimental GraphQL MCP)**
  - `graphQL_mcp.py` includes logic to normalize LLM-produced field names (e.g. `stock` → `availableStock`, `supplier` → `supplierIds`) and enforce validation rules before hitting the backend, which is a mature approach to tool robustness.

## 11. Evidence of Production Readiness

**Positive signals**
- Uses FastAPI with CORS middleware and a clear separation between static assets and API routes.
- Employs environment variables and `.env` files for configuration (OpenAI keys, LangSmith settings, GraphQL URL).
- Wraps external APIs and the database in well-typed tools with docstrings and validation logic (especially in MCP and GraphQL wrappers).
- Integrates LangSmith tracing, which suggests attention to observability.

**Gaps / prototype indicators**
- Sensitive data:
  - Hard-coded SQL Server connection string with credentials and security flags directly in `db_agent.py`.
  - Real-looking API and tracing keys are checked into `.env`.
- No tests or CI configuration found in the repo.
- README is the default GitLab template and does not document how to run or deploy the system.
- Some modules contain demo code that executes on import (e.g. streaming example calls), which would be undesirable in a production service.
- CORS is fully open, and there is no authentication or authorization around the chat endpoint.

Overall, this looks like a **functioning internal prototype or demo system**, not yet hardened for external production use.

## 12. Challenges the Developer Likely Had to Solve

- **Mapping business operations to tools**
  - Translating complex e-commerce operations (search with many filters, cart management, order placement, feedback) into LLM-friendly tool signatures with precise docstrings and validation.

- **Surface consistency across DB / REST / GraphQL**
  - Ensuring the three backends expose similar capabilities despite very different mechanics:
    - SQL query composition and schema discovery.
    - REST endpoints and JSON bodies.
    - GraphQL queries, mutations, and input types.

- **Handling partial / ambiguous user requests**
  - Designing prompts so that agents can ask follow-up questions (e.g., when adding a product or placing an order) rather than blindly guessing missing fields.

- **Streaming integration**
  - Dealing with LangGraph’s streaming format (`langgraph_node`, block-based content) and converting it into a clean text stream over HTTP and a markdown-rendered UI.

- **GraphQL schema friction**
  - Getting advanced search and product CRUD operations working through GraphQL, including input shapes like `productAdvanceSearchInput`, `productInput`, `productCartInput`, and `productOrderInput`.

- **Robustness against LLM “creative” payloads**
  - In the experimental GraphQL MCP module, normalizing LLM outputs (aliases, missing fields, incorrect types) into valid GraphQL inputs likely required iterative debugging with real model behavior.

## 13. What Makes This Project Strong on a Resume

- **Multi-agent architecture**: Demonstrates the ability to design and implement multiple agents over different backends (DB, REST, GraphQL) with a unified UX.
- **Practical e-commerce integration**: Connects directly to a realistic e-commerce backend: MS SQL Server, REST API, and GraphQL API, not just toy examples.
- **Modern LLM tooling**: Uses LangChain, LangGraph, MCP, and OpenAI GPT-4/4o with streaming and tool usage.
- **Tool and schema engineering**: Shows thoughtful design of tools with strict schemas, validation, and input normalization for reliability.
- **Full-stack skills**: Combines backend engineering (FastAPI, SQL Server, HTTP/GraphQL clients) with frontend UX for streaming chat (Tailwind, Showdown, streaming fetch).

## 14. Limitations or Gaps

- **Security & secrets**
  - Secrets (OpenAI keys, LangSmith keys, DB credentials) are present in the repository and in code.
  - Database connection uses `Encrypt=no` and `TrustServerCertificate=yes`, which is not ideal for production.

- **Documentation**
  - README is not customized; there are no clear setup, run, or deployment instructions.

- **Testing & reliability**
  - No automated tests, health checks, or retry logic for external APIs.
  - No structured logging or monitoring beyond LangSmith tracing.

- **Code hygiene**
  - Demo streaming loops inside agent modules run at import-time; these should be gated behind `if __name__ == "__main__":` for clarity.
  - Two different GraphQL MCP implementations exist (`graph_mcp.py`, `graphQL_mcp.py`), and it is not immediately obvious which one is canonical.

- **Auth / access control**
  - No authentication or rate limiting on the public streaming endpoint, and CORS is wide open.

## 15. Best Future Improvements

- **Security & configuration**
  - Move all secrets into a secure secret manager and scrub them from the repo.
  - Parameterize the SQL connection string and external API URLs via environment or configuration files, not hard-coded values.
  - Enable TLS and enforce secure DB connection parameters.

- **Production hardening**
  - Add authentication (e.g., API keys, OAuth, SSO) and rate limiting for the chat endpoint.
  - Introduce structured logging, metrics, and error-reporting (e.g., via OpenTelemetry).
  - Add retry policies and clearer error handling around REST and GraphQL calls.

- **Code quality**
  - Refactor demo code into separate scripts or notebooks and keep library modules side-effect-free at import.
  - Consolidate GraphQL MCP implementations into a single, well-documented module.
  - Add unit and integration tests, especially around tool payloads and external API contracts.

- **User experience**
  - Connect `login.html` to FastAPI (or remove it) and potentially support selecting a single agent or orchestrating between them.
  - Enhance the UI to show structured data (tables for products, carts, orders) alongside natural-language summaries.

## 16. Recruiter-Friendly Summary

This project is a **multi-agent e-commerce assistant** that lets users ask natural-language questions and perform operations (like viewing inventory, managing carts, and placing orders) against a real e-commerce backend. It showcases:
- a **FastAPI** backend with **LLM-powered agents** built on **LangChain/LangGraph**,
- integrations with **SQL Server, REST APIs, and GraphQL**,
- and a **streaming comparison UI** that displays the output of all three agents side by side.

It’s a strong demonstration of end-to-end AI application development—covering data access, tool and schema design, streaming UX, and practical deployment concerns like configuration and observability.

## 17. Deep Technical Summary

At its core, the system is a FastAPI application (`main.py`) that serves a single HTML page and a streaming endpoint. The HTML page (`dpsk_bot.html`) is a Tailwind-based, mobile-friendly UI that manages three independent result panels and uses Fetch + streams to consume text responses incrementally. The streaming endpoint uses LangGraph’s `astream` interface to send only the language-model-generated text, filtering out intermediary tool events and preserving a clean, line-oriented token stream.

Three LangChain agents back this endpoint:
- The **DB agent** uses `SQLDatabaseToolkit` to introspect a SQL Server `PRODUCT_DB` and answer questions via T-SQL. Its system prompt encodes domain knowledge about core tables like `PRODUCT`, `SUPPLIER`, `PRODUCT_CART`, etc., enforcing query best practices (limit results, select only needed columns, inspect schema first).
- The **REST agent** uses a FastMCP server (`mcp_server.py`) to wrap a .NET-like REST API at `http://192.168.210.100:6051`. The MCP layer translates human-friendly tool calls (e.g., `save_product`, `place_order`) into HTTP requests with correctly shaped JSON payloads, normalizing responses with `_safe_json`.
- The **GraphQL agent** uses a GraphQL MCP server (`graph_mcp.py` or the more advanced `graphQL_mcp.py`) to map GraphQL queries and mutations like `getProductList`, `saveProduct`, and `placeOrder` into tool calls. It carefully constructs input objects, strips `None` fields, and provides docstrings that align with the backend schema.

The system is wired for observability via LangSmith and uses `.env` for configuration, although secrets are currently in-repo. While not fully production-ready, the code demonstrates solid patterns for building LLM-powered agents on top of existing enterprise systems, and highlights the complexities of integrating SQL, REST, and GraphQL backends into a unified conversational interface.

## 18. FAQ for Another AI Assistant

1. **Q:** What is the primary goal of this project?  
   **A:** To provide a single conversational interface that can query and manipulate an e-commerce system via three different backends—SQL, REST, and GraphQL—and to compare how those approaches behave side by side.

2. **Q:** Where does the HTTP server start, and what routes matter?  
   **A:** `main.py` defines the FastAPI app. The key routes are `GET /` (serves `dpsk_bot.html`) and `POST /stream/{agent_type}` (accepts a message and thread ID and streams responses from the chosen agent).

3. **Q:** How do I select which agent to use when calling the backend?  
   **A:** Use the `agent_type` path parameter in `POST /stream/{agent_type}`, which must be `"db"`, `"rest"`, or `"graphql"`. The frontend already sends three separate requests, one for each.

4. **Q:** How does streaming work from the model to the browser?  
   **A:** LangGraph’s `agent.astream(..., stream_mode="messages")` yields `(token, metadata)` pairs. The backend filters events where `langgraph_node == "model"` and yields text to `StreamingResponse`. The browser then reads the HTTP stream chunk-by-chunk and renders markdown into HTML.

5. **Q:** What database does the DB agent connect to, and how?  
   **A:** It connects to a Microsoft SQL Server `PRODUCT_DB` via a pyodbc connection string in `db_agent.py`, using LangChain’s `SQLDatabase` and `SQLDatabaseToolkit` to expose SQL tools to the LLM.

6. **Q:** What does the REST MCP layer (`mcp_server.py`) actually wrap?  
   **A:** It wraps a product REST API hosted at `http://192.168.210.100:6051`, providing tools for suppliers, product search and details, product CRUD, cart operations, orders, and feedback. It uses `httpx` for async HTTP calls and provides consistent JSON responses.

7. **Q:** How are GraphQL operations exposed to the GraphQL agent?  
   **A:** `graph_mcp.py` (and `graphQL_mcp.py`) expose GraphQL queries and mutations as MCP tools using a `FastMCP` server. These tools build GraphQL documents and variable payloads, send them via HTTP to `/graphql`, and return parsed data fields.

8. **Q:** Where are OpenAI model credentials configured?  
   **A:** Agents call `load_dotenv()` and then rely on `OPENAI_API_KEY` and related settings defined in `.env`. Do not expose or share those keys; they should be rotated and stored securely in production.

9. **Q:** How should I run this system locally?  
   **A:** Although not documented in the README, the typical flow is:
   - create a Python environment and install `requirements.txt`,
   - set up `.env` with valid OpenAI and backend URLs/keys,
   - start any required MCP servers if used as separate processes (depending on how you integrate them),
   - run the FastAPI app (e.g., `uvicorn main:app --reload`),
   - then open the root URL in a browser.
   This is inferred from the code structure rather than explicit docs.

10. **Q:** Is this project ready for production deployment as-is?  
    **A:** No. It lacks authentication, has secrets in the repo, uses permissive CORS, and has no tests or deployment configuration. It is better viewed as a capable internal prototype or reference implementation for multi-agent, multi-backend e-commerce assistants.

11. **Q:** What is the relationship between `graph_mcp.py` and `graphQL_mcp.py`?  
    **A:** Both wrap the same GraphQL backend. `graph_mcp.py` uses synchronous `requests` and relatively direct mappings, while `graphQL_mcp.py` uses async `httpx` and more aggressive normalization/validation of input dicts from the LLM. The active GraphQL agent currently imports tools from `graph_mcp.py`.

12. **Q:** How does the system keep track of conversation state?  
    **A:** `thread_id` is passed in a `config` object to `agent.astream`, and `InMemorySaver` is instantiated in agents, but persistent checkpointing is commented out. State is thus primarily conversational within a single streaming session; long-lived memory is not fully wired in.

## 19. Confidence and Uncertainty Notes

- **High confidence**
  - Core tech stack (FastAPI, LangChain, LangGraph, MCP, OpenAI) and their roles.
  - Presence and purpose of `main.py`, `db_agent.py`, `rest_agent.py`, `graphQL_agent.py`, `mcp_server.py`, `graph_mcp.py`, `graphQL_mcp.py`, and `dpsk_bot.html`.
  - Capabilities of each agent (SQL, REST, GraphQL) and the general e-commerce operations they can perform.
  - Existence of MS SQL Server, REST, and GraphQL backends with the described endpoints and schema fragments.

- **Medium confidence**
  - Exact deployment model (whether MCP servers are run as separate processes or just as libraries; the code supports both patterns).
  - Intended primary user personas (engineers vs business users); inference is based on naming and UI text rather than explicit docs.
  - Which GraphQL MCP module (`graph_mcp.py` vs `graphQL_mcp.py`) is considered the final or recommended path; current imports favor `graph_mcp.py`.

- **Low confidence / assumptions**
  - Real-world production usage of this repository (no deployment files or usage metrics visible).
  - Any external integration details beyond what is directly visible in connection strings, URLs, and docstrings.

---

## Machine Summary

```json
{
  "project_name": "e-commerce-agent",
  "project_type": "Multi-agent e-commerce assistant with FastAPI backend and streaming web UI",
  "summary_short": "A FastAPI-based, OpenAI-powered assistant that exposes the same e-commerce backend through SQL, REST, and GraphQL agents with a side-by-side comparison UI.",
  "primary_language": ["Python", "HTML", "JavaScript"],
  "frameworks": [
    "FastAPI",
    "LangChain",
    "LangGraph",
    "FastMCP",
    "Tailwind CSS"
  ],
  "key_features": [
    "Three agents (DB, REST, GraphQL) over the same e-commerce domain",
    "Streaming chat endpoint with side-by-side comparison UI",
    "SQL Server integration via LangChain SQLDatabaseToolkit",
    "REST API integration via FastMCP-wrapped tools",
    "GraphQL integration via custom MCP servers",
    "OpenAI GPT-4/4o based conversational interface",
    "LangSmith tracing and observability hooks"
  ],
  "architecture_style": "Monolithic FastAPI service with agentic backends and tool-based integrations to external SQL, REST, and GraphQL services",
  "deployment_signals": [
    "FastAPI + Uvicorn entrypoint",
    "Environment-based configuration via .env",
    "LangSmith tracing configured",
    "No explicit Docker/CI files in repo"
  ],
  "ai_capabilities": [
    "Tool-using LLM agents for SQL, REST, and GraphQL",
    "Natural-language querying of e-commerce data",
    "Cart, order, and product management via tools",
    "Streaming token-level responses to the UI"
  ],
  "data_sources": [
    "Microsoft SQL Server PRODUCT_DB",
    "Product REST API at http://192.168.210.100:6051",
    "GraphQL API at http://192.168.210.100:6051/graphql"
  ],
  "notable_strengths": [
    "Clear demonstration of SQL vs REST vs GraphQL integration patterns",
    "Thoughtful MCP and GraphQL tool design with validation and normalization",
    "Streaming-first UX implementation end-to-end",
    "Practical use of LangChain, LangGraph, and OpenAI in an e-commerce domain"
  ],
  "limitations": [
    "Secrets and DB credentials present in code and .env",
    "No tests or deployment configuration",
    "Prototype-level security (open CORS, no auth)",
    "Some demo code executes at import time"
  ],
  "confidence": "high for architecture and capabilities inferred directly from code; medium for deployment and real-world usage details"
}
```

