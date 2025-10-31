from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.core.database import get_db
from app.services.source_manager import SourceRegistry
from app.utils.logging import get_source_health_report
from app.tasks import run_scraper, run_all_scrapers

router = APIRouter()


@router.get("/source-health")
def get_all_source_health(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get health status for all sources"""
    registry = SourceRegistry(db)
    return registry.get_source_health()


@router.get("/source-health/{source_id}")
def get_source_health_detail(
    source_id: str,
    days: int = 7,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed health report for a specific source"""
    try:
        return get_source_health_report(db, source_id, days)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/source/{source_id}/enable")
def enable_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Enable a job source"""
    registry = SourceRegistry(db)
    success = registry.enable_source(source_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {"success": True, "message": "Source enabled"}


@router.post("/source/{source_id}/disable")
def disable_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Disable a job source"""
    registry = SourceRegistry(db)
    success = registry.disable_source(source_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {"success": True, "message": "Source disabled"}


@router.post("/scrape/{source_name}")
def trigger_scraper(source_name: str) -> Dict[str, Any]:
    """Manually trigger a scraper"""
    task = run_scraper.delay(source_name)
    return {
        "success": True,
        "task_id": task.id,
        "message": f"Scraper for {source_name} triggered"
    }


@router.post("/scrape-all")
def trigger_all_scrapers() -> Dict[str, Any]:
    """Manually trigger all scrapers"""
    task = run_all_scrapers.delay()
    return {
        "success": True,
        "task_id": task.id,
        "message": "All scrapers triggered"
    }


@router.get("/available-scrapers")
def list_available_scrapers() -> Dict[str, List[str]]:
    """List all available scrapers"""
    return {
        "scrapers": SourceRegistry.get_available_scrapers()
    }