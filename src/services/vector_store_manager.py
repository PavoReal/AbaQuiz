"""
Vector Store Manager for OpenAI File Search API.

Manages the OpenAI vector store containing BCBA study content.
Handles creation, file uploads, synchronization, and state persistence.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from openai import AsyncOpenAI

from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


@dataclass
class FileInfo:
    """Information about a file in the vector store."""

    filename: str
    file_id: str
    uploaded_at: str
    size_bytes: int
    checksum: str


@dataclass
class SyncResult:
    """Result of a sync operation."""

    added: list[str]
    removed: list[str]
    unchanged: list[str]
    errors: list[str]


class VectorStoreManager:
    """Manages OpenAI vector store for BCBA content."""

    STORE_NAME = "abaquiz-bcba-content"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            max_retries=3,
        )
        self.state_file = Path(__file__).parent.parent.parent / "data" / ".vector_store_state.json"
        self.content_dir = Path(__file__).parent.parent.parent / "data" / "processed"

    def _load_state(self) -> dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"

    async def get_store_id(self) -> Optional[str]:
        """Get the vector store ID from state file."""
        state = self._load_state()
        return state.get("vector_store_id")

    async def create_store(self, name: Optional[str] = None) -> str:
        """Create a new vector store.

        Args:
            name: Optional custom name for the store.

        Returns:
            The vector store ID.

        Raises:
            RuntimeError: If store creation fails.
        """
        store_name = name or self.STORE_NAME
        existing_id = await self.get_store_id()

        if existing_id:
            logger.warning(f"Vector store already exists: {existing_id}")
            # Verify it still exists in OpenAI
            try:
                store = await self.client.vector_stores.retrieve(existing_id)
                logger.info(f"Existing vector store verified: {store.id}")
                return store.id
            except Exception:
                logger.warning("Existing store not found in OpenAI, creating new one")

        try:
            store = await self.client.vector_stores.create(name=store_name)
            logger.info(f"Created vector store: {store.id}")

            # Save state
            state = {
                "vector_store_id": store.id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_sync": None,
                "files": {},
            }
            self._save_state(state)

            return store.id
        except Exception as e:
            raise RuntimeError(f"Failed to create vector store: {e}") from e

    async def upload_files(self, directory: Optional[Path] = None) -> list[str]:
        """Upload all .md files from directory to vector store.

        Args:
            directory: Directory containing markdown files. Defaults to content_dir.

        Returns:
            List of uploaded file IDs.

        Raises:
            RuntimeError: If no vector store exists or upload fails.
        """
        store_id = await self.get_store_id()
        if not store_id:
            raise RuntimeError(
                "No vector store configured. Run: python -m src.scripts.manage_vector_store create"
            )

        content_dir = directory or self.content_dir
        md_files = list(content_dir.glob("*.md"))

        # Exclude index file
        md_files = [f for f in md_files if f.name != "00_index.md"]

        if not md_files:
            logger.warning(f"No markdown files found in {content_dir}")
            return []

        state = self._load_state()
        uploaded_ids = []

        for file_path in md_files:
            try:
                # Upload file to OpenAI
                with open(file_path, "rb") as f:
                    file_obj = await self.client.files.create(
                        file=f,
                        purpose="assistants",
                    )

                # Attach to vector store
                await self.client.vector_stores.files.create(
                    vector_store_id=store_id,
                    file_id=file_obj.id,
                )

                # Update state
                checksum = self._compute_checksum(file_path)
                state["files"][file_path.name] = {
                    "file_id": file_obj.id,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                    "size_bytes": file_path.stat().st_size,
                    "checksum": checksum,
                }
                uploaded_ids.append(file_obj.id)

                logger.info(f"Uploaded: {file_path.name} -> {file_obj.id}")

            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")

        state["last_sync"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)

        logger.info(f"Uploaded {len(uploaded_ids)} files to vector store {store_id}")
        return uploaded_ids

    async def sync(self) -> SyncResult:
        """Synchronize local files with vector store.

        Detects new/changed files and uploads them. Removes files that no longer exist locally.

        Returns:
            SyncResult with details of what changed.
        """
        store_id = await self.get_store_id()
        if not store_id:
            raise RuntimeError(
                "No vector store configured. Run: python -m src.scripts.manage_vector_store create"
            )

        state = self._load_state()
        tracked_files = state.get("files", {})

        # Get current local files
        local_files = {
            f.name: f
            for f in self.content_dir.glob("*.md")
            if f.name != "00_index.md"
        }

        result = SyncResult(added=[], removed=[], unchanged=[], errors=[])

        # Check for new or changed files
        for filename, file_path in local_files.items():
            current_checksum = self._compute_checksum(file_path)

            if filename not in tracked_files:
                # New file
                try:
                    with open(file_path, "rb") as f:
                        file_obj = await self.client.files.create(
                            file=f,
                            purpose="assistants",
                        )
                    await self.client.vector_stores.files.create(
                        vector_store_id=store_id,
                        file_id=file_obj.id,
                    )
                    tracked_files[filename] = {
                        "file_id": file_obj.id,
                        "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        "size_bytes": file_path.stat().st_size,
                        "checksum": current_checksum,
                    }
                    result.added.append(filename)
                    logger.info(f"Added: {filename}")
                except Exception as e:
                    result.errors.append(f"{filename}: {e}")
                    logger.error(f"Failed to add {filename}: {e}")

            elif tracked_files[filename]["checksum"] != current_checksum:
                # File changed - delete old, upload new
                try:
                    old_file_id = tracked_files[filename]["file_id"]
                    # Delete old file from vector store
                    try:
                        await self.client.vector_stores.files.delete(
                            vector_store_id=store_id,
                            file_id=old_file_id,
                        )
                        await self.client.files.delete(old_file_id)
                    except Exception:
                        pass  # Old file may already be gone

                    # Upload new version
                    with open(file_path, "rb") as f:
                        file_obj = await self.client.files.create(
                            file=f,
                            purpose="assistants",
                        )
                    await self.client.vector_stores.files.create(
                        vector_store_id=store_id,
                        file_id=file_obj.id,
                    )
                    tracked_files[filename] = {
                        "file_id": file_obj.id,
                        "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        "size_bytes": file_path.stat().st_size,
                        "checksum": current_checksum,
                    }
                    result.added.append(filename)
                    logger.info(f"Updated: {filename}")
                except Exception as e:
                    result.errors.append(f"{filename}: {e}")
                    logger.error(f"Failed to update {filename}: {e}")
            else:
                result.unchanged.append(filename)

        # Check for deleted files
        for filename in list(tracked_files.keys()):
            if filename not in local_files:
                try:
                    file_id = tracked_files[filename]["file_id"]
                    await self.client.vector_stores.files.delete(
                        vector_store_id=store_id,
                        file_id=file_id,
                    )
                    await self.client.files.delete(file_id)
                    del tracked_files[filename]
                    result.removed.append(filename)
                    logger.info(f"Removed: {filename}")
                except Exception as e:
                    result.errors.append(f"{filename}: {e}")
                    logger.error(f"Failed to remove {filename}: {e}")

        # Save updated state
        state["files"] = tracked_files
        state["last_sync"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)

        return result

    async def list_files(self) -> list[FileInfo]:
        """List all files tracked in the vector store.

        Returns:
            List of FileInfo objects.
        """
        state = self._load_state()
        files = []

        for filename, info in state.get("files", {}).items():
            files.append(
                FileInfo(
                    filename=filename,
                    file_id=info["file_id"],
                    uploaded_at=info["uploaded_at"],
                    size_bytes=info["size_bytes"],
                    checksum=info["checksum"],
                )
            )

        return sorted(files, key=lambda f: f.filename)

    async def get_status(self) -> dict[str, Any]:
        """Get vector store status.

        Returns:
            Dict with store info and file counts.
        """
        state = self._load_state()
        store_id = state.get("vector_store_id")

        status = {
            "configured": store_id is not None,
            "vector_store_id": store_id,
            "created_at": state.get("created_at"),
            "last_sync": state.get("last_sync"),
            "local_file_count": len(list(self.content_dir.glob("*.md"))) - 1,  # Exclude index
            "tracked_file_count": len(state.get("files", {})),
        }

        # Check store status in OpenAI if configured
        if store_id:
            try:
                store = await self.client.vector_stores.retrieve(store_id)
                status["store_status"] = store.status
                status["store_file_counts"] = {
                    "completed": store.file_counts.completed,
                    "in_progress": store.file_counts.in_progress,
                    "failed": store.file_counts.failed,
                    "total": store.file_counts.total,
                }
            except Exception as e:
                status["store_status"] = "error"
                status["store_error"] = str(e)

        return status

    async def delete_store(self) -> None:
        """Delete the vector store and clear state.

        Removes all files and the store from OpenAI.
        """
        store_id = await self.get_store_id()
        if not store_id:
            logger.warning("No vector store to delete")
            return

        state = self._load_state()

        # Delete all tracked files
        for filename, info in state.get("files", {}).items():
            try:
                await self.client.files.delete(info["file_id"])
                logger.debug(f"Deleted file: {filename}")
            except Exception:
                pass  # File may already be gone

        # Delete the vector store
        try:
            await self.client.vector_stores.delete(store_id)
            logger.info(f"Deleted vector store: {store_id}")
        except Exception as e:
            logger.warning(f"Failed to delete store from OpenAI: {e}")

        # Clear state file
        if self.state_file.exists():
            self.state_file.unlink()
            logger.debug("Cleared state file")


# Singleton instance
_manager: Optional[VectorStoreManager] = None


def get_vector_store_manager() -> VectorStoreManager:
    """Get or create the vector store manager instance."""
    global _manager
    if _manager is None:
        _manager = VectorStoreManager()
    return _manager
