# Project: Ambient Email Agent

## 1. One-Sentence Summary

An AI-powered ambient email assistant that triages incoming messages, loops in a human when needed, and can draft and send replies or schedule meetings via Gmail and Google Calendar using a LangGraph multi-node workflow.

## 2. Executive Summary

This project implements an opinionated email assistant built on LangGraph and LangChain that sits between a user’s inbox and their calendar. Incoming emails are parsed into a structured format, routed through an LLM-based triage model, and either ignored, surfaced as a notification, or handed off to a response agent that can call tools to draft emails, schedule meetings, or ask the user clarifying questions. Human‑in‑the‑loop (HITL) review is a first-class part of the design: important tool calls like sending mail or scheduling meetings can be intercepted, edited, accepted, or ignored from an Agent Inbox UI via LangGraph’s `interrupt` mechanism. The system integrates tightly with Gmail and Google Calendar APIs, including support for replying in existing threads, creating Calendar events with correct time zones, and checking free/busy availability. Overall, it demonstrates a realistic, production‑adjacent pattern for orchestrating LLM tools for communications workflows.

## 3. What Problem This Project Solves

Modern knowledge workers receive many emails that don’t all deserve the same level of attention. Manually deciding which emails to ignore, which just need to be seen, and which require careful replies is time‑consuming. This project aims to offload much of that workload to an agent that can:
- Automatically triage emails into ignore / notify / respond buckets.
- Draft and send appropriate replies where possible.
- Proactively schedule or respond to meeting requests using calendar data.
- Ask the human for guidance only when it truly lacks context.

The intent is to reduce cognitive load and context switching around email, while still keeping a human firmly in control of high‑impact actions.

## 4. Likely Users / Stakeholders

- **Individual professionals** who want a personal AI executive assistant to manage email and calendar.
- **Developers / ML engineers** exploring LangGraph patterns for agent orchestration and HITL.
- **Internal tools teams** at companies that want to pilot AI‑driven email triage for a subset of employees.
- **Recruiters / hiring managers** who need to understand the candidate’s ability to build realistic agentic workflows around email and calendar.

## 5. What the System Actually Does

- **Parses incoming emails** into a standard dictionary form (`author`, `to`, `subject`, `body`, `email_thread`, `id` etc.) using helper functions like `parse_email` and `parse_gmail`.
- **Formats emails for display** as markdown, including HTML‑to‑markdown conversion for Gmail messages, so that emails can be clearly shown in an Agent Inbox or used as LLM context.
- **Runs LLM-based triage**:
  - A `RouterSchema` Pydantic model defines a structured output with `reasoning` and `classification` (`ignore`, `respond`, `notify`).
  - An OpenAI `gpt-4.1` chat model (via `langchain.chat_models.init_chat_model`) is wrapped with `.with_structured_output(RouterSchema)` to reliably emit triage decisions based on detailed written rules and background context.
- **Executes a response agent**:
  - A second `gpt-4.1` model is bound to tools (`write_email`, `schedule_meeting_tool`, `calendar_freebusy`, `Question`, `Done`) with `tool_choice="required"`, forcing it to use tools rather than produce free-form answers.
  - The response agent runs as a LangGraph state machine that repeatedly calls the LLM and then routes to an interrupt handler whenever tool calls are present.
- **Provides human-in-the-loop control**:
  - Tool calls deemed sensitive (e.g., `write_email`, `schedule_meeting`, `Question`) are turned into `interrupt` requests with a rich markdown description that includes the original email and a formatted display of the proposed action.
  - The Agent Inbox user can `accept`, `edit`, `ignore`, or send a `response` (feedback); the graph then either executes the tool, updates tool arguments, ends the workflow, or feeds back the user’s comments to the agent.
- **Integrates with Google Calendar**:
  - Schedules meetings via `schedule_meeting`, which uses Calendar v3 to create events with proper time zones (default `Australia/Melbourne`), guests, and notifications.
  - Checks free/busy availability for a given day using the Calendar FreeBusy API and returns readable busy slots.
- **Integrates with Gmail**:
  - Builds MIME messages, encodes them to base64, and sends them using the Gmail API.
  - Supports replying within an existing thread by attaching a `threadId` to the API request.
- **Captures user preferences and memory** (partially implemented):
  - Pydantic models and prompt templates describe how to gradually update user preferences over time from HITL feedback, so the assistant can learn what to respond to, notify about, or ignore.

## 6. Technical Architecture

- **Core paradigm**: LangGraph state graphs orchestrating LLM calls, tool calls, and human interrupts.
- **Main graph (`overall_workflow`)**:
  - **Input schema**: `StateInput` (`email_input: dict`).
  - **State**: `State` extends `MessagesState` and adds `email_input` and `classification_decision`.
  - **Nodes**:
    - `triage_router`: classifies the email as `ignore`, `notify`, or `respond`.
    - `triage_interrupt_handler`: for `notify` cases, surfaces a notification and waits for a human response via `interrupt`.
    - `response_agent`: a compiled subgraph that runs the email‑response workflow including HITL for tool calls.
  - **Edges**:
    - `START -> triage_router`.
    - `triage_router` transitions to:
      - `END` if classification is `ignore`.
      - `triage_interrupt_handler` if `notify`.
      - `response_agent` if `respond`.
- **Response agent subgraph**:
  - Built as its own `StateGraph(State)` with:
    - Node `llm_call`: calls `llm_with_tools` with the HITL‑specific system prompt and the accumulated `messages`.
    - Node `interrupt_handler`: examines the latest LLM tool calls, decides which ones must be interrupted, creates Agent Inbox requests, and translates user actions into new messages or tool executions.
  - Conditional edge function `should_continue` routes either back to `interrupt_handler` or to `END` based on whether the last message contains tool calls and whether the `Done` tool has been used.
  - The compiled graph `response_agent` is nested as a node inside the top‑level `overall_workflow`.
- **Tools / integrations layer**:
  - `tools.py` defines LangChain `@tool` functions/classes:
    - `write_email` → calls Gmail send.
    - `schedule_meeting_tool` → wraps Calendar event scheduling.
    - `calendar_freebusy` → wraps Calendar FreeBusy.
    - `Question` and `Done` as structured tool classes (Pydantic models).
  - `gmail.py` encapsulates Google API logic:
    - Credential management via OAuth tokens and local `token.json` or base64‑encoded env secret (`GMAIL_SECRET`) when `ENV=prod`.
    - Low‑level Gmail and Calendar API calls.
  - `helpers.py` holds formatting and parsing utilities for emails and tool calls.
  - `prompts.py` centralizes system prompts, background, response preferences, calendar preferences, triage rules, and tool description strings.
- **Configuration / packaging**:
  - `pyproject.toml` describes a Python 3.11 package `ambient_agents2` with dependencies on LangGraph, LangChain, OpenAI, Google APIs, Pydantic, SQLAlchemy, and various utilities.

## 7. Main Components

- **`agent.py` (email agent orchestration)**:
  - Defines the main triage and response graphs.
  - Binds the LLMs to tools and structured output schemas.
  - Exposes an `email_assistant` compiled workflow that can be invoked with an `email_input` dict.
- **`utils/tools.py` (agent tools)**:
  - Implements the tools the LLM uses:
    - `write_email` (send via Gmail).
    - `schedule_meeting_tool` (calendar events).
    - `calendar_freebusy` (availability lookup).
    - `Question` and `Done` for HITL interaction management.
- **`utils/gmail.py` (Gmail and Calendar integration)**:
  - Manages Google OAuth credentials (local files and environment‑based secrets).
  - Implements `schedule_meeting`, `check_calendar_availability`, `send_gmail`, and helper functions like `create_message` and `send_message`.
- **`utils/helpers.py` (formatting and parsing helpers)**:
  - Email formatting (`format_email_markdown`, `format_gmail_markdown`) for readability and Agent Inbox display.
  - Message extraction utilities from LangChain message objects.
  - Few‑shot example formatting for triage.
  - Safe extraction of tool call names and pretty‑printed message logs.
- **`utils/prompts.py` (prompt templates and defaults)**:
  - Triage prompts (`triage_system_prompt`, `triage_user_prompt`) including rules and background.
  - Agent system prompts with and without HITL, plus versions that mention memory.
  - Default background text, response preferences, calendar preferences, and detailed triage instructions.
  - Tool description templates for standard, HITL, and memory‑enabled workflows.
  - Memory‑update instruction prompts for learning from user feedback.
- **`utils/schemas.py` (data models)**:
  - Pydantic and TypedDict models for router output, state, email data, and user preferences.

## 8. End-to-End Flow

1. **Email ingestion**:
   - External code (not shown here) receives a new email (from Gmail or another source) and constructs an `email_input` dict with at least author, recipient, subject, body, and thread information.
2. **Triage**:
   - `email_assistant.invoke({"email_input": email_input})` triggers `triage_router`.
   - The helper `parse_email` extracts fields, and `triage_user_prompt` is filled with the email details.
   - `triage_system_prompt` is formatted with `default_background` and `default_triage_instructions`, then passed to `llm_router`.
   - The LLM outputs a `RouterSchema` with reasoning and `classification`.
3. **Branching**:
   - **Ignore**: The workflow sets `classification_decision="ignore"` and goes directly to `END` with no further action.
   - **Notify**:
     - Triage goes to `triage_interrupt_handler`, which constructs an Agent Inbox interrupt describing the email and the fact that it’s a notification.
     - The human can choose to ignore or respond; if they respond, their feedback is added as an additional user message and control goes to `response_agent`.
   - **Respond**:
     - The system sets messages to a user instruction like “Respond to the email: [markdown]” and transitions to `response_agent`.
4. **Response agent loop**:
   - `llm_call` runs with `agent_system_prompt_hitl`, injecting background, response preferences, calendar preferences, and detailed tool descriptions, plus previous messages.
   - The LLM is required to call at least one tool (`tool_choice="required"`).
   - After the call, `should_continue` checks:
     - If the last message has no tool calls → go to `END`.
     - If it has a `Done` tool call → go to `END`.
     - Otherwise → go to `interrupt_handler`.
5. **Interrupt handler / HITL**:
   - For each tool call:
     - If it is a low‑risk tool (not in the HITL list), the tool is executed directly and its observation is appended as a `tool` role message.
     - If it is `write_email`, `schedule_meeting`, or `Question`:
       - The original email is reconstructed via `parse_email` and `format_email_markdown`.
       - A formatted tool preview (e.g., email draft or calendar invite) is created via `format_for_display`.
       - An `interrupt` request is sent to the Agent Inbox with allowed actions (`allow_accept`, `allow_edit`, `allow_ignore`, `allow_respond`) based on tool type.
       - The human’s response determines whether the tool is executed as‑is, executed with edited args, ignored with explanatory tool messages, or used to feed back a plain‑language response into the conversation.
   - The resulting messages are written back into state; the graph loops to `llm_call` or ends based on `should_continue`.
6. **External handling**:
   - The caller of `email_assistant` inspects the final `messages` list to see tool outputs, including whether an email was sent, a meeting was scheduled, or nothing needed to be done.

## 9. Tech Stack

- **Languages**: Python 3.11.
- **AI / LLM orchestration**:
  - `langgraph` (0.5.x) for state graphs, conditional edges, and interrupts.
  - `langchain`, `langchain-core`, `langchain-openai`, `langchain-text-splitters`.
  - OpenAI `gpt-4.1` chat model via `langchain.chat_models.init_chat_model`.
- **Data modeling**:
  - `pydantic` v2 for schemas and structured outputs.
  - `typing_extensions.TypedDict` and `MessagesState` from LangGraph.
- **External integrations**:
  - `google-api-python-client`, `google-auth`, `google-auth-oauthlib` for Gmail and Calendar.
  - `python-dateutil`, `pytz`, `dateutil.tz` for time zones and date handling.
- **Packaging and utilities**:
  - `SQLAlchemy` (present as a dependency but not heavily used in the shown files).
  - `orjson`, `ormsgpack`, `tiktoken`, `xxhash`, `zstandard` for performance and serialization (likely supporting LangGraph / LangSmith).
  - `langsmith` for observability (dependency present; usage not shown in these snippets).
- **Build system**: `setuptools` with `pyproject.toml` configuration.

## 10. Notable Engineering Decisions

- **Structured triage with Pydantic**: Using a dedicated `RouterSchema` for triage ensures that the LLM reliably returns both a classification and a human‑readable reasoning string, which is useful for debugging and observability.
- **Explicit HITL boundaries**:
  - The code distinguishes between tools that require human approval (`write_email`, `schedule_meeting`, `Question`) and others that can execute automatically.
  - Configuration flags (`allow_ignore`, `allow_respond`, `allow_edit`, `allow_accept`) per tool type give fine-grained control over what the Agent Inbox is allowed to do.
- **Immutability in state updates**:
  - When editing tool calls based on HITL feedback, the code copies and reconstructs `tool_calls` lists and message objects (`model_copy(update={...})`) instead of mutating them in place, which aligns with LangGraph’s design philosophy.
- **Environment-aware credential handling**:
  - In production (`ENV=prod`), credentials are loaded from a base64‑encoded `GMAIL_SECRET` environment variable and written to a temporary file.
  - In non‑prod, local `credentials.json` and `token.json` are used, which simplifies local development and demos.
- **Dedicated helper modules**:
  - Formatting and parsing logic is pulled into helpers (`format_email_markdown`, `format_gmail_markdown`, `format_for_display`, `extract_message_content`), keeping the graph definition cleaner and more focused on control flow.

## 11. Evidence of Production Readiness

- **Authentication and secrets handling**:
  - Supports environment‑driven secrets via `GMAIL_SECRET` and a clear separation between prod and local credential flows.
- **HITL safeguards**:
  - Potentially destructive actions (sending email, scheduling meetings) are gated behind human approval flows.
- **Time zone correctness**:
  - Calendar events are created with explicit IANA time zone strings and localized datetimes.
- **State modeling and strict typing**:
  - Uses Pydantic models and TypedDicts for states and schemas, reducing the chance of schema drift.
- **Logging / debugging hooks**:
  - Prints triage decisions and parsed email data; while basic, this helps during development.

There is no explicit Dockerfile, CI configuration, or infrastructure-as-code in the inspected portion of the repo, so full productionization steps (deployment, monitoring, scaling) are not represented here.

## 12. Challenges the Developer Likely Had to Solve

- **Designing a robust triage taxonomy** that is both simple (`ignore`, `notify`, `respond`) and expressive enough for real email workflows.
- **Orchestrating LLM tools with HITL** so that humans can safely override or correct AI decisions without breaking the state graph.
- **Handling Gmail and Calendar OAuth flows** in both local and production environments, including token refresh logic and secure secret storage.
- **Dealing with HTML-heavy emails** by converting them to markdown in a way that still reads well to both humans and LLMs.
- **Ensuring idempotent and debuggable flows** when tool calls are edited or ignored, especially with nested graphs and message history.

## 13. What Makes This Project Strong on a Resume

- **Multi-agent / graph-based orchestration**: Demonstrates non-trivial use of LangGraph to build a multi-node workflow with conditional routing and nested graphs.
- **Real-world integrations**: Shows practical integration with Gmail and Google Calendar APIs, including free/busy checks and calendar event creation.
- **Human-in-the-loop design**: Implements a concrete HITL pattern with interrupts, editable tool calls, and clear UX semantics around accept/edit/ignore/response.
- **Structured prompting and schemas**: Uses Pydantic schemas for structured outputs and separate modules for prompt templates and preferences.
- **Security- and environment-aware engineering**: Handles secrets via environment variables for production, without hardcoding credentials into the codebase.

## 14. Limitations or Gaps

- **Deployment story not shown**: No visible deployment configs (e.g., Docker, server scripts, CI/CD) in the inspected files.
- **State storage and persistence**: While LangGraph checkpoint dependencies are present, the high-level state persistence / storage configuration is not visible here.
- **Limited memory integration**: Memory prompts and schemas exist, but end-to-end memory integration (e.g., with a vector store or LangMem) is not fully implemented in the snippets reviewed.
- **Error handling and retries**:
  - Basic `try/except` blocks are used for Gmail calls; more robust retry and fallback logic could be added, especially around Google API quotas or transient LLM errors.
- **Scalability considerations**: There is no explicit queuing or concurrency management; the code is more aligned with a single-user assistant pattern than a multi-tenant system.

## 15. Best Future Improvements

- **Add a proper API/server wrapper** around `email_assistant` (e.g., FastAPI) to expose an HTTP endpoint for email ingestion and callback handling.
- **Introduce persistent memory** using a vector store or LangMem, wired into prompts so that the assistant can recall prior conversations, preferences, or recurring contacts.
- **Enhance observability** with LangSmith traces, structured logging, and metrics for triage accuracy, tool usage, and HITL intervention rates.
- **Implement robust retry policies** around Google APIs and LLM calls, including exponential backoff and clearer user‑facing error messages.
- **Add test coverage** for triage classification, parsing utilities, and tool wrappers, including integration tests that mock Gmail/Calendar APIs.
- **Package and document deployment** (Dockerfile, environment templates, and README sections explaining setup, credentials, and running the agent).

## 16. Recruiter-Friendly Summary

This project is a LangGraph‑powered ambient email assistant that uses OpenAI’s GPT‑4.1 to triage emails and orchestrate tool calls for Gmail and Google Calendar. It demonstrates a realistic human‑in‑the‑loop workflow where AI‑proposed email drafts and meeting invites are intercepted for approval or editing via an Agent Inbox. The code shows strong familiarity with modern LLM tooling (LangChain/LangGraph), Google APIs, and structured prompt engineering. It’s a solid example of applying agentic patterns to a concrete productivity use case.

## 17. Deep Technical Summary

At its core, the system models email processing as a LangGraph `StateGraph` with two nested phases: triage and response. Triage uses a dedicated OpenAI `gpt-4.1` model with Pydantic structured output (`RouterSchema`) and rich instructions to categorize emails as `ignore`, `notify`, or `respond`. Based on that classification, the main graph either ends, raises an interrupt for notification, or routes into a nested response agent graph.

The response agent binds an OpenAI chat model to a set of tools (`write_email`, `schedule_meeting_tool`, `calendar_freebusy`, `Question`, `Done`) and forces tool use via `tool_choice="required"`. The conversation state is modeled with `MessagesState` extended by additional fields. After each LLM step, a conditional edge inspects the last message’s tool calls: if the `Done` tool appears, the graph ends; otherwise, it transitions to an `interrupt_handler`. This handler distinguishes between tools that require HITL and those that can run automatically. For HITL tools, it builds an `interrupt` request that contains a formatted representation of the original email plus the proposed tool call. The Agent Inbox can edit or ignore tool calls, or accept them as‑is. The handler executes tools via a `tools_by_name` registry, appends tool results as messages, and may also update the original AI message with edited tool calls to maintain a coherent history.

On the integration side, Google Calendar scheduling is done via the v3 API using fully time zone‑aware datetimes and `sendUpdates="all"` to ensure attendees receive invitations. Free/busy checks call the Calendar FreeBusy endpoint and serialize busy periods into human‑readable strings. Gmail sending uses MIME message construction, base64 encoding, and the Gmail API’s `users.messages.send`, with support for both new messages and thread replies. OAuth credentials are managed via `token.json` for local runs and a base64‑encoded `GMAIL_SECRET` env var for production. Helper modules encapsulate email parsing, markdown formatting, and content extraction from LangChain message types, while `prompts.py` centralizes instructions, background, preferences, and tool descriptions for easy evolution of the assistant’s behavior.

## 18. FAQ for Another AI Assistant

1. **What is the main entrypoint to run the email assistant?**  
   Call the compiled `email_assistant` graph in `agent.py` with an `email_input` dictionary, e.g. `email_assistant.invoke({"email_input": email_dict})`.

2. **How does the system decide whether to ignore, notify, or respond to an email?**  
   It uses an LLM (`gpt-4.1`) with a structured output schema `RouterSchema` and detailed triage instructions; the LLM outputs a `classification` field (`ignore`, `notify`, or `respond`) along with reasoning, and the graph routes based on that value.

3. **Where are the prompts and background instructions defined?**  
   In `utils/prompts.py`, which contains triage prompts, agent prompts (with and without HITL), default background, response preferences, calendar preferences, and tool description templates.

4. **How can I change what counts as an “important” email?**  
   Edit `default_triage_instructions` in `prompts.py` to adjust the rules for what should be ignored, notified, or responded to; these instructions directly guide the triage LLM.

5. **How are Gmail and Google Calendar credentials handled?**  
   `utils/gmail.py` manages credentials: locally it uses `credentials.json` and `token.json`; in production it can decode a base64‑encoded `GMAIL_SECRET` env var to obtain credentials and then builds Calendar and Gmail service clients.

6. **How does human-in-the-loop review work for tool calls?**  
   The `interrupt_handler` node inspects each tool call; for sensitive tools (`write_email`, `schedule_meeting`, `Question`) it creates a structured `interrupt` request with a description and a config specifying allowed actions; the Agent Inbox response (`accept`, `edit`, `ignore`, `response`) determines whether the tool is executed, edited, or skipped.

7. **What tools can the LLM call, and what do they do?**  
   Tools in `utils/tools.py` include `write_email` (send Gmail messages, optionally in an existing thread), `schedule_meeting_tool` (create Calendar events), `calendar_freebusy` (check daily availability), `Question` (ask user follow‑up questions), and `Done` (mark workflow completion).

8. **How are emails formatted for display to the user or LLM?**  
   `format_email_markdown` and `format_gmail_markdown` in `utils/helpers.py` convert email details to markdown, optionally converting HTML content to readable text, which is then used in prompts and Agent Inbox descriptions.

9. **How does the system prevent infinite loops of tool calls?**  
   The `should_continue` function checks the last message for tool calls and especially for the `Done` tool; if `Done` is present or there are no tool calls, the graph routes to `END` instead of back to `interrupt_handler`.

10. **Is there any notion of long-term memory or user preferences?**  
    `utils/prompts.py` and `utils/schemas.py` define memory update instructions and a `UserPreferences` model that can be used to maintain user-specific rules, but the full wiring to a persistence layer or retrieval system is not fully shown in the inspected code.

11. **How can I adapt this assistant to a different time zone or email account?**  
    Change the default `timezone_str` and `calendar_id` in `schedule_meeting` within `utils/gmail.py`, and modify the hardcoded sender email in `send_gmail`; for production, ensure the appropriate Google credentials and scopes are configured.

12. **Can this system handle HTML-heavy marketing emails?**  
    Yes, `format_gmail_markdown` detects HTML content and converts it to markdown using `html2text`, which makes these emails more legible to both humans and LLMs during triage and response.

## 19. Confidence and Uncertainty Notes

- **High confidence** in the description of email triage, the response agent graph, HITL behavior, and Gmail/Calendar tool wiring, as these are directly reflected in the code under `src/my_agent`.
- **High confidence** in the tech stack details derived from `pyproject.toml` and imports.
- **Medium confidence** regarding how memory and user preferences are used at runtime, since the prompts and models exist but the full integration pipeline is not visible in the inspected code.
- **Low confidence** about deployment, multi-user support, and observability setup, as related configuration files (Docker, CI, infra) were not part of the reviewed files.

## Machine Summary

```json
{
  "project_name": "ambient_agents2 (Ambient Email Assistant)",
  "project_type": "LangGraph-based AI email and calendar assistant with human-in-the-loop control",
  "summary_short": "An AI-powered ambient email assistant that triages messages and orchestrates Gmail and Google Calendar actions via a LangGraph workflow with human-in-the-loop review.",
  "primary_language": ["Python"],
  "frameworks": ["LangGraph", "LangChain", "LangChain OpenAI"],
  "key_features": [
    "LLM-based email triage into ignore/notify/respond",
    "LangGraph state graph orchestrating triage and response flows",
    "Gmail integration for sending and replying to emails",
    "Google Calendar integration for scheduling meetings and checking availability",
    "Human-in-the-loop review of tool calls via LangGraph interrupts",
    "Structured prompts and Pydantic schemas for reliable model outputs"
  ],
  "architecture_style": "Agentic workflow orchestrated by LangGraph state machines with nested subgraphs and tool-based LLM interactions",
  "deployment_signals": [
    "Environment-based credential handling via GMAIL_SECRET",
    "Use of OAuth tokens and token refresh for Google APIs",
    "Separation of local vs production credential flows"
  ],
  "ai_capabilities": [
    "Email triage classification with structured reasoning",
    "Tool-using LLM for email drafting and meeting scheduling",
    "Human-in-the-loop editing and approval of AI-generated actions"
  ],
  "data_sources": [
    "Gmail messages via Google API",
    "Google Calendar events and free/busy data"
  ],
  "notable_strengths": [
    "Realistic application of LangGraph for multi-step agent workflows",
    "Robust integration with Gmail and Google Calendar",
    "Clear separation of prompts, tools, schemas, and helpers",
    "Thoughtful HITL design for safety and control"
  ],
  "limitations": [
    "No explicit deployment or CI configuration in the inspected code",
    "Memory and user preference learning not fully wired to persistent storage",
    "Limited test coverage and resilience patterns visible in code"
  ],
  "confidence": "High confidence in core architecture, features, and stack based on source files; medium to low confidence about production deployment details and long-term memory integration."
}
```
