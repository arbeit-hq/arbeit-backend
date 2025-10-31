"""
Alert system for critical errors and degraded sources.
Configure with Slack webhook or email service.
"""
import structlog
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = structlog.get_logger()


async def send_slack_alert(message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Send alert to Slack webhook.
    
    Args:
        message: Alert message
        metadata: Additional context
        
    Returns:
        True if sent successfully
    """
    slack_webhook = getattr(settings, 'slack_webhook_url', None)
    
    if not slack_webhook:
        logger.warning("slack_webhook_not_configured")
        return False
    
    try:
        payload = {
            "text": f"🚨 Arbeit Alert: {message}",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {"title": key, "value": str(value), "short": True}
                        for key, value in (metadata or {}).items()
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(slack_webhook, json=payload)
            response.raise_for_status()
            
        logger.info("slack_alert_sent", message=message)
        return True
        
    except Exception as e:
        logger.error("slack_alert_failed", error=str(e))
        return False


async def alert_source_degradation(source_name: str, error_rate: float) -> None:
    """Alert when a source is degrading"""
    await send_slack_alert(
        f"Source {source_name} is degraded",
        {
            "source": source_name,
            "error_rate": f"{error_rate:.1%}",
            "action": "Check source health dashboard"
        }
    )


async def alert_scraper_failure(source_name: str, error: str) -> None:
    """Alert when a scraper completely fails"""
    await send_slack_alert(
        f"Scraper {source_name} failed",
        {
            "source": source_name,
            "error": error,
            "action": "Check logs and source configuration"
        }
    )