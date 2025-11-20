from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from .. import schemas, models, database
from ..services import auth_service

router = APIRouter()

@router.get("/stats/demographics", response_model=List[schemas.DemographicStat])
def get_demographics(
    group_by: str = "provincia",
    admin_user: models.User = Depends(auth_service.get_current_admin_user),
    db: Session = Depends(database.get_db)
):
    """
    (Solo Admin) Obtiene estadísticas demográficas de los perfiles de onboarding.
    Agrupa por 'pais' o 'profesion'.
    """
    if group_by not in ["provincia", "profesion"]:
        group_by_col = models.OnboardingProfile.provincia
    else:
        group_by_col = getattr(models.OnboardingProfile, group_by)

    stats = db.query(
        group_by_col.label("group"), 
        func.count(models.OnboardingProfile.id).label("count")
    ).group_by(group_by_col).order_by(func.count(models.OnboardingProfile.id).desc()).all()
    
    return [schemas.DemographicStat(group=row.group, count=row.count) for row in stats if row.group]

@router.get("/stats/usage", response_model=List[schemas.UsageStat])
def get_usage_stats(
    admin_user: models.User = Depends(auth_service.get_current_admin_user),
    db: Session = Depends(database.get_db)
):
    """
    (Solo Admin) Obtiene el número de consultas de usuario (mensajes) por día.
    """
    # Esta consulta es para SQLite. Puede necesitar ajuste para PostgreSQL (usando DATE_TRUNC)
    stats = db.query(
        func.strftime('%Y-%m-%d', models.Message.timestamp).label("date"),
        func.count(models.Message.id).label("count")
    ).filter(
        models.Message.sender == models.SenderType.user
    ).group_by(
        func.strftime('%Y-%m-%d', models.Message.timestamp)
    ).order_by(
        func.strftime('%Y-%m-%d', models.Message.timestamp).desc()
    ).limit(30).all() # Últimos 30 días
    
    return [schemas.UsageStat(date=row.date, count=row.count) for row in stats]

@router.get("/stats/top-queries", response_model=List[schemas.DemographicStat])
def get_top_queries(
    admin_user: models.User = Depends(auth_service.get_current_admin_user),
    db: Session = Depends(database.get_db)
):
    """
    (Solo Admin) Obtiene los temas (consultas) más frecuentes.
    """
    stats = db.query(
        models.Message.content.label("group"),
        func.count(models.Message.id).label("count")
    ).filter(
        models.Message.sender == models.SenderType.user
    ).group_by(
        models.Message.content
    ).order_by(
        func.count(models.Message.id).desc()
    ).limit(20).all() # Top 20 consultas
    
    return [schemas.DemographicStat(group=row.group, count=row.count) for row in stats]