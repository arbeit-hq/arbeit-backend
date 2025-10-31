"""
User Preferences API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
import structlog

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, UserPreference
from app.schemas.preference import PreferenceCreate, PreferenceUpdate, PreferenceOut, EmailFrequencyUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])
logger = structlog.get_logger()


@router.get("", response_model=PreferenceOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's preferences.
    
    Returns 404 if preferences not set.
    """
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not set. Please create preferences first."
        )
    
    logger.info("preferences_retrieved", user_id=str(current_user.id))
    return preference


@router.post("", response_model=PreferenceOut, status_code=status.HTTP_201_CREATED)
async def create_or_update_preferences(
    preference_data: PreferenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update user preferences.
    
    If preferences already exist, they will be updated.
    """
    # Check if preferences already exist
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    existing_preference = result.scalar_one_or_none()
    
    if existing_preference:
        # Update existing preferences
        for key, value in preference_data.model_dump(exclude_unset=True).items():
            setattr(existing_preference, key, value)
        
        db.commit()
        db.refresh(existing_preference)
        
        logger.info("preferences_updated", user_id=str(current_user.id))
        return existing_preference
    else:
        # Create new preferences
        new_preference = UserPreference(
            user_id=current_user.id,
            **preference_data.model_dump()
        )
        db.add(new_preference)
        db.commit()
        db.refresh(new_preference)
        
        logger.info("preferences_created", user_id=str(current_user.id))
        return new_preference


@router.patch("", response_model=PreferenceOut)
async def partial_update_preferences(
    preference_data: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Partially update user preferences.
    
    Only provided fields will be updated.
    """
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found. Please create preferences first."
        )
    
    # Update only provided fields
    update_data = preference_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(preference, key, value)
    
    db.commit()
    db.refresh(preference)
    
    logger.info("preferences_partially_updated", user_id=str(current_user.id), fields=list(update_data.keys()))
    return preference


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete user preferences (reset to defaults).
    """
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found."
        )
    
    db.delete(preference)
    db.commit()
    
    logger.info("preferences_deleted", user_id=str(current_user.id))
    return None


@router.patch("/email", response_model=PreferenceOut)
async def update_email_frequency(
    frequency_data: EmailFrequencyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update email notification frequency.
    
    Options:
    - 'realtime': Immediate notifications for new matches
    - 'daily': Daily digest at 08:00 UTC
    - 'weekly': Weekly digest on Monday at 08:00 UTC
    - 'none': No email notifications
    """
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = db.execute(stmt)
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found. Please create preferences first."
        )
    
    # Update notification frequency
    preference.notification_frequency = frequency_data.notification_frequency
    db.commit()
    db.refresh(preference)
    
    logger.info(
        "email_frequency_updated",
        user_id=str(current_user.id),
        frequency=frequency_data.notification_frequency
    )
    return preference