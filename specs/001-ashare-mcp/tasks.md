---
description: "Task list for A-Share Financial Data MCP Server"
---

# Tasks: A-Share Financial Data MCP Server

**Input**: Design documents from `/specs/001-ashare-mcp/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are explicitly requested due to TDD methodology (user rules).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2])
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create python source directory structure (`src/core/`, `src/tools/`, `src/utils/`, `tests/` etc.)
- [x] T002 Initialize Python project and install dependencies (`mcp`, `akshare`, `pandas`, `pytest`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [x] T003 Setup core application logging and `server.py` MCP skeleton
- [x] T004 [P] Create `src/utils/file_utils.py` for standardizing markdown/csv file output
- [x] T005 [P] Create unit tests for `src/utils/file_utils.py` in `tests/unit/test_file_utils.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Fetch Company Financial Data for Valuation (Priority: P1) 🎯 MVP

**Goal**: As an AI Agent conducting company research, I want to provide a company code to the MCP tool, so that it can automatically fetch the company's recent years of financial data, current stock price, and circulating shares, and save them as local files.

**Independent Test**: Can be fully tested by calling the MCP tool with a valid stock code (e.g., '600519') and verifying that the corresponding data files are created in the current directory containing correct historical financial data, current price, and circulating shares.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Write unit test for `core/akshare_client.py`'s financial fetching logic in `tests/unit/test_akshare_client_financials.py`
- [x] T007 [P] [US1] Write contract test for `get_financials` tool handler in `tests/integration/test_get_financials.py` (Mocking akshare outputs)

### Implementation for User Story 1

- [x] T008 [P] [US1] Implement core `akshare` fetching functions (price, snapshot, indicator history) in `src/core/akshare_client.py` 
- [x] T009 [US1] Implement `get_financials` MCP tool handler in `src/tools/get_financials.py`
- [x] T010 [US1] Register `get_financials` tool in `src/server.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Find Stock Code by Name (Priority: P2)

**Goal**: As an AI Agent conducting company research, I want to provide a company's name to a tool, so that it can return the exact stock code needed for fetching the financial data.

**Independent Test**: Can be tested by providing a name like "贵州茅台" to the tool and checking if it returns the correct stock code "600519".

### Tests for User Story 2 ⚠️

- [x] T011 [P] [US2] Write unit test for `core/akshare_client.py`'s search logic in `tests/unit/test_akshare_client_search.py`
- [x] T012 [P] [US2] Write contract test for `search_stock` tool handler in `tests/integration/test_search_stock.py`

### Implementation for User Story 2

- [x] T013 [P] [US2] Implement stock search logic mapping name to code in `src/core/akshare_client.py`
- [x] T014 [US2] Implement `search_stock` MCP tool handler in `src/tools/search_stock.py`
- [x] T015 [US2] Register `search_stock` tool in `src/server.py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T016 [P] Implement graceful error handling across `tools/` and `core/` to ensure descriptive strings instead of runtime exceptions.
- [x] T017 Run manual validation using `quickstart.md` scenarios natively with the test CLI or MCP inspector.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion
- **User Stories (Phase 3+)**: All depend on Phase 2 completion
  - User Story 1 and 2 can proceed in parallel but sequential order is recommended.
- **Polish (Final Phase)**: Depends on User Stories

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational
- **User Story 2 (P2)**: Can start after Foundational

### Parallel Opportunities

- Tests within the same story ([P] marked) can be developed concurrently before implementation.
