"""EventBusService — single publish gateway for all SISMO events.

Replaces the fragmented event_bus.py / emit_state_change() pattern with a
typed, resilient service that:
  - validates permissions before persisting (D-04)
  - silently rejects duplicate event_ids (D-05 / BUS-02)
  - sends MongoDB write failures to a Dead Letter Queue (D-06 / BUS-03)
  - retries DLQ events with exponential backoff (D-07 / BUS-04)
  - exposes live health metrics (D-11 / BUS-05)
"""
import logging
from datetime import datetime, timezone, timedelta

from pymongo.errors import DuplicateKeyError

from event_models import RoddosEvent, DLQEvent, EVENT_LABELS
from permissions import validate_write_permission

logger = logging.getLogger(__name__)

# Exponential backoff intervals in minutes (max 5 retries: 5m, 15m, 45m, 2h, 6h)
_BACKOFF_MINUTES: list[int] = [5, 15, 45, 120, 360]


class EventBusService:
    """Publish gateway for all SISMO events.

    Usage::

        bus = EventBusService(db)
        await bus.emit(event)
    """

    def __init__(self, db) -> None:
        """
        Args:
            db: Motor AsyncIOMotorDatabase instance.
        """
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    async def emit(self, event: RoddosEvent) -> None:
        """Publish a RoddosEvent to roddos_events collection.

        Steps:
          1. Enforce agent write permission — raises PermissionError immediately
             (NOT sent to DLQ per D-06).
          2. Auto-populate label if empty.
          3. Insert into roddos_events.
          4. DuplicateKeyError → silent return (idempotent per D-05/BUS-02).
          5. Any other MongoDB error → DLQ, never raises to caller (D-06/BUS-03).

        Args:
            event: Validated RoddosEvent instance.

        Raises:
            PermissionError: If source_agent is not allowed to write to
                roddos_events. (Propagated immediately — not sent to DLQ.)
        """
        # 1. Permission enforcement — propagate immediately, never DLQ
        validate_write_permission(event.source_agent, "roddos_events")

        # 2. Auto-label
        if not event.label:
            event.label = EVENT_LABELS.get(event.event_type, event.event_type)

        # 3. Persist — handle failure modes separately
        try:
            await self.db.roddos_events.insert_one(event.to_mongo())
        except DuplicateKeyError:
            # 4. Idempotent: duplicate event_id already in collection — silent return
            logger.debug(
                "[EventBus] Duplicate event_id ignored: %s (%s)",
                event.event_id,
                event.event_type,
            )
            return
        except Exception as exc:
            # 5. Network / timeout / other MongoDB error → DLQ
            logger.error(
                "[EventBus] emit failed for %s (%s): %s — sending to DLQ",
                event.event_id,
                event.event_type,
                exc,
            )
            await self._send_to_dlq(event, exc)

    async def retry_dlq(self) -> int:
        """Retry failed DLQ events that are ready (next_retry <= now).

        Uses exponential backoff: 5min → 15min → 45min → 2h → 6h.
        Events that exhaust all 5 retries are permanently failed
        (next_retry set to None, retry_count = 5).

        Returns:
            Number of events successfully re-published to roddos_events.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        retried_count = 0

        cursor = self.db.roddos_events_dlq.find(
            {
                "retry_count": {"$lt": 5},
                "next_retry": {"$lte": now_iso},
            }
        )

        async for doc in cursor:
            event_id = doc.get("event_id")
            if not event_id:
                continue

            # Reconstruct a minimal event document from DLQ fields
            reconstructed = {
                "event_id": event_id,
                "event_type": doc.get("event_type"),
                "timestamp_utc": doc.get("timestamp_utc"),
                "source_agent": doc.get("source_agent", "sistema"),
                "actor": doc.get("original_actor", "dlq_retry"),
                "target_entity": doc.get("target_entity", ""),
                "payload": doc.get("payload", {}),
                "modules_to_notify": doc.get("modules_to_notify", []),
                "correlation_id": doc.get("correlation_id", ""),
                "version": doc.get("version", 1),
                "alegra_synced": doc.get("alegra_synced", False),
                "estado": "processed",
                "label": EVENT_LABELS.get(doc.get("event_type", ""), doc.get("event_type", "")),
            }

            try:
                await self.db.roddos_events.insert_one(reconstructed)
                # Success — remove from DLQ
                await self.db.roddos_events_dlq.delete_one({"event_id": event_id})
                retried_count += 1
                logger.info(
                    "[EventBus] DLQ retry success: %s (%s)",
                    event_id,
                    doc.get("event_type"),
                )
            except DuplicateKeyError:
                # Already in roddos_events — remove stale DLQ entry
                await self.db.roddos_events_dlq.delete_one({"event_id": event_id})
                retried_count += 1
                logger.info(
                    "[EventBus] DLQ duplicate removed (already exists): %s", event_id
                )
            except Exception as exc:
                # Retry failed — apply backoff or mark permanently failed
                current_retry_count = doc.get("retry_count", 0)
                new_retry_count = current_retry_count + 1

                if new_retry_count >= 5:
                    # Permanently failed — mark as exhausted
                    await self.db.roddos_events_dlq.update_one(
                        {"event_id": event_id},
                        {
                            "$set": {
                                "retry_count": new_retry_count,
                                "next_retry": None,
                                "permanently_failed": True,
                                "last_error": str(exc),
                                "permanently_failed_at": datetime.now(timezone.utc).isoformat(),
                            }
                        },
                    )
                    logger.error(
                        "[EventBus] DLQ permanently_failed after 5 retries: %s (%s)",
                        event_id,
                        doc.get("event_type"),
                    )
                else:
                    # Schedule next retry with exponential backoff
                    backoff_minutes = _BACKOFF_MINUTES[new_retry_count] if new_retry_count < len(_BACKOFF_MINUTES) else 360
                    next_retry = (
                        datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
                    ).isoformat()
                    await self.db.roddos_events_dlq.update_one(
                        {"event_id": event_id},
                        {
                            "$set": {
                                "retry_count": new_retry_count,
                                "next_retry": next_retry,
                                "last_error": str(exc),
                                "last_retry_at": datetime.now(timezone.utc).isoformat(),
                            }
                        },
                    )
                    logger.warning(
                        "[EventBus] DLQ retry %d failed for %s — next retry in %d min: %s",
                        new_retry_count,
                        event_id,
                        backoff_minutes,
                        exc,
                    )

        return retried_count

    async def get_bus_health(self) -> dict:
        """Return live bus health metrics from MongoDB.

        Returns:
            dict with keys:
              - dlq_pending (int): DLQ events with retry_count < 5
              - events_last_hour (int): events persisted in the last 60 minutes
              - status (str): "healthy" | "degraded" | "down"
        """
        # Count DLQ events still eligible for retry
        dlq_pending = await self.db.roddos_events_dlq.count_documents(
            {"retry_count": {"$lt": 5}}
        )

        # Count events published in the last hour
        one_hour_ago = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        events_last_hour = await self.db.roddos_events.count_documents(
            {"timestamp_utc": {"$gte": one_hour_ago}}
        )

        # Determine status
        if dlq_pending == 0:
            status = "healthy"
        elif dlq_pending < 10:
            status = "degraded"
        else:
            status = "down"

        return {
            "dlq_pending": dlq_pending,
            "events_last_hour": events_last_hour,
            "status": status,
        }

    async def get_recent_events(self, limit: int = 15) -> list:
        """Return recent events from roddos_events, sorted by timestamp descending.

        Provides the same functionality as the old event_bus.get_recent_events().
        """
        events = (
            await self.db.roddos_events.find({}, {"_id": 0})
            .sort("timestamp_utc", -1)
            .limit(limit)
            .to_list(limit)
        )
        return events

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _send_to_dlq(self, event: RoddosEvent, error: Exception) -> None:
        """Persist a failed event to the Dead Letter Queue.

        Never raises — failure to persist DLQ must not block the caller.

        Args:
            event: The RoddosEvent that failed to be persisted.
            error: The exception that caused the failure.
        """
        # First retry scheduled in 5 minutes
        next_retry = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat()

        dlq_event = DLQEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp_utc=event.timestamp_utc,
            source_agent=event.source_agent,
            payload=event.payload,
            correlation_id=event.correlation_id,
            original_actor=event.actor,
            error_message=str(error),
            retry_count=0,
            next_retry=next_retry,
        )

        try:
            await self.db.roddos_events_dlq.insert_one(dlq_event.to_mongo())
            logger.info(
                "[EventBus] Event %s (%s) sent to DLQ — next retry at %s",
                event.event_id,
                event.event_type,
                next_retry,
            )
        except Exception as dlq_exc:
            # Last resort: log and swallow — never block the caller
            logger.error(
                "[EventBus] CRITICAL: failed to persist to DLQ for event %s: %s",
                event.event_id,
                dlq_exc,
            )
