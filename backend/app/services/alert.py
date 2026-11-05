"""Alert and notification service."""
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert, AlertType, AlertSeverity
from app.models.station import Station
from app.models.train import Train
from app.schemas.alert import AlertCreate, AlertUpdate, AlertSummary


class AlertService:
    """Alert management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_alert(self, alert_data: AlertCreate, creator_id: Optional[UUID] = None) -> Alert:
        """Create a new alert."""
        alert = Alert(**alert_data.model_dump())
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def get_alert(self, alert_id: UUID) -> Optional[Alert]:
        """Get alert by ID."""
        result = await self.db.execute(
            select(Alert)
            .where(Alert.id == alert_id)
            .options(selectinload(Alert.station), selectinload(Alert.train))
        )
        return result.scalar_one_or_none()

    async def list_alerts(
        self,
        type: Optional[AlertType] = None,
        severity: Optional[AlertSeverity] = None,
        station_id: Optional[UUID] = None,
        train_id: Optional[UUID] = None,
        unread_only: bool = False,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Alert]:
        """List alerts with filtering."""
        query = select(Alert).options(selectinload(Alert.station), selectinload(Alert.train))

        if active_only:
            now = datetime.utcnow()
            query = query.where(
                or_(
                    Alert.expires_at.is_(None),
                    Alert.expires_at > now,
                ),
                Alert.is_dismissed == False,
            )

        if type:
            query = query.where(Alert.type == type)
        if severity:
            query = query.where(Alert.severity == severity)
        if station_id:
            query = query.where(Alert.station_id == station_id)
        if train_id:
            query = query.where(Alert.train_id == train_id)
        if unread_only:
            query = query.where(Alert.is_read == False)

        query = query.offset(skip).limit(limit).order_by(desc(Alert.created_at))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_alert(self, alert_id: UUID, alert_data: AlertUpdate) -> Optional[Alert]:
        """Update alert (mark read/dismissed)."""
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        for field, value in alert_data.model_dump(exclude_unset=True).items():
            setattr(alert, field, value)

        if alert_data.is_dismissed and not alert.is_dismissed:
            alert.dismissed_at = datetime.utcnow()

        alert.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def mark_all_read(self, user_id: UUID) -> int:
        """Mark all alerts as read for user."""
        # In a real implementation, track per-user read status
        # For now, just return count
        result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.is_read == False,
                Alert.is_dismissed == False,
            )
        )
        return result.scalar() or 0

    async def get_alert_summary(self) -> AlertSummary:
        """Get alert summary for dashboard."""
        now = datetime.utcnow()

        # Total active alerts
        total_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                Alert.is_dismissed == False,
            )
        )
        total = total_result.scalar() or 0

        # Unread
        unread_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.is_read == False,
                or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                Alert.is_dismissed == False,
            )
        )
        unread = unread_result.scalar() or 0

        # By severity
        critical_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.severity == AlertSeverity.CRITICAL,
                or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                Alert.is_dismissed == False,
            )
        )
        critical = critical_result.scalar() or 0

        warning_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.severity == AlertSeverity.WARNING,
                or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                Alert.is_dismissed == False,
            )
        )
        warning = warning_result.scalar() or 0

        info_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.severity == AlertSeverity.INFO,
                or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                Alert.is_dismissed == False,
            )
        )
        info = info_result.scalar() or 0

        # By type
        by_type = {}
        for alert_type in AlertType:
            type_result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    Alert.type == alert_type,
                    or_(Alert.expires_at.is_(None), Alert.expires_at > now),
                    Alert.is_dismissed == False,
                )
            )
            by_type[alert_type.value] = type_result.scalar() or 0

        return AlertSummary(
            total=total,
            unread=unread,
            critical=critical,
            warning=warning,
            info=info,
            by_type=by_type,
        )

    async def create_overcrowding_alert(
        self,
        station_id: UUID,
        occupancy_rate: float,
        passenger_count: int,
        capacity: int,
    ) -> Alert:
        """Create overcrowding alert."""
        severity = AlertSeverity.WARNING
        if occupancy_rate >= 90:
            severity = AlertSeverity.CRITICAL
        elif occupancy_rate >= 75:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        return await self.create_alert(AlertCreate(
            type=AlertType.OVERCROWDING,
            severity=severity,
            title=f"Overcrowding at Station",
            message=f"Station occupancy at {occupancy_rate:.1f}% ({passenger_count}/{capacity})",
            station_id=station_id,
        ))

    async def create_delay_alert(
        self,
        train_id: UUID,
        delay_minutes: int,
        station_id: Optional[UUID] = None,
    ) -> Alert:
        """Create delay alert."""
        severity = AlertSeverity.WARNING
        if delay_minutes > 15:
            severity = AlertSeverity.CRITICAL

        return await self.create_alert(AlertCreate(
            type=AlertType.DELAY,
            severity=severity,
            title=f"Train Delay",
            message=f"Train delayed by {delay_minutes} minutes",
            train_id=train_id,
            station_id=station_id,
        ))

    async def cleanup_expired_alerts(self) -> int:
        """Clean up expired alerts."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Alert).where(
                Alert.expires_at.is_not(None),
                Alert.expires_at <= now,
                Alert.is_dismissed == False,
            )
        )
        alerts = result.scalars().all()
        for alert in alerts:
            alert.is_dismissed = True
            alert.dismissed_at = now
        await self.db.commit()
        return len(alerts)