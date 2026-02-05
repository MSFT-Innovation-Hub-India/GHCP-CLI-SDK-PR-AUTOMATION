"""
Progress Tracker & Call Logger
==============================
Provides visual progress tracking and API call logging for the fleet compliance agent.

Features:
- Step-by-step progress visualization with timing
- API/MCP call tracking with request/response logging
- Summary report generation at the end of each run
- Optional file-based run logging

Usage:
    from fleet_agent.tracker import tracker, step, track_call

    with step("Clone repository"):
        clone_repo(url, path)
    
    with track_call("RAG", "vector_search", query=query):
        results = search(query)
"""

from __future__ import annotations
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Any
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import os


@dataclass
class CallRecord:
    """Record of an API/service call."""
    service: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "pending"
    request_summary: Optional[str] = None
    response_summary: Optional[str] = None
    error: Optional[str] = None


@dataclass
class StepRecord:
    """Record of a workflow step."""
    name: str
    repo: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "pending"
    calls: list[CallRecord] = field(default_factory=list)


class ProgressTracker:
    """
    Tracks progress and API calls across the fleet compliance agent workflow.
    
    Features:
    - Visual step indicators (⏳ → ✓ or ✗)
    - Nested call tracking within steps
    - Timing for all operations
    - Summary report at end of run
    """
    
    # Step icons
    ICON_PENDING = "⏳"
    ICON_SUCCESS = "✓"
    ICON_FAILED = "✗"
    ICON_SKIPPED = "○"
    ICON_ARROW = "→"
    ICON_CALL = "  📡"
    ICON_INFO = "  ℹ"
    
    def __init__(self, verbose: bool = True, log_file: Optional[Path] = None):
        self.verbose = verbose
        self.log_file = log_file
        self.run_id = f"run-{int(time.time())}"
        self.run_start: Optional[float] = None
        self.run_end: Optional[float] = None
        self.steps: list[StepRecord] = []
        self.current_step: Optional[StepRecord] = None
        self.current_repo: Optional[str] = None
        self.total_calls = 0
        self.failed_calls = 0
        
    def start_run(self, title: str = "Fleet Compliance Agent") -> None:
        """Start a new tracking run."""
        self.run_start = time.time()
        self.steps = []
        self.total_calls = 0
        self.failed_calls = 0
        
        if self.verbose:
            print()
            print("=" * 60)
            print(f"  {title}")
            print(f"  Run ID: {self.run_id}")
            print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print()
    
    def set_repo(self, repo_name: str) -> None:
        """Set current repository context."""
        self.current_repo = repo_name
        if self.verbose:
            print()
            print(f"┌{'─' * 58}┐")
            print(f"│  Repository: {repo_name:<43} │")
            print(f"└{'─' * 58}┘")
    
    def start_step(self, name: str, details: Optional[str] = None) -> StepRecord:
        """Start tracking a new step."""
        step = StepRecord(
            name=name,
            repo=self.current_repo,
            start_time=time.time(),
        )
        self.steps.append(step)
        self.current_step = step
        
        if self.verbose:
            detail_str = f" ({details})" if details else ""
            print(f"{self.ICON_PENDING} {name}{detail_str}...", end="", flush=True)
        
        return step
    
    def end_step(self, status: str = "success", message: Optional[str] = None) -> None:
        """End the current step."""
        if not self.current_step:
            return
            
        self.current_step.end_time = time.time()
        self.current_step.duration_ms = (self.current_step.end_time - self.current_step.start_time) * 1000
        self.current_step.status = status
        
        if self.verbose:
            icon = self.ICON_SUCCESS if status == "success" else (self.ICON_FAILED if status == "failed" else self.ICON_SKIPPED)
            duration_str = f" [{self.current_step.duration_ms:.0f}ms]"
            msg_str = f" - {message}" if message else ""
            print(f"\r{icon} {self.current_step.name}{duration_str}{msg_str}")
        
        self.current_step = None
    
    def skip_step(self, name: str, reason: str) -> None:
        """Record a skipped step."""
        step = StepRecord(
            name=name,
            repo=self.current_repo,
            start_time=time.time(),
            end_time=time.time(),
            duration_ms=0,
            status="skipped",
        )
        self.steps.append(step)
        
        if self.verbose:
            print(f"{self.ICON_SKIPPED} {name} (skipped: {reason})")
    
    def start_call(
        self, 
        service: str, 
        operation: str, 
        request_summary: Optional[str] = None
    ) -> CallRecord:
        """Start tracking an API/service call."""
        call = CallRecord(
            service=service,
            operation=operation,
            start_time=time.time(),
            request_summary=request_summary,
        )
        
        if self.current_step:
            self.current_step.calls.append(call)
        
        self.total_calls += 1
        
        if self.verbose:
            req_str = f": {request_summary[:40]}..." if request_summary and len(request_summary) > 40 else (f": {request_summary}" if request_summary else "")
            print(f"\n{self.ICON_CALL} {service}.{operation}{req_str}", end="", flush=True)
        
        return call
    
    def end_call(
        self, 
        call: CallRecord, 
        status: str = "success", 
        response_summary: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """End tracking an API/service call."""
        call.end_time = time.time()
        call.duration_ms = (call.end_time - call.start_time) * 1000
        call.status = status
        call.response_summary = response_summary
        call.error = error
        
        if status == "failed":
            self.failed_calls += 1
        
        if self.verbose:
            icon = self.ICON_SUCCESS if status == "success" else self.ICON_FAILED
            duration_str = f" [{call.duration_ms:.0f}ms]"
            resp_str = f" {self.ICON_ARROW} {response_summary[:30]}..." if response_summary and len(response_summary) > 30 else (f" {self.ICON_ARROW} {response_summary}" if response_summary else "")
            error_str = f" ERROR: {error}" if error else ""
            print(f" {icon}{duration_str}{resp_str}{error_str}")
    
    def info(self, message: str) -> None:
        """Print an info message."""
        if self.verbose:
            print(f"{self.ICON_INFO} {message}")
    
    def end_run(self) -> dict:
        """End the run and print summary."""
        self.run_end = time.time()
        total_duration = (self.run_end - self.run_start) * 1000 if self.run_start else 0
        
        # Calculate stats
        successful_steps = sum(1 for s in self.steps if s.status == "success")
        failed_steps = sum(1 for s in self.steps if s.status == "failed")
        skipped_steps = sum(1 for s in self.steps if s.status == "skipped")
        
        # Group steps by repo
        repos_processed = set(s.repo for s in self.steps if s.repo)
        
        summary = {
            "run_id": self.run_id,
            "total_duration_ms": total_duration,
            "repos_processed": len(repos_processed),
            "steps": {
                "total": len(self.steps),
                "successful": successful_steps,
                "failed": failed_steps,
                "skipped": skipped_steps,
            },
            "calls": {
                "total": self.total_calls,
                "failed": self.failed_calls,
            },
        }
        
        if self.verbose:
            print()
            print("=" * 60)
            print("  RUN SUMMARY")
            print("=" * 60)
            print(f"  Duration:        {total_duration/1000:.2f}s")
            print(f"  Repositories:    {len(repos_processed)}")
            print(f"  Steps:           {successful_steps} ✓  {failed_steps} ✗  {skipped_steps} ○")
            print(f"  API Calls:       {self.total_calls} total, {self.failed_calls} failed")
            print()
            
            # Call breakdown by service
            call_stats: dict[str, int] = {}
            for step in self.steps:
                for call in step.calls:
                    key = call.service
                    call_stats[key] = call_stats.get(key, 0) + 1
            
            if call_stats:
                print("  Call Breakdown:")
                for service, count in sorted(call_stats.items()):
                    print(f"    {service}: {count} calls")
            
            print("=" * 60)
            print()
        
        # Write to log file if specified
        if self.log_file:
            self._write_log(summary)
        
        return summary
    
    def _write_log(self, summary: dict) -> None:
        """Write detailed run log to file."""
        log_data = {
            **summary,
            "steps": [
                {
                    "name": s.name,
                    "repo": s.repo,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "calls": [
                        {
                            "service": c.service,
                            "operation": c.operation,
                            "status": c.status,
                            "duration_ms": c.duration_ms,
                            "error": c.error,
                        }
                        for c in s.calls
                    ]
                }
                for s in self.steps
            ]
        }
        
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# Global tracker instance
tracker = ProgressTracker(
    verbose=os.getenv("TRACKER_VERBOSE", "true").lower() == "true"
)


@contextmanager
def step(name: str, details: Optional[str] = None):
    """
    Context manager for tracking a workflow step.
    
    Usage:
        with step("Clone repository", details="contoso-api"):
            clone_repo(url, path)
    """
    step_record = tracker.start_step(name, details)
    try:
        yield step_record
        tracker.end_step("success")
    except Exception as e:
        tracker.end_step("failed", str(e))
        raise


@contextmanager
def track_call(
    service: str, 
    operation: str, 
    request_summary: Optional[str] = None,
    capture_response: bool = True
):
    """
    Context manager for tracking an API/service call.
    
    Usage:
        with track_call("RAG", "vector_search", query[:50]) as call:
            results = search(query)
            call.response_summary = f"{len(results)} results"
    """
    call = tracker.start_call(service, operation, request_summary)
    try:
        yield call
        tracker.end_call(call, "success", call.response_summary)
    except Exception as e:
        tracker.end_call(call, "failed", error=str(e))
        raise
