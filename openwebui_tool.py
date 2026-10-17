"""
title: AYA Saved Export Recipes
description: Export authorized JSON uploads through an independently verified component.
version: 0.1.0
"""

import asyncio
import io
import json
import os
from pathlib import Path

import aiohttp
from fastapi import UploadFile
from pydantic import BaseModel, Field
from starlette.datastructures import Headers

from open_webui.models.tools import Tools as ToolStore
from open_webui.models.users import Users
from open_webui.routers.files import get_file_content_by_id, upload_file_handler


class Tools:
    class UserValves(BaseModel):
        recipes: dict = Field(default_factory=dict, description="Saved JSON export recipes")

    async def save_recipe(self, name: str, columns_json: str, __user__: dict, __id__: str = "aya_recipes") -> str:
        """Save ordered columns for the signed-in user. columns_json is a JSON array of label/path/fallback objects."""
        if not name.strip() or len(name) > 80 or len(columns_json.encode()) > 16_384:
            return "Invalid recipe name or size."
        columns = json.loads(columns_json)
        check = await self._call_runtime({"records": [], "columns": columns})
        if "error" in check:
            return "Recipe rejected: " + check["error"]
        settings = await ToolStore.get_user_valves_by_id_and_user_id(__id__, __user__["id"]) or {}
        recipes = settings.get("recipes", {})
        if name not in recipes and len(recipes) >= 32:
            return "Recipe limit reached."
        recipes[name] = columns
        settings["recipes"] = recipes
        result = await ToolStore.update_user_valves_by_id_and_user_id(__id__, __user__["id"], settings)
        if result is None:
            raise RuntimeError("Could not save recipe")
        return f"Saved recipe '{name}' for your account."

    async def list_recipes(self, __user__: dict, __id__: str = "aya_recipes") -> str:
        """List the signed-in user's saved export recipes."""
        settings = await ToolStore.get_user_valves_by_id_and_user_id(__id__, __user__["id"]) or {}
        return json.dumps(settings.get("recipes", {}), ensure_ascii=False)

    async def export_file(self, file_id: str, recipe_name: str, __user__: dict, __request__,
                          __id__: str = "aya_recipes") -> str:
        """Apply a saved recipe to an uploaded JSON file. Return a table preview and a CSV download link."""
        user = await Users.get_user_by_id(__user__["id"])
        if user is None:
            raise PermissionError("Sign in to export files")
        settings = await ToolStore.get_user_valves_by_id_and_user_id(__id__, user.id) or {}
        columns = settings.get("recipes", {}).get(recipe_name)
        if columns is None:
            return "Recipe not found. Save a recipe first."
        response = await get_file_content_by_id(file_id, user=user, db=None)
        if not hasattr(response, "path"):
            return "Upload a JSON file with stored bytes."
        path = Path(response.path)
        if path.stat().st_size > 1_048_576:
            return "File exceeds the 1 MiB input limit."
        records = json.loads(await asyncio.to_thread(path.read_bytes))
        result = await self._call_runtime({"records": records, "columns": columns})
        if "error" in result:
            return "Export rejected: " + result["error"]
        export = UploadFile(file=io.BytesIO(result["csv"].encode()), filename="aya-export.csv",
                            headers=Headers({"content-type": "text/csv"}))
        saved = await upload_file_handler(__request__, file=export, metadata={}, process=False,
                                         process_in_background=False, user=user, db=None)
        identity = saved["id"] if isinstance(saved, dict) else saved.id
        def cell(value):
            return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        lines = [" | ".join(cell(x) for x in result["columns"]), " | ".join("---" for _ in result["columns"])]
        lines += [" | ".join(cell(x) for x in row) for row in result["rows"][:10]]
        return (f"Exported {len(result['rows'])} rows with recipe **{recipe_name}**.\n\n"
                + "\n".join(lines) + f"\n\n[Download CSV](/api/v1/files/{identity}/content)\n\n"
                + f"Verified module: `{result.get('module_sha256', 'unknown')}`")

    async def _call_runtime(self, payload: dict) -> dict:
        url = os.environ["AYA_RUNTIME_URL"]
        token = os.environ["AYA_RUNTIME_TOKEN"]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(url, json=payload, headers={"Authorization": "Bearer " + token}) as response:
                response.raise_for_status()
                return await response.json()
