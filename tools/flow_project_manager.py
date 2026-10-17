# -*- coding: utf-8 -*-
"""Daily Project Manager for Google Flow CDP Automation.

Automatically manages and creates fresh daily project workspaces on flow.google.com:
- Tracks current date's project URL in output/flow_daily_projects.json.
- Reuses today's active project across hourly character & garment tasks.
- When a new date begins, automatically triggers 'New project' on flow.google.com via CDP,
  registers the new project URL, and closes previous days' canvas tabs to keep memory minimal.
"""
import os
import sys
import json
import time
import datetime
import urllib.request
import websocket
from pathlib import Path

CDP_BASE_URL = "http://127.0.0.1:9222"
DAILY_PROJECTS_FILE = Path(__file__).resolve().parent.parent / "output" / "flow_daily_projects.json"


def load_daily_projects():
    if DAILY_PROJECTS_FILE.exists():
        try:
            return json.loads(DAILY_PROJECTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_daily_projects(data):
    DAILY_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DAILY_PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_flow_project_from_cdp():
    try:
        req = urllib.request.urlopen(f"{CDP_BASE_URL}/json", timeout=4)
        targets = json.loads(req.read().decode())
    except Exception:
        return None

    for t in targets:
        url = t.get("url", "")
        if "flow.google.com/project/" in url and t.get("type") == "page":
            return {
                "id": t.get("id"),
                "url": url,
                "title": t.get("title", ""),
                "ws_url": t.get("webSocketDebuggerUrl")
            }
    return None


def create_new_project_via_cdp():
    """Create a new project by opening flow.google.com and clicking 'New project'."""
    try:
        # 1. Open new tab to flow.google.com
        req = urllib.request.Request(f"{CDP_BASE_URL}/json/new?https://flow.google.com/", method="PUT")
        tab_info = json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
        target_id = tab_info.get("id")
        ws_url = tab_info.get("webSocketDebuggerUrl")

        time.sleep(4)
        ws = websocket.create_connection(ws_url, timeout=20, suppress_origin=True)

        # 2. Click 'New project'
        js_click_new = """
        (() => {
            const btn = Array.from(document.querySelectorAll('button')).find(el => {
                const txt = (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase();
                return txt.includes('new project') || txt.includes('create project');
            });
            if (btn) {
                btn.click();
                return { success: true, text: btn.innerText.trim() };
            }
            return { success: false };
        })()
        """
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_click_new, 'returnByValue': True}}))
        raw = ws.recv()

        # 3. Wait for redirection to project/<uuid>
        new_url = None
        for _ in range(15):
            time.sleep(1)
            ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': 'window.location.href', 'returnByValue': True}}))
            res = json.loads(ws.recv())
            cur_url = res.get('result', {}).get('result', {}).get('value', '')
            if "flow.google.com/project/" in cur_url and not cur_url.endswith("/project/"):
                new_url = cur_url
                break

        ws.close()

        if new_url:
            # Close other older flow project tabs
            try:
                t_req = urllib.request.urlopen(f"{CDP_BASE_URL}/json", timeout=4)
                targets = json.loads(t_req.read().decode())
                for t in targets:
                    if t.get("id") != target_id and "flow.google.com/project/" in t.get("url", ""):
                        urllib.request.urlopen(f"{CDP_BASE_URL}/json/close/{t.get('id')}", timeout=4)
            except Exception:
                pass
            return new_url
    except Exception as e:
        print(f"[!] Error creating new Flow project: {e}", file=sys.stderr)
        return None


def get_or_create_daily_project(target_date=None):
    """Retrieve existing project for target_date (YYYY-MM-DD), or create a fresh one."""
    today_str = target_date or datetime.date.today().strftime("%Y-%m-%d")
    projects = load_daily_projects()

    if today_str in projects and projects[today_str].get("project_url"):
        return projects[today_str]["project_url"]

    # Check if there's already an active Flow project tab in Chrome
    active_tab = get_active_flow_project_from_cdp()
    if active_tab:
        project_url = active_tab["url"]
        projects[today_str] = {
            "project_url": project_url,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": active_tab.get("title", "")
        }
        save_daily_projects(projects)
        return project_url

    # Create new project
    print(f"[+] Creating a fresh daily Google Flow project for {today_str}...")
    new_url = create_new_project_via_cdp()
    if new_url:
        projects[today_str] = {
            "project_url": new_url,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": f"Google Flow Daily Project {today_str}"
        }
        save_daily_projects(projects)
        return new_url

    # Fallback to default
    return "https://flow.google.com/project/bbd7b0d1-bd3e-4cc0-9143-201c503ca526"


if __name__ == "__main__":
    url = get_or_create_daily_project()
    print(f"Daily Project URL: {url}")
