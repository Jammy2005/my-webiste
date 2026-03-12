# Project: Scada Virtual Agent

## 1. One-Sentence Summary

An LLM-powered web assistant that lets users upload CSV/Excel datasets (especially SCADA/power data) and then chat with a ReAct-style agent that analyzes the data with pandas/matplotlib, streams back explanations, and generates visualizations.

## 2. Executive Summary

**Scada Virtual Agent** is a small but sophisticated data-assistant web app built around a FastAPI backend and a LangGraph/LangChain agent. Users upload tabular data files via a browser UI, then ask natural-language questions; the backend orchestrates an OpenAI `gpt-4o` model wrapped in a ReAct agent that can execute Python code against a pandas `DataFrame`. The agent performs data analysis and generates plots using matplotlib, saving images to disk, which are then surfaced in the chat UI.

The system implements full-duplex-style streaming: the backend emits NDJSON events for text deltas, tool-code execution, tool results, and discovered plot images; the frontend consumes these events via a streaming `fetch` and renders an interleaved timeline of text, tool cards, and clickable images. Prompt-level guardrails constrain the assistant to power/energy/data-analysis topics and enforce a plotting protocol (non-GUI Agg backend, `plt.savefig`, `plt.close`, etc.), showing attention to safe code execution and resource handling. Overall, it is a strong demo of an **agentic, tool-using LLM fronted by a custom streaming UI** for exploratory data analysis.

## 3. What Problem This Project Solves

- **Data exploration friction**: Non-programmer or semi-technical users often struggle to explore CSV/Excel datasets—especially power/SCADA logs—using code and plots.
- **Bridging natural language and code**: Users can describe what they want (e.g., “visualise temp against time”) instead of writing Python/pandas/matplotlib code themselves.
- **On-demand visualizations**: The agent automatically generates plots, saves them, and exposes them as images in the chat, without the user leaving the browser.
- **Domain-relevant guardrails**: The system is scoped to power, energy, and general data analysis/visualisation questions, avoiding irrelevant or off-topic usage.

This is best understood as **internal tooling / a demo assistant** for data-centric workflows, particularly around SCADA/power datasets (evidenced by sample CSV columns like `TOTAL LOAD`, `FREQUENCY`, `TEMPERATURE`, `HUMIDITY` and the project name).

## 4. Likely Users / Stakeholders

- **Power systems / SCADA engineers** who need quick visual and statistical insights from operational logs.
- **Data analysts / BI professionals** who want a conversational layer over CSV/Excel data.
- **Non-technical stakeholders** (managers, operations staff) who can ask high-level questions without writing code.
- **ML/AI practitioners** demonstrating agentic tooling, LangGraph, and streaming UI integrations for client or portfolio purposes.
- **Recruiters or hiring managers** evaluating the developer’s ability to integrate LLMs, agents, and web backends.

## 5. What the System Actually Does

- **File upload & dataset setup**
  - Frontend allows users to upload `.csv`, `.xlsx`, or `.xls` files.
  - Backend `/upload` endpoint:
    - Reads Excel via pandas and converts to CSV, or stores CSV directly in a `data/` directory.
    - Calls `set_dataset(csv_path)` in `agent.py`, which:
      - Reads the CSV into a pandas `DataFrame`.
      - Builds a LangGraph ReAct agent with a `PythonAstREPLTool` wired to that `DataFrame` and relevant Python modules.
- **Chat interaction**
  - Frontend sends chat messages to `/chat-stream` via `fetch` with a JSON body containing `message` and local `history`.
  - Backend `chat_stream`:
    - Invokes `ag.stream(...)` on the LangGraph agent with the user message and a thread ID.
    - Streams NDJSON events back, including:
      - `text_delta`: incremental natural-language output.
      - `tool_start`, `tool_code_delta`, `tool_result_delta`, `tool_end`: a detailed trace of Python code execution and results.
      - `image`: URLs of generated plot files.
- **Code execution & plotting**
  - Agent prompt (`_build_prompt`) defines:
    - A global `df` `DataFrame` and how to use it.
    - Strict matplotlib usage rules: `matplotlib.use('Agg')`, `plt.savefig` to a configured output directory, `plt.close()`, no `plt.show()`.
  - The `PythonAstREPLTool` executes LLM-generated Python code in a sandboxed local environment with access to:
    - `df`, `pd`, `matplotlib`, `plt`, `output_dir`, `os`.
- **Plot discovery and serving**
  - After agent execution, the backend inspects final messages:
    - `extract_image_url_from_messages` uses regex to find `plt.savefig('...')` calls in tool-code.
    - If the saved image path exists, it copies the image into the `plots/` directory and emits an `image` event with `/plots/<id>.png`.
  - Frontend displays these as inline images with a click-to-zoom lightbox.
- **Session management**
  - A global `THREAD_ID` and LangGraph `InMemorySaver` track conversation.
  - `/clear` resets the agent and deletes uploaded data from the `data/` directory.

## 6. Technical Architecture

- **Overall style**: Single-service backend with a thin, mostly-static frontend; **agentic back-end orchestration** using LangGraph.
- **Backend**
  - **FastAPI** application (`main.py`) as the primary entrypoint.
  - Static file mounts:
    - `/static` → `static/` assets (CSS, SVG icons, logos).
    - `/plots` → `plots/` directory where matplotlib images are stored.
  - Core endpoints:
    - `GET /`: serves `dpsk_bot.html` (chat UI).
    - `POST /upload`: handles file upload and dataset initialization.
    - `POST /chat-stream`: NDJSON streaming of chat and tool events.
    - `POST /tts`: current stub (returns empty audio).
    - `DELETE /clear`: resets session state and deletes uploaded files.
  - **Agent composition** (`agent.py`):
    - Uses `ChatOpenAI(model="gpt-4o", temperature=0)`.
    - Uses `PythonAstREPLTool` to run Python code.
    - Wraps with `create_react_agent` from `langgraph.prebuilt`.
    - Uses `InMemorySaver` from `langgraph.checkpoint.memory` for state.
- **Frontend**
  - A single HTML file (`dpsk_bot.html`) with:
    - Tailwind CSS via CDN, plus a custom `global.css`.
    - Showdown.js for Markdown → HTML conversion.
    - Vanilla JavaScript to:
      - Manage chat state and DOM.
      - Perform file uploads.
      - Stream NDJSON responses and render a "timeline" of blocks (text, tool cards, images).
      - Provide a lightbox for zooming into images.
- **Storage**
  - **File system only**:
    - Uploaded CSVs in `data/`.
    - Generated plots in `plots/`.
  - No database or external persistent store.
- **Configuration**
  - `.env` loaded via `python-dotenv` (presumably holds OpenAI API credentials).
  - All project dependencies pinned in `requirements.txt`.

## 7. Main Components

- **`main.py`**
  - FastAPI app definition and configuration.
  - CORS, static mounts (`/static`, `/plots`).
  - Directory initialization (`PLOTS_DIR`, `UPLOAD_DIR` creation).
  - `clear_data_directory()` to remove uploaded files on startup and via `/clear`.
  - **Streaming logic** in `chat_stream`:
    - Orchestrates LangGraph `ag.stream` with both `messages` and `values`.
    - Maintains internal buffers to:
      - Reassemble partial tool-call arguments JSON (`tool_call_chunks`).
      - Emit incremental `tool_code_delta` events as the `query` string becomes parseable.
    - After streaming completion, inspects `final_state` for plots and emits `image` events.
- **`agent.py`**
  - `_build_prompt(df, output_dir)`: builds a long system prompt that:
    - Describes the `df` (via `df.head().to_markdown()`).
    - Enforces plotting protocol and guardrails (topic focus, retry on failure, closing plots, no path leakage, Arabic → Kuwaiti dialect, etc.).
  - `_build_agent(csv_path)`: 
    - Loads CSV into `df`.
    - Sets up `tool_globals` for the Python tool.
    - Instantiates `ChatOpenAI` and `create_react_agent`.
    - Stores the agent and current CSV path in globals.
  - `set_dataset`, `get_agent`, `reset_agent`: global lifecycle functions.
  - A hard-coded initial agent build using `titanic.csv` so the system has a default dataset.
- **`dpsk_bot.html`**
  - UI layout:
    - Fixed-height chat container with a header (logo + title + clear button).
    - Scrollable message area with a welcome card.
    - Input bar with text field, send button, and upload button.
  - JS logic:
    - `addUserMessage`, `addBotMessageShell`, `makeToolCard`, etc.
    - `sendMessage()`:
      - Streams from `/chat-stream`, buffering lines terminated by `\n`, parsing them as JSON, and applying per-event-type update functions.
    - Tool cards:
      - Expandable sections showing executed code and textual tool output.
    - Image lightbox for `/plots/*.png` images.
- **Assets and sample data**
  - `static/styles/global.css` plus SVG icons for buttons and logos.
  - `Feb Power Load_Sheet1.csv` and generated plot PNGs (evidence of real SCADA/power usage).
  - `smth.txt` — captured LangGraph run logs, showing real agent/tool interactions over power-load data.

## 8. End-to-End Flow

1. **User opens the app**
   - Browser loads `GET /` → `dpsk_bot.html` → tailwind + custom CSS + JS.
   - Welcome message instructs the user to upload data before chatting.

2. **User uploads a dataset**
   - Clicks the upload icon → selects a `.csv`, `.xlsx`, or `.xls`.
   - Frontend:
     - Shows a user message “Uploaded file: `<name>`”.
     - Posts the file to `POST /upload` using `FormData`.
   - Backend:
     - Saves or converts the file to a CSV in `UPLOAD_DIR`.
     - Calls `set_dataset` which:
       - Reads CSV into pandas `df`.
       - Rebuilds the LangGraph agent bound to this `df`.
     - Returns success JSON.
   - Frontend:
     - Replaces typing placeholder with a bot message telling the user the dataset is loaded.

3. **User sends a question**
   - Types something like “can u help me visualise temp against time ?”.
   - Frontend:
     - Sends a `{ message, history }` JSON to `POST /chat-stream`.
     - Disables input, shows a typing bubble.
   - Backend:
     - Uses `get_agent()` to retrieve or lazily build the agent (if none configured).
     - Calls `ag.stream(...)` with the user message and a thread_id.
     - As the agent runs, it:
       - Produces normal LLM text.
       - Issues tool calls (`python_repl_ast`) with generated code operating on `df`.
     - `chat_stream`:
       - Emitted events for:
         - `text_delta` (for plain explanation).
         - `tool_start` → signals that code execution has begun.
         - `tool_code_delta` → incremental reconstruction of Python code from tool-call arguments.
         - `tool_result_delta` → incremental tool output/errors.
         - `tool_end`.
       - After completion, inspects `final_state["messages"]`, parses the python code, detects any `plt.savefig(...)` calls, verifies the file exists, copies it to the `plots` directory, and emits a final `image` event.

4. **Frontend renders the response**
   - For `text_delta`: appends markdown-rendered text inside a “text block”.
   - For `tool_*`: creates/updates expandable tool cards with code and output traces.
   - For `image`: appends an image block with `src` pointing to `/plots/<uuid>.png`; clicking opens a full-screen overlay.
   - Re-enables input and appends the full assistant message text to local `chatHistory`.

5. **User clears the session**
   - Clicking the reload icon triggers `DELETE /clear`:
     - Backend resets the global agent and `THREAD_ID`, deletes uploaded files.
     - Frontend resets UI, chat history, and focus.

## 9. Tech Stack

- **Languages**
  - **Python** (backend and agent orchestration).
  - **JavaScript** (frontend logic in `dpsk_bot.html`).
  - **HTML/CSS** (UI, layout, custom styling).

- **Frameworks & Libraries (Backend)**
  - **FastAPI**: Web framework and routing.
  - **Starlette**: Underlying ASGI, static file serving.
  - **Uvicorn**: ASGI server (referenced in your terminal).
  - **Pydantic**: Request models (`QueryRequest`).
  - **Pandas**: CSV/Excel data loading and manipulation.
  - **Matplotlib**: Plotting, configured with `Agg` backend.
  - **OpenPyXL**: Excel reading support.
  - **LangChain / LangGraph**:
    - `langchain_openai.ChatOpenAI`.
    - `langchain_experimental.tools.PythonAstREPLTool`.
    - `langgraph.prebuilt.create_react_agent`.
    - `langgraph.checkpoint.memory.InMemorySaver`.

- **Frameworks & Libraries (Frontend)**
  - **Tailwind CSS** via CDN.
  - **Showdown.js** for markdown-to-HTML rendering.
  - Plain DOM APIs, `fetch`, and `ReadableStream` readers.

- **AI / Model Providers**
  - OpenAI `gpt-4o` (via `langchain_openai`).
  - ReAct-style agent pattern through LangGraph.

- **Infrastructure / Tooling**
  - `.env` loading via `python-dotenv`.
  - Requirements pinned in `requirements.txt`.
  - No explicit Docker/CI files in the repo snapshot.

## 10. Notable Engineering Decisions

- **ReAct agent with Python REPL tool**:
  - Uses a LangGraph prebuilt ReAct agent with a `PythonAstREPLTool` that runs code directly against a shared `df`, giving the model powerful and flexible analytical capabilities.
- **Strict plotting protocol**:
  - The prompt enforces:
    - `matplotlib.use('Agg')`.
    - `plt.savefig(..., dpi=300, bbox_inches='tight')`.
    - Always `plt.close()` afterwards.
    - Never `plt.show()`.
  - This avoids GUI issues in headless environments and frees memory.
- **Evented NDJSON streaming API**:
  - Instead of basic text streaming, the backend emits structured events:
    - Allows the frontend to show a rich timeline (code, results, images).
    - Facilitates future extension (e.g., additional event types).
- **Plot extraction from source code**:
  - Rather than relying on the model to explicitly tell the frontend what image was created, the backend parses the executed Python code for `plt.savefig` paths and verifies files exist.
- **Guardrails in prompt**:
  - Topic restrictions (power, energy, data analysis/visualisation).
  - Resilience instructions (“Do not give up; try to understand why it failed…”).
  - Localized language behavior (Arabic → Kuwaiti dialect).
- **Threaded state via `THREAD_ID` and in-memory checkpointing**:
  - Global `THREAD_ID` and `InMemorySaver` allow conversation continuity and agent-state restoration within one process.

## 11. Evidence of Production Readiness

**Evidence for some production-minded thinking:**

- **Pinned dependencies** in `requirements.txt`.
- **Non-GUI plotting backend** and explicit resource cleanup.
- **File uploads constrained to CSV/Excel**, with clear error messages for unsupported types.
- **Error handling**:
  - Uploads wrapped in `try/except`, returning structured error responses.
  - `chat_stream` wraps agent streaming in a `try/except` and emits `error` events.
- **Static mounting and directory bootstrapping** to ensure required directories exist.

**Evidence suggesting it is more of a prototype/demo than hardened production:**

- **Global mutable state** (`_current_agent`, `_current_csv_path`, `THREAD_ID`) – not safe for multi-process scaling or concurrent users.
- **No authentication/authorization**.
- **No database or long-term persistence** of conversations or datasets.
- **No tests or CI configuration** visible.
- **README** is still the GitLab template, not project-specific.
- **TTS endpoint** is stubbed, indicating incomplete features.

Overall, it appears “production-ready” for a **single-user demo** or internal prototype, not yet for multi-tenant or internet-wide deployment.

## 12. Challenges the Developer Likely Had to Solve

- **Streaming integration between LangGraph and the browser**:
  - Mapping LangGraph’s `stream` outputs (`mode`, `chunk` pairs) into a linear NDJSON stream usable by a simple JS client.
  - Handling partial tool-call arguments (`tool_call_chunks`) and reconstructing valid JSON to extract the `query` code string.
- **Designing a robust Python execution sandbox**:
  - Safely exposing only specific globals (`df`, `pd`, `matplotlib`, `plt`, `output_dir`, `os`) while letting the agent perform expressive data transformations and plotting.
- **Plot discovery and routing**:
  - Detecting `plt.savefig` calls via regex, verifying existence, and copying files into a served `/plots` directory with randomized filenames.
- **Frontend timeline model**:
  - Keeping text, tool-code, tool-output, and images ordered correctly as they stream in.
  - Managing “typing” placeholders, block replacement, and incremental markdown rendering without flicker.
- **Resilient prompt/agent design**:
  - Handling failures like `KeyError` on missing columns by prompting the model to inspect `df.columns` and retry (as evidenced in `smth.txt` logs).
- **Domain adaptation**:
  - Tailoring the agent prompt and sample data to power-load datasets (timestamped readings, total load, frequency, temperature, humidity).

## 13. What Makes This Project Strong on a Resume

- **End-to-end LLM agent integration**:
  - Integrates OpenAI’s `gpt-4o` with LangChain/LangGraph, implements a Python tool, and manages agent state.
- **Rich streaming UI**:
  - Custom, event-based streaming protocol and frontend that visualizes:
    - Natural-language tokens,
    - Tool code and outputs,
    - Generated plots,
    in a coherent timeline.
- **Practical data-assistant use case**:
  - Real CSV/Excel ingestion, agentic data analysis, and automatic visualization.
- **Attention to non-trivial details**:
  - Matplotlib backend issues in servers.
  - Closing plots and managing memory.
  - Guardrails and prompt engineering.
  - File-system routing for plots.
- **Clear separation of concerns**:
  - Agent logic in `agent.py`.
  - HTTP & streaming orchestration in `main.py`.
  - UI and UX in `dpsk_bot.html` and `global.css`.
- **Pinned, modern Python ecosystem**:
  - Up-to-date FastAPI, LangChain, LangGraph, and OpenAI libraries.

## 14. Limitations or Gaps

- **Scalability & multi-user support**
  - Global `THREAD_ID` and a single `_current_agent` mean only one logical conversation/thread is effectively supported at a time.
  - No multi-session or user-level isolation.
- **Security considerations**
  - Python tool executes arbitrary code generated by the LLM over the shared `tool_globals` (including `os`), which may pose risks in untrusted deployments.
  - No explicit resource limits, sandboxing, or process isolation beyond the Python process.
- **Persistence & observability**
  - No database or logging framework; minimal console `print` error reporting.
  - No central store for chat history or analysis outputs beyond front-end state.
- **Documentation**
  - README is generic GitLab template; no instructions for running the app, configuring OpenAI keys, or explaining architecture.
- **Testing**
  - No visible automated tests or QA infrastructure.
- **TTS feature**
  - Present only as a stub; the frontend calls `/tts` but backend returns empty audio.

## 15. Best Future Improvements

- **Session and user management**
  - Replace global `THREAD_ID` with per-client session IDs (cookies or tokens).
  - Maintain multiple parallel LangGraph threads, keyed by session.
- **Security hardening**
  - Introduce a stricter sandbox for Python code (e.g. restricted builtins, jailed file system path).
  - Remove or tightly scope access to `os`.
- **Persistence & observability**
  - Store chat history and analysis metadata in a database (e.g. Postgres, SQLite).
  - Add structured logging and metrics (request latency, tool-error rates, plot generation counts).
- **Deployment artifacts**
  - Add a proper README with run instructions (`uvicorn main:app --reload` etc.).
  - Provide Dockerfile and simple CI config for automated testing and deployment.
- **Frontend UX enhancements**
  - Indicate when the dataset is not loaded and prevent sending chat messages until upload.
  - Allow selecting or switching between multiple uploaded datasets.
  - Add pre-configured example questions / quick replies specific to power/SCADA.
- **Model and agent improvements**
  - Support multiple model backends or versions.
  - Add tools for summary statistics, missing-value reports, and outlier detection with standardized cards.
- **Robust error recovery**
  - More informative error event handling on the frontend (e.g., separate banner vs. inline text).

## 16. Recruiter-Friendly Summary

**Scada Virtual Agent** is a full-stack AI data assistant: a FastAPI/LangGraph backend with an OpenAI `gpt-4o` ReAct agent that runs Python code over uploaded CSV/Excel data, and a custom Tailwind/JS frontend that renders streaming responses, code snippets, and generated plots. The project demonstrates strong skills in **LLM orchestration, streaming APIs, prompt/guardrail design, and modern Python web development**.

The project shows the ability to build **agentic workflows that execute real code**, handle file uploads and plotting with matplotlib, and connect those to a smooth browser experience. It is a compelling demo of turning raw SCADA-like datasets into an interactive, conversational analytics tool.

## 17. Deep Technical Summary

At its core, the system wires together:

- **LangGraph ReAct Agent**
  - `create_react_agent` produces an LLM agent that:
    - Receives messages.
    - Decides when to call tools (here, a Python AST REPL).
    - Uses observation results to continue reasoning.
- **PythonAstREPLTool**
  - Accepts a `query` string of Python code.
  - Executes it in a local environment seeded with:
    - `df` (pandas `DataFrame` from the active CSV).
    - `pd`, `matplotlib`, `plt`, `output_dir`, `os`.
  - Returns the stringified result or error as a tool message.

The main streaming loop in `chat_stream`:

- Invokes `ag.stream` with `stream_mode=["messages", "values"]`.
- For each `messages` chunk:
  - If it’s a `ToolMessage`, it:
    - Emits `tool_result_delta` with content.
    - Emits `tool_end` for that `tool_call_id`.
  - If it’s an `AIMessage`:
    - Emits `text_delta` for any non-empty `content` (plain text).
    - Inspects `additional_kwargs.tool_calls` to:
      - Emit `tool_start` when a `python_repl_ast` is scheduled.
      - Track `tool_call_id` by index.
    - Inspects `tool_call_chunks` to:
      - Accumulate partial `args` strings per `tool_call_id`.
      - Attempt to parse them as JSON and extract the `query` field.
      - When parsing succeeds, emit `tool_code_delta` with only the new portion of the query.
- After streaming:
  - Uses `final_state["messages"]` to search for `plt.savefig` calls, copies the image file to the `plots` mount, and emits one `image` event.

The frontend is careful to order events and UI elements:

- Maintains a timeline container per assistant turn.
- Treats each event type as a “block”:
  - Text blocks (rendered via Showdown markdown).
  - Tool cards (with separate “Code” and “Output” panes).
  - Image blocks (clickable, with lightbox overlay).
- Uses debounced rendering for text (`setTimeout` ~50ms) to reduce DOM churn during token streaming.

The agent prompt itself:

- Embeds `df.head().to_markdown()` to give the model schema and sample values.
- States a robust protocol for matplotlib usage and user engagement (offer follow-up analysis suggestions).
- Enforces domain and language constraints.

Overall, the project is a compact but non-trivial implementation of a **code-executing, streaming LLM agent over user data**, packaged as a web app.

## 18. FAQ for Another AI Assistant

1. **What does this project do in plain terms?**  
   It lets users upload CSV/Excel datasets in the browser and then chat with an AI that analyzes the data using Python and generates plots, all displayed in a streaming chat UI.

2. **Where is the main backend entrypoint?**  
   The main ASGI app is defined in `main.py` as a FastAPI application (`app = FastAPI()`), with routes like `/`, `/upload`, `/chat-stream`, `/tts`, and `/clear`.

3. **How is the LLM agent implemented?**  
   In `agent.py`, using `ChatOpenAI(model="gpt-4o")`, a `PythonAstREPLTool` for execution, and `create_react_agent` from `langgraph.prebuilt`, with an `InMemorySaver` checkpoint store.

4. **How does the agent access the dataset?**  
   When a CSV is uploaded, `set_dataset` loads it into a pandas `DataFrame` named `df`, which is passed as part of the `locals` to `PythonAstREPLTool`, allowing the LLM to write code like `df['TEMPERATURE'].mean()`.

5. **How are plots generated and shown to the user?**  
   The LLM writes matplotlib code with `plt.savefig('<path>')`. After execution, the backend parses the executed code for `plt.savefig` file paths, copies the resulting images into the `plots/` directory, and sends an `image` event so the frontend can display them.

6. **How does streaming work between backend and frontend?**  
   The frontend uses `fetch` with `res.body.getReader()` to read a byte stream from `/chat-stream`. The backend writes NDJSON lines, each containing an event with a `type` field (e.g., `text_delta`, `tool_start`), which the frontend parses and renders incrementally.

7. **What are the main guardrails for the agent?**  
   The system prompt restricts responses to power, energy, data analysis, or visualization questions, enforces correct matplotlib usage, encourages retries on code errors, and instructs the agent to reply in Kuwaiti Arabic if the user asks in Arabic.

8. **Is the system multi-user or multi-session aware?**  
   Not robustly; it uses a single global `THREAD_ID` and a single `_current_agent`. The `/clear` endpoint resets the agent and thread ID, so the current design is best suited for one user/session at a time.

9. **What external dependencies are required?**  
   The main ones are FastAPI, Starlette, Uvicorn, pandas, matplotlib, openpyxl, python-dotenv, langchain, langgraph, langchain-openai, and OpenAI credentials (via `.env`). All are listed with pinned versions in `requirements.txt`.

10. **How should this project be run locally?**  
    Although the README doesn’t specify, the usual pattern is: install dependencies from `requirements.txt`, set the necessary `.env` variables (like `OPENAI_API_KEY`), then run `uvicorn main:app --reload` and open the root URL in a browser.

11. **How is TTS handled?**  
    The frontend calls `/tts` after receiving the full assistant message, expecting base64-encoded audio. Currently, the backend `/tts` endpoint returns an empty `audio` field—so TTS is stubbed out and non-functional.

12. **What sample data or domain is the project geared toward?**  
    There is a sample CSV `Feb Power Load_Sheet1.csv` with columns like `DATE & TIME`, `TOTAL LOAD`, `FREQUENCY`, `TEMPERATURE`, `HUMIDITY`, and saved plots like `temperature_over_time.png`, indicating SCADA/power-load time series data.

13. **Is there any persistent storage beyond files?**  
    No; the project uses file-system storage only (uploaded CSVs and generated plots) and in-memory agent state via LangGraph’s `InMemorySaver`.

14. **Does the project include authentication or user accounts?**  
    No authentication or authorization is implemented in the codebase snapshot.

15. **How easy is it to extend with new tools?**  
    Additional tools can be wired into the agent by extending the `tool_globals` or adding other LangChain tools, then re-creating the agent with `create_react_agent` and updating the frontend to visualize new event types if needed.

## 19. Confidence and Uncertainty Notes

- **Confidence (high)** about:
  - The overall architecture (FastAPI backend + LangGraph agent + PythonAstREPLTool + Tailwind/JS frontend).
  - The primary use case (upload tabular data, chat-based analysis and plotting).
  - The specifics of the streaming protocol and plot extraction, since these are clearly implemented in `main.py` and the frontend JS.
- **Uncertainties / assumptions**:
  - Exact deployment environment (local vs. cloud) is not specified.
  - Intended scale and user base are not documented; we infer single-user or demo use from the global state design.
  - Future feature roadmap and non-demo requirements are not present, as the README is still the default GitLab template.