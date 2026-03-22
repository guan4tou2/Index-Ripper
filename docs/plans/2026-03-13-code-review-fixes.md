# Index-Ripper Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 issues identified in code review: (1) test failure due to UI architecture mismatch, (2) partial file cleanup on download failure, (3) ThreadPoolExecutor resource management.

**Architecture:** Incremental fixes to existing code without architectural changes.

**Tech Stack:** Python 3.11+, CustomTkinter, requests, BeautifulSoup

---

### Task 1: Fix test_has_treeview Failure

**Files:**
- Modify: `test_ui_ctk.py:86-93`
- Verify: Run `uv run pytest test_ui_ctk.py::TestWebsiteCopierCtkSmoke::test_has_treeview -v`

**Root Cause:** Test checks for `app.tree` (ttk.Treeview) but `WebsiteCopierCtk` uses custom UI with `tree_nodes`, `tree_roots`, `_row_widgets`, `tree_scroll_frame`.

**Step 1: Update test to check correct attributes**

```python
def test_has_treeview(self):
    import ui_ctk, importlib
    importlib.reload(ui_ctk)
    app = ui_ctk.WebsiteCopierCtk(ui_smoke=False)
    app.window.after(0, app.window.destroy)
    app.run()
    # CTk version uses custom FileTree components, not ttk.Treeview
    self.assertTrue(hasattr(app, "tree_nodes"))
    self.assertTrue(hasattr(app, "tree_roots"))
    self.assertTrue(hasattr(app, "tree_scroll_frame"))
    self.assertTrue(hasattr(app, "search_var"))
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_ui_ctk.py::TestWebsiteCopierCtkSmoke::test_has_treeview -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_ui_ctk.py
git commit -m "fix(test): update test_has_treeview to match CTk UI architecture"
```

---

### Task 2: Add Partial File Cleanup on Download Failure

**Files:**
- Modify: `backend.py:303-351`

**Root Cause:** When download is canceled/fails/stopped, partial file remains on disk.

**Step 1: Add cleanup helper function**

Add at top of `backend.py` after imports:
```python
def _cleanup_partial_file(file_path: str) -> None:
    """Remove partial download file if it exists."""
    try:
        import os
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # Best-effort cleanup
```

**Step 2: Add cleanup calls in download_file**

Modify `backend.py` - add cleanup in these 3 locations:

1. After cancel detection (around line 314):
```python
if cancel_event is not None and cancel_event.is_set():
    self.ui_manager.log_message(f"[Download] Canceled: {file_name}")
    _cleanup_partial_file(file_path)  # ADD THIS LINE
    try:
        self.ui_manager.update_download_status(file_path, "Canceled")
    except AttributeError:
        pass
    return False
```

2. After should_stop check (around line 317):
```python
if self.should_stop:
    self._log(f"[Download] Stopping download for {file_name}")
    _cleanup_partial_file(file_path)  # ADD THIS LINE
    return False
```

3. In exception handlers (around lines 341 and 351):
```python
except requests.exceptions.RequestException as ex:
    self._log(f"[Download] Error downloading {file_name}: {str(ex)}")
    _cleanup_partial_file(file_path)  # ADD THIS LINE
    try:
        self.ui_manager.update_download_status(file_path, "Failed")
        self.ui_manager.log_message(f"[Download] Error: {file_name} - {ex}")
    except AttributeError:
        pass
    return False
```

And:
```python
except IOError as ex:
    self._log(f"[Download] File error for {file_name}: {str(ex)}")
    _cleanup_partial_file(file_path)  # ADD THIS LINE
    try:
        self.ui_manager.update_download_status(file_path, "Failed")
        self.ui_manager.log_message(f"[Download] File error: {file_name} - {ex}")
    except AttributeError:
        pass
    return False
```

**Step 3: Run tests to verify no regressions**

Run: `uv run pytest test_backend.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add backend.py
git commit -m "fix(backend): cleanup partial files on download cancel/failure"
```

---

### Task 3: Fix ThreadPoolExecutor Resource Management

**Files:**
- Modify: `index_ripper.py:1183-1194`
- Verify: Run `uv run pytest test_ui_ctk.py -v`

**Root Cause:** `update_thread_count` shuts down old executor without waiting, then immediately creates new one, potentially causing resource leaks.

**Step 1: Fix executor shutdown sequence**

Modify `index_ripper.py` lines 1183-1194:

```python
def update_thread_count(self, new_count_str: str):
    """Updates the number of concurrent download threads."""
    try:
        new_count = int(new_count_str)
        if 1 <= new_count <= 10:
            old_executor = self.executor
            self.max_workers = new_count
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
            # Shutdown old executor after new one is ready
            old_executor.shutdown(wait=True, cancel_futures=False)
    except (ValueError, TypeError):
        pass
```

**Step 2: Run tests to verify no regressions**

Run: `uv run pytest test_ui_ctk.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add index_ripper.py
git commit -m "fix: properly shutdown ThreadPoolExecutor before creating new one"
```

---

### Task 4: Final Verification

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (44 passed, 1 skipped)

**Step 2: Verify no lint errors**

Run: `uv run python -m py_compile index_ripper.py backend.py test_ui_ctk.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: code review fixes - test update, partial file cleanup, executor management"
```
