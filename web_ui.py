"""Dependency-free browser UI for the startup launch agent."""

from __future__ import annotations

import argparse
import json
import sqlite3
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from urllib.parse import urlparse

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent import DB_PATH, build_graph, save_artifact, safe_project_id


ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "ui"


def graph_for_request():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    return build_graph(SqliteSaver(connection)), connection


def public_state(values: dict) -> dict:
    keys = (
        "project_id",
        "startup_idea",
        "goal",
        "research_plan",
        "research_findings",
        "pain_points",
        "hypotheses",
        "selected_hypothesis",
        "validation_plan",
        "thirty_day_roadmap",
        "current_phase",
        "status",
    )
    return {key: values.get(key, "") for key in keys}


class StartupUIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {format % args}")

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/projects/"):
            self.get_project(path.removeprefix("/api/projects/"))
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/projects":
                self.start_project()
            elif path.startswith("/api/projects/") and path.endswith("/resume"):
                project_id = path.removeprefix("/api/projects/").removesuffix("/resume")
                self.resume_project(project_id)
            else:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def start_project(self) -> None:
        data = self.read_json()
        idea = str(data.get("idea", "")).strip()
        raw_id = str(data.get("project_id", "")).strip()
        if not idea or not raw_id:
            self.send_json(
                {"error": "Startup idea and project ID are required."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        project_id = safe_project_id(raw_id)
        config = {"configurable": {"thread_id": project_id}}
        graph, connection = graph_for_request()
        try:
            existing = graph.get_state(config)
            if existing.values:
                self.send_json(
                    {"error": "That project ID already exists. Choose another."},
                    HTTPStatus.CONFLICT,
                )
                return
            result = graph.invoke(
                {
                    "project_id": project_id,
                    "startup_idea": idea,
                    "goal": "Identify the highest-value problem to validate before building an MVP.",
                    "current_phase": "planning",
                    "status": "running",
                },
                config=config,
            )
            self.send_json(self.result_payload(graph, config, result))
        finally:
            connection.close()

    def resume_project(self, raw_project_id: str) -> None:
        data = self.read_json()
        choice = str(data.get("choice", "")).strip()
        if not choice:
            self.send_json({"error": "Select a hypothesis first."}, HTTPStatus.BAD_REQUEST)
            return
        project_id = safe_project_id(raw_project_id)
        config = {"configurable": {"thread_id": project_id}}
        graph, connection = graph_for_request()
        try:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                self.send_json({"error": "Project not found."}, HTTPStatus.NOT_FOUND)
                return
            result = graph.invoke(Command(resume=choice), config=config)
            self.send_json(self.result_payload(graph, config, result))
        finally:
            connection.close()

    def get_project(self, raw_project_id: str) -> None:
        try:
            project_id = safe_project_id(raw_project_id)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        config = {"configurable": {"thread_id": project_id}}
        graph, connection = graph_for_request()
        try:
            snapshot = graph.get_state(config)
            if not snapshot.values:
                self.send_json({"error": "Project not found."}, HTTPStatus.NOT_FOUND)
                return
            payload = {"state": public_state(dict(snapshot.values))}
            if snapshot.interrupts:
                payload["decision"] = snapshot.interrupts[0].value
            self.send_json(payload)
        finally:
            connection.close()

    @staticmethod
    def result_payload(graph, config: dict, result: dict) -> dict:
        state = dict(graph.get_state(config).values)
        payload = {"state": public_state(state)}
        if "__interrupt__" in result:
            payload["decision"] = result["__interrupt__"][0].value
        if state.get("status") == "completed":
            payload["artifact"] = str(save_artifact(state))
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Startup Agent browser interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), StartupUIHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Startup Agent UI running at {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
